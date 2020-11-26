import collections
import re
from typing import Any, List, Optional, Tuple

import xlrd

from .types import StateError, MiSeqOutput, MiSeqResult, SampleSheetColumn, column_label

from common import xlsx_strip

_PEAK_RE = re.compile(r"^peak([0-9]+)$", re.I)
_PEAK_INDEL = re.compile(r"(-?[0-9]+)( \(inframe\))?")


def load_miseq_table(filename: str) -> MiSeqOutput:
    knockouts = {}  # type: MiSeqOutput
    with xlrd.open_workbook(filename) as workbook:

        def _read_row(row: int) -> List[Any]:
            return [
                xlsx_strip(sheet.cell(row, column).value)
                for column in range(sheet.ncols)
            ]

        for sheet in workbook.sheets():
            header = _read_row(0)

            for row_idx in range(1, sheet.nrows):
                row = _read_row(row_idx)
                if len(row) != len(header):
                    raise StateError(
                        f"Row {row_idx} contains the wrong " "number of columns!"
                    )

                values = dict(zip(header, row))
                knockout = values["Target"]

                result = {
                    "target": knockout,
                    "index": int(values["Index/Well"]),
                    "reads": int(values["Reads"]),
                    "wt": int(values["WT"]),
                    "indel": int(values["Indel"]),
                    "picked": False,
                    "peaks": [],
                    "comment": "",
                }  # type: MiSeqResult

                for key, value in values.items():
                    if _PEAK_RE.match(key) and value:
                        indel, inframe = _PEAK_INDEL.match(value).groups()
                        pct = values[key + "%"]

                        result["peaks"].append(
                            {
                                "indel": int(indel),
                                "inframe": bool(inframe),
                                "pct": float(pct),
                            }
                        )

                result["peaks"].sort(key=lambda peak: peak["pct"], reverse=True)

                if any(peak["inframe"] for peak in result["peaks"]):
                    result["comment"] = "In-frame"

                result["peaks"].sort(key=lambda peak: peak["pct"], reverse=True)

                column = knockouts.setdefault(knockout, {})
                column[int(values["Index/Well"])] = result

    return knockouts


def load_samplesheet(filename: str) -> List[SampleSheetColumn]:
    # Read first sheet in spreadsheet (as columns)
    table = _read_xlsx_columns(filename)
    # Locate rectangle containing knockouts (0 or 1s)
    cells = _locate_cells(table)

    if not cells:
        raise StateError("Could not locate knockouts")
    elif cells.top < 3:
        raise StateError("Could not locate headers")

    columns = []  # type: List[SampleSheetColumn]
    for column_idx in range(cells.left, cells.right):
        raw_column = table[column_idx]
        layout = raw_column[cells.top : cells.bottom]
        label = "[%s] %s" % (column_label(column_idx + 1), raw_column[cells.top - 1])

        column = {
            "index": column_idx + 1,
            "cells": [idx for idx, value in enumerate(layout) if value],
            "miseq": None,
            "meta": {
                "id": label,
                "extraction": raw_column[cells.top - 3],
                "amplicon": raw_column[cells.top - 2],
                "knockout": raw_column[cells.top - 1],
            },
        }  # type: SampleSheetColumn

        # SampleSheetColumn values propagate left-to-right
        for key, value in column["meta"].items():
            if not value and columns:
                column["meta"][key] = columns[-1]["meta"][key]

        columns.append(column)

    return columns


_Rect = collections.namedtuple("_Rect", ("top", "left", "bottom", "right"))


XLSXTable = List[List[object]]


def _read_xlsx_columns(filename: str) -> XLSXTable:
    table = []

    with xlrd.open_workbook(filename) as workbook:
        for sheet in workbook.sheets():
            for column in range(sheet.ncols):
                cells = []

                for row in range(sheet.nrows):
                    cells.append(xlsx_strip(sheet.cell(row, column).value))

                table.append(cells)

            # Only read first sheet
            break

    return table


def _locate_cells(table: XLSXTable) -> Optional[_Rect]:
    best_row = None
    best_column = None
    best_width = 0
    best_height = 0

    for column_idx, column in enumerate(table):
        if (len(table) - column_idx) * len(column) < best_width * best_height:
            break

        for row_idx, _ in enumerate(column):
            width, height = _grow_selection(table, row_idx, column_idx)
            if width * height > best_width * best_height:
                best_row = row_idx
                best_column = column_idx
                best_width = width
                best_height = height

    if best_row is not None and best_column is not None:
        return _Rect(
            top=best_row,
            left=best_column,
            bottom=best_row + best_height,
            right=best_column + best_width,
        )

    return None


def _grow_selection(
    table: List[List[object]], row_idx: int, column_idx: int
) -> Tuple[int, int]:
    width = 0
    height = 0

    for column in table[column_idx:]:
        current_height = 0

        for cell in column[row_idx:]:
            if cell in (0, 1):
                current_height += 1
            else:
                break

        if not current_height or current_height < height:
            break

        width += 1
        height = min(height or current_height, current_height)

    return width, height

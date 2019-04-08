#!/usr/bin/env python3
import collections
import copy
from typing import Dict, List, Optional, Tuple, Set

import xlrd

from mypy_extensions import TypedDict

import common


class SampleSheetError(Exception):
    pass


# Headers above knockouts (0 or 1s) containing labels
HEADERS = ['extraction', 'amplicon', 'knockout']


SplitGroup = TypedDict('SplitGroup', {
    'user': bool,
    'auto': bool,
})


Knockout = TypedDict('Knockout', {
    'headers': Dict[str, str],
    'column': List[Optional[str]],
    'split': SplitGroup,
    'group': str,
})


SampleSheet = TypedDict('SampleSheet', {
    'knockouts': List[Knockout],
    'headers': List[str],
    'width': int,
    'height': int,
    'group_by': str,
})


GroupCellCounts = Dict[str, Set[int]]


def load(filename: str) -> SampleSheet:
    # Read first sheet in spreadsheet (as columns)
    table = _read_xlsx_columns(filename)
    # Locate rectangle containing knockouts (0 or 1s)
    cells = _locate_cells(table)

    if not cells:
        raise SampleSheetError('Could not locate knockouts')
    elif not cells.top:
        raise SampleSheetError('Could not locate knockout names')

    knockouts = []  # type: List[Knockout]
    for column_idx in range(cells.left, cells.right):
        column = table[column_idx]

        headers = {}
        for offset, key in enumerate(reversed(HEADERS), start=1):
            if cells.top - offset >= 0:
                value = column[cells.top - offset]
                if not value and knockouts:
                    # Groupings propagate left-to-right
                    value = knockouts[-1]['headers'][key]

                headers[key] = value

        headers['id'] = '[%s] %s' % (common.column_label(column_idx + 1),
                                     headers['knockout'])

        knockouts.append({
            'column': ['DummyValue' if value else None
                       for value in column[cells.top:cells.bottom]],
            'headers': headers,
            'group': str(column_idx),
            'split': {
                'auto': False,
                'user': False,
            },
        })

    samplesheet = {
        'headers': HEADERS[-cells.top:],
        'knockouts': knockouts,
        'width': len(knockouts),
        'height': cells.bottom - max(0, cells.top - 3),
        'group_by': 'id',
    }  # type: SampleSheet

    # Group by most significant available header
    return group_by(samplesheet, samplesheet['headers'][0])


def group_by(samplesheet: SampleSheet, key: str) -> SampleSheet:
    cell_counts = collections.defaultdict(set)  # type: GroupCellCounts

    samplesheet = copy.deepcopy(samplesheet)
    samplesheet['group_by'] = key

    for knockout in samplesheet['knockouts']:
        current_group = knockout['headers'][key]
        knockout['group'] = current_group
        cell_counts[current_group].add(sum(map(bool, knockout['column'])))

    cell_counts = dict(cell_counts)
    for knockout in samplesheet['knockouts']:
        group = knockout['group']
        is_verification = len(cell_counts[group] - set((0,))) > 1

        knockout['split'] = {
            'auto': is_verification,
            'user': False,
        }

        knockout['column'] = _update_cell_labels(knockout['column'],
                                                 is_verification)

    return samplesheet


def set_user_split(samplesheet: SampleSheet, group: str, value: bool) -> SampleSheet:
    samplesheet = copy.deepcopy(samplesheet)

    for knockout in samplesheet['knockouts']:
        if knockout['group'] == group:
            knockout['split']['user'] = value

    return samplesheet


def get_column_for_ko(samplesheet: SampleSheet, knockout: str) -> List[Optional[str]]:
    for ko in samplesheet['knockouts']:
        if ko['headers']['knockout'] == knockout:
            return ko['column']

    return ['<NA>'] * 96


def get_groups(samplesheet: SampleSheet) -> List[Tuple[str, bool]]:
    result = []
    observed = set()  # type: Set[str]

    for knockout in samplesheet['knockouts']:
        group = _group(knockout)
        if group not in observed:
            result.append((group, any(knockout['split'].values())))
            observed.add(group)

    return result


def get_group(samplesheet: SampleSheet, group: str) -> List[Knockout]:
    knockouts = []
    for knockout in samplesheet['knockouts']:
        if _group(knockout) == group:
            knockouts.append(knockout)

    return knockouts


_Rect = collections.namedtuple('_Rect', ('top', 'left', 'bottom', 'right'))


def _group(knockout: Knockout) -> str:
    if any(knockout['split'].values()):
        if knockout['group'] != knockout['headers']['knockout']:
            return '{} ({})'.format(knockout['headers']['knockout'],
                                    knockout['group'])

    return knockout['group']


def _update_cell_labels(column: List[Optional[str]], is_verification: bool) -> List[Optional[str]]:
    column = list(column)
    counter = 0
    for row, value in enumerate(column):
        if value:
            if is_verification:
                column[row] = str(row + 1)
            else:
                column[row] = common.clone_label(counter)
            counter += 1

    return column


XLSXTable = List[List[object]]


def _read_xlsx_columns(filename: str) -> XLSXTable:
    table = []

    with xlrd.open_workbook(filename) as workbook:
        for sheet in workbook.sheets():
            for column in range(sheet.ncols):
                cells = []

                for row in range(sheet.nrows):
                    cells.append(sheet.cell(row, column).value)

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
        return _Rect(top=best_row,
                     left=best_column,
                     bottom=best_row + best_height,
                     right=best_column + best_width)

    return None


def _grow_selection(table: List[List[object]], row_idx: int, column_idx: int) -> Tuple[int, int]:
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

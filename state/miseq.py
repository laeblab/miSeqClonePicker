import copy
import re
from typing import Any, Dict, List, Optional

from mypy_extensions import TypedDict

import xlrd


class MiSeqOutputError(Exception):
    pass


_PEAK_RE = re.compile(r'^peak([0-9]+)$', re.I)
_PEAK_INDEL = re.compile(r'(-?[0-9]+)( \(inframe\))?')

Peak = TypedDict('Peak', {
    'indel': int,
    'inframe': bool,
    'pct': float,
})


Result = TypedDict('Result', {
    'index': int,
    'reads': int,
    'wt': int,
    'indel': int,
    'picked': bool,
    'peaks': List[Peak],
    'comment': str,
    'target': str,
})


Column = Dict[int, Result]
MiSeqOutput = Dict[str, Column]


def load(filename: str) -> MiSeqOutput:
    knockouts = {}  # type: MiSeqOutput
    with xlrd.open_workbook(filename) as workbook:
        def _read_row(row: int) -> List[Any]:
            return [sheet.cell(row, column).value
                    for column in range(sheet.ncols)]

        for sheet in workbook.sheets():
            header = _read_row(0)

            for row_idx in range(1, sheet.nrows):
                row = _read_row(row_idx)
                if len(row) != len(header):
                    raise MiSeqOutputError(f'Row {row_idx} contains the wrong '
                                           'number of columns!')

                values = dict(zip(header, row))
                knockout = values['Target']

                result = {
                    'target': knockout,
                    'index': int(values['Index/Well']),
                    'reads': int(values['Reads']),
                    'wt': int(values['WT']),
                    'indel': int(values['Indel']),
                    'picked': False,
                    'peaks': [],
                    'comment': '',
                }  # type: Result

                for key, value in values.items():
                    if _PEAK_RE.match(key) and value:
                        indel, inframe = _PEAK_INDEL.match(value).groups()
                        pct = values[key + '%']

                        result['peaks'].append({
                            'indel': int(indel),
                            'inframe': bool(inframe),
                            'pct': float(pct),
                        })

                result['peaks'].sort(key=lambda peak: peak['pct'],
                                     reverse=True)

                if any(peak['inframe'] for peak in result['peaks']):
                    result['comment'] = '(inframe)'

                result['peaks'].sort(key=lambda peak: peak['pct'],
                                     reverse=True)

                column = knockouts.setdefault(knockout, {})
                column[int(values['Index/Well'])] = result

    return knockouts


def is_picked(miseq: MiSeqOutput, target: str, index: int) -> bool:
    return miseq[target][index]['picked']


def toggle_picked(miseq: MiSeqOutput, target: str, index: int) -> MiSeqOutput:
    miseq = copy.deepcopy(miseq)
    miseq[target][index]['picked'] = not is_picked(miseq, target, index)

    return miseq


def set_picked(miseq: MiSeqOutput, target: str, index: int, picked: bool) -> MiSeqOutput:
    miseq = copy.deepcopy(miseq)
    miseq[target][index]['picked'] = picked

    return miseq


def set_comment(miseq: MiSeqOutput, target: str, index: int, comment: str) -> MiSeqOutput:
    miseq = copy.deepcopy(miseq)
    miseq[target][index]['comment'] = comment

    return miseq

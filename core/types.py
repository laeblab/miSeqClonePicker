import string

from typing import Dict, List, Optional
from mypy_extensions import TypedDict


class StateError(Exception):
    pass


MiSeqPeak = TypedDict('MiSeqPeak', {
    'indel': int,
    'inframe': bool,
    'pct': float,
})


MiSeqResult = TypedDict('MiSeqResult', {
    'index': int,
    'reads': int,
    'wt': int,
    'indel': int,
    'picked': bool,
    'peaks': List[MiSeqPeak],
    'comment': str,
    'target': str,
})


MiSeqColumn = Dict[int, MiSeqResult]
MiSeqOutput = Dict[str, MiSeqColumn]


SampleSheetColumn = TypedDict('SampleSheetColumn', {
    'index': int,
    'meta': Dict[str, str],
    'cells': List[int],
    'miseq': MiSeqColumn,
})


Clone = TypedDict('Clone', {
    'label': str,
    'knockouts': Dict[str, Optional[MiSeqResult]]
})


# FIXME
def column_label(number: int) -> str:
    assert number > 0, number
    label = []
    while number:
        number, remainder = divmod(number - 1, 26)
        label.append(chr(65 + remainder))

    return ''.join(label[::-1])


# FIXME
def clone_label(number: int) -> str:
    assert number >= 0
    return string.ascii_uppercase[(number // 12)] + str(number % 12 + 1)

#!/usr/bin/env python3
import collections

from typing import Dict, List, Optional

from core_types import column_label, clone_label  # FIXME
from core_types import Clone, SampleSheetColumn, MiSeqColumn

from .load import load_samplesheet


# def toggle_picked(miseq: MiSeqOutput, target: str, index: int) -> MiSeqOutput:
#     miseq = copy.deepcopy(miseq)
#     miseq[target][index]['picked'] = not miseq[target][index]['picked']

#     return miseq


# def set_comment(miseq: MiSeqOutput, target: str, index: int, comment: str) -> MiSeqOutput:
#     miseq = copy.deepcopy(miseq)
#     miseq[target][index]['comment'] = comment

#     return miseq


class Group:
    __slots__ = [
        'label',
        'columns',
        'clones',
        'parent',
    ]

    def __init__(self, label: str, columns: List[SampleSheetColumn], parent: Optional['Group'] = None) -> None:
        self.label = label
        self.columns = columns
        self.clones = None  # type: Optional[List[Clone]]
        self.parent = parent

        if parent and len(columns) != 1:
            raise ValueError('Split group %r must contain exactly one column'
                             % (label,))

        clone_counts = set(len(column['cells']) for column in columns)
        # Empty columns are allowed in a group
        if len(clone_counts - set((0,))) <= 1:
            # Create named clones from first non-empty column
            self.clones = []
            for column in columns:
                if column['cells']:
                    for idx, row in enumerate(column['cells']):
                        self.clones.append({
                            'label': str(row) if parent else clone_label(idx),
                            'knockouts': {},
                        })

                    break

            # Assign knockouts and miSeq data (if available) to each clone
            self.update_mapping()

    def update_mapping(self) -> None:
        if self.clones is not None:
            for column in self.columns:
                miseq = column['miseq']
                key = column['meta']['knockout']

                assert not miseq or len(self.clones) == len(miseq)
                assert len(column['cells']) in (0, len(self.clones))
                for cell, clone in zip(column['cells'], self.clones):
                    knockouts = clone['knockouts']
                    knockouts[key] = miseq[cell] if miseq is not None else None

    def is_valid(self) -> bool:
        return self.clones is not None

    def is_split(self) -> bool:
        return self.parent is not None

    def split(self) -> List['Group']:
        split_groups = []   # type: List[Group]
        for column in self.columns:
            label = '[%s] %s' % (column_label(column['index']),
                                 column['meta']['knockout'])
            split_groups.append(Group(label, [column], self))

        return split_groups


class State:
    __slots__ = [
        'columns',
        'groups',
        'grouped_by',
        'miseq',
    ]

    def __init__(self) -> None:
        self.columns = []  # type: List[SampleSheetColumn]
        self.groups = []  # type: List[Group]
        self.grouped_by = None  # type: Optional[str]

    def load_samplesheet(self, filename: str) -> None:
        self.columns = load_samplesheet(filename)
        self.groups = []
        self.grouped_by = None
        self.group_by('extraction')

    def load_miseq_table(self, filename: str) -> None:
        # TODO
        self.reset_mapping()

    def reset_mapping(self) -> None:
        for column in self.columns:
            column['miseq'] = None

        for group in self.groups:
            group.update_mapping()

    def group_by(self, key: str) -> None:
        if key != self.grouped_by:
            column_groups = collections.OrderedDict()  # type: Dict[str, List[SampleSheetColumn]]

            for column in self.columns:
                value = column['meta'][key]
                column_group = column_groups.setdefault(value, [])
                column_group.append(column)

            final_groups = []
            for label, columns in column_groups.items():
                group = Group(label, columns)
                if group.is_valid():
                    final_groups.append(group)
                else:
                    final_groups.extend(group.split())

            self.grouped_by = key
            self.groups = final_groups

    def split_group(self, to_split: Group) -> None:
        if not to_split.is_split():
            groups = []  # type: List[Group]
            for group in self.groups:
                if group is to_split:
                    groups.extend(to_split.split())
                else:
                    groups.append(group)

            self.groups = groups

    def merge_group(self, to_merge: Group) -> None:
        if to_merge.parent and to_merge.parent.is_valid():
            groups = []  # type: List[Group]
            was_inserted = False
            for group in self.groups:
                if group.parent is to_merge.parent:
                    if not was_inserted:
                        groups.append(to_merge.parent)
                        was_inserted = True
                else:
                    groups.append(group)

            self.groups = groups
            to_merge.parent.update_mapping()

    def assign_miseq(self, miseq: MiSeqColumn, target: SampleSheetColumn) -> None:
        updated_columns = []
        for column in self.columns:
            if column is target:
                column['miseq'] = miseq
                updated_columns.append(column)
            elif column['miseq'] is miseq:
                column['miseq'] = None
                updated_columns.append(column)

        for group in self.groups:
            for column in group.columns:
                if column in updated_columns:
                    group.update_mapping()
                    break

#!/usr/bin/env python3
from typing import Any, List

import wx

from common import wx_find, wx_bind
from state import State


class KOMappingWidget(object):
    def __init__(self, root: "wx.App", state: State) -> None:
        self._root = root
        self._state = state
        self._updating_lists = False

        wx_bind("mapping_load", wx.EVT_BUTTON, self.OnLoadButton)

        root.undo_buttons.append(wx_find("mapping_button_undo"))
        root.redo_buttons.append(wx_find("mapping_button_redo"))

        self.ss_list = wx_find("mapping_current")
        self.ss_list.ClearAll()
        self.ss_list.AppendColumn("SampleSheet targets")
        self.ss_list.AppendColumn("miSeq targets")
        # FIXME: Workaround for dark theme being applied
        self.ss_list.SetForegroundColour(wx.Colour(35, 35, 35))

        self.miseq_list = wx_find("mapping_miseq")
        self.miseq_list.ClearAll()
        self.miseq_list.AppendColumn("miSeq targets")
        self.miseq_list.AppendColumn("SampleSheet targets")
        # FIXME: Workaround for dark theme being applied
        self.miseq_list.SetForegroundColour(wx.Colour(35, 35, 35))

        self.ss_list.Bind(wx.EVT_LIST_ITEM_SELECTED, self.OnViewChanged)
        self.miseq_list.Bind(wx.EVT_LIST_ITEM_SELECTED, self.OnMappingChanged)

        self.refresh_ui()

    def refresh_ui(self) -> None:
        ss_targets = self._state.samplesheet_target_names()
        ss_mapping = self._state.ko_mapping
        ss_mapping_default = self._state.default_ko_mapping
        self._build_list(self.ss_list, ss_targets, ss_mapping)
        self._refresh_colors(self.ss_list, ss_mapping_default)

        miseq_targets = self._state.miseq_target_names()
        miseq_mapping = {
            value: key for key, value in ss_mapping.items() if value is not None
        }
        default_miseq_mapping = {
            value: key for key, value in ss_mapping_default.items() if value is not None
        }
        self._build_list(self.miseq_list, miseq_targets, miseq_mapping)
        self._refresh_colors(self.miseq_list, default_miseq_mapping)

    def _build_list(self, widget: Any, targets: List[str], mapping: Any) -> None:
        while widget.GetItemCount() < len(targets):
            widget.Append(["", ""])

        while widget.GetItemCount() > len(targets):
            widget.DeleteItem(widget.GetItemCount() - 1)

        for idx, value in enumerate(sorted(targets, key=str.lower)):
            widget.SetItem(idx, 0, value)
            widget.SetItem(idx, 1, mapping.get(value) or "")

        for column in range(widget.GetColumnCount()):
            widget.SetColumnWidth(column, wx.LIST_AUTOSIZE)

    def _refresh_colors(self, widget: Any, default_mapping: Any) -> None:
        for row_idx in range(widget.GetItemCount()):
            key = widget.GetItemText(row_idx, 0)
            current_value = widget.GetItemText(row_idx, 1)
            default_value = default_mapping.get(key) or ""

            if not current_value:
                colour = wx.RED
            elif current_value != default_value:
                colour = wx.YELLOW
            else:
                colour = wx.WHITE

            widget.SetItemBackgroundColour(row_idx, colour)

    def OnLoadButton(self, _event: Any) -> None:
        self._root.load_miseq_output()

    def OnViewChanged(self, event: Any) -> None:
        if self._updating_lists:
            return

        try:
            self._updating_lists = True

            for row_idx in _selected_items(self.miseq_list):
                self.miseq_list.SetItemState(row_idx, 0, wx.LIST_STATE_SELECTED)

            key = None
            for row_idx in _selected_items(self.ss_list):
                key = self.ss_list.GetItemText(row_idx, 1)
                break

            if key:
                for miseq_row in range(self.miseq_list.GetItemCount()):
                    if self.miseq_list.GetItemText(miseq_row) == key:
                        self.miseq_list.Select(miseq_row, True)
                        self.miseq_list.Focus(miseq_row)
                        break

        finally:
            self._updating_lists = False

    def OnMappingChanged(self, event: Any) -> None:
        if self._updating_lists:
            return

        try:
            self._updating_lists = True

            ss_selection = _selected_items(self.ss_list)
            miseq_selection = _selected_items(self.miseq_list)

            if len(ss_selection) != 1 or len(miseq_selection) != 1:
                return

            ss_key = self.ss_list.GetItemText(ss_selection[0], 0)
            ss_value = self.ss_list.GetItemText(ss_selection[0], 1)
            miseq_key = self.miseq_list.GetItemText(miseq_selection[0])

            if ss_value != miseq_key:
                self._state.mapping_set(samplesheet=ss_key, miseq=miseq_key)
                self._root.refresh_ui(self)

        finally:
            self._updating_lists = False


def _selected_items(widget: Any) -> List[int]:
    selection = []
    row_idx = widget.GetFirstSelected()
    while row_idx != -1:
        selection.append(row_idx)
        row_idx = widget.GetNextSelected(row_idx)

    return selection

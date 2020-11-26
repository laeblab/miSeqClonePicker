#!/usr/bin/env python3
from typing import Any, Optional

import wx

from common import wx_bind, wx_find
from state import State, MiSeqOutput


_ARROW_UP = "▲"
_ARROW_DOWN = "▼"

_COLUMNS = ("Index", "Sample", "Reads", "WT", "Indel", "Indel%")
_COLUMN_WIDTH = (40, 40, 80, 80, 80, 60)


class MiSeqOutputWidget(object):
    def __init__(self, root: "wx.App", state: State) -> None:
        self._root = root
        self._state = state
        self._last_data = None  # type: Optional[MiSeqOutput]
        self._sort_column = 5
        self._sort_reverse = True

        wx_bind("miseq_load", wx.EVT_BUTTON, self.OnLoadButton)
        wx_bind("miseq_output", wx.EVT_LIST_ITEM_ACTIVATED, self.OnPickItem)
        wx_bind("miseq_output", wx.EVT_LIST_COL_CLICK, self.OnColumnClick)
        wx_bind("miseq_targets", wx.EVT_LISTBOX, self.OnListBox)

        wx_bind("miseq_min_pct", wx.EVT_SPINCTRL, self.OnSpinBox)
        wx_bind("miseq_min_reads", wx.EVT_SPINCTRL, self.OnSpinBox)

        root.undo_buttons.append(wx.FindWindowByName("miseq_button_undo"))
        root.redo_buttons.append(wx.FindWindowByName("miseq_button_redo"))

        self._targets = wx_find("miseq_targets")
        self._output = wx_find("miseq_output")
        self._min_pct = wx_find("miseq_min_pct")
        self._min_reads = wx_find("miseq_min_reads")

        self._min_pct.SetValue(90)  # FIXME: Should be saved
        self._min_reads.SetValue(1000)  # FIXME: Should be saved

        self.refresh_ui()

    def OnColumnClick(self, event: Any) -> None:
        if event.GetColumn() < len(_COLUMNS):
            if event.GetColumn() == self._sort_column:
                self._sort_reverse = not self._sort_reverse
            else:
                self._sort_column = event.GetColumn()

            self._refresh_output()
            self._refresh_output_colours()

    def OnSpinBox(self, _event: Any) -> None:
        self._refresh_output_colours()

    def OnListBox(self, _event: Any) -> None:
        self._refresh_output()
        self._refresh_output_colours()

    def OnLoadButton(self, _event: Any) -> None:
        self._root.load_miseq_output()

    def OnPickItem(self, event: Any) -> None:
        knockout = self._get_selection()
        if knockout is not None:
            self._state.miseq_toggle_picked(knockout, event.GetData())
            self._set_item_picked(event.GetIndex())

            self._last_data = self._state.miseq
            self._root.refresh_ui()

    def refresh_ui(self) -> None:
        data = self._state.miseq

        if data is not self._last_data:
            self._targets.Clear()
            if data:
                self._targets.InsertItems(sorted(data), 0)
                self._targets.SetSelection(0)

            self._refresh_output()

        self._refresh_output_colours()

        self._last_data = data

    def _refresh_output(self) -> None:
        self._output.ClearAll()
        for idx, column in enumerate(_COLUMNS):
            if idx == self._sort_column:
                arrow = _ARROW_DOWN if self._sort_reverse else _ARROW_UP
                column = "%s%s" % (arrow, column)

            self._output.AppendColumn(column)
            self._output.SetColumnWidth(idx, _COLUMN_WIDTH[idx])

        knockout = self._get_selection()
        if knockout is not None:
            data = self._state.miseq[knockout]
            num_peaks = max(
                (len(column["peaks"]) for column in data.values()), default=0
            )

            for _ in range(num_peaks):
                self._output.AppendColumn("Peak")
                self._output.SetColumnWidth(self._output.GetColumnCount() - 1, 140)

            for item_data, entry in self._sorted_entries(knockout):
                self._output.Append(entry)
                row = self._output.GetItemCount() - 1
                self._output.SetItemData(row, item_data)

    def _sorted_entries(self, knockout: str) -> Any:
        data = self._state.miseq[knockout]

        def _sort_key(pair: Any) -> Any:
            item_data, entry = pair
            if self._sort_column == 0:
                return entry[0]
            elif self._sort_column == 1:
                return entry[1]

            if item_data < 0:
                return float("-inf") if self._sort_reverse else float("inf")

            result = data[item_data]
            if self._sort_column == 2:
                return result["reads"]
            elif self._sort_column == 3:
                return result["wt"]
            elif self._sort_column == 4:
                return result["indel"]
            elif self._sort_column == 5:
                return result["indel"] / result["reads"]
            else:
                return item_data

        entries = list(self._build_entries(knockout))
        entries.sort(key=_sort_key, reverse=self._sort_reverse)

        return entries

    def _build_entries(self, knockout: str) -> Any:
        data = self._state.miseq[knockout]
        labels = self._state.samplesheet_column(knockout)

        for index, label in enumerate(labels, start=1):
            if label is not None:
                if index in data:
                    result = data[index]
                    item_data = index
                    entry = [
                        "%02i" % (index,),
                        label if label != str(index) else "-",
                        str(result["reads"]),
                        str(result["wt"]),
                        str(result["indel"]),
                        "%02.2f" % (100.0 * result["indel"] / result["reads"]),
                    ]

                    for peak in result["peaks"]:
                        if peak["inframe"]:
                            tmpl = "%+i (%.2f%%; inframe)"
                        else:
                            tmpl = "%+i (%.2f%%)"

                        entry.append(tmpl % (peak["indel"], peak["pct"] * 100))
                else:
                    item_data = -index
                    entry = [
                        "%02i" % (index,),
                        label if label != str(index) else "-",
                        "?",
                        "?",
                        "?",
                        "?",
                    ]

                yield (item_data, entry)

    def _refresh_output_colours(self) -> None:
        for row in range(self._output.GetItemCount()):
            self._set_item_picked(row)

    def _set_item_picked(self, row: int) -> None:
        knockout = self._get_selection()
        if knockout is not None:
            index = self._output.GetItemData(row)

            default_font = self._output.GetFont()
            bold_font = default_font.Bold()

            text_font = default_font
            text_colour = wx.BLACK
            background_colour = wx.WHITE

            if index > 0:
                result = self._state.miseq[knockout][index]
                min_reads = self._min_reads.GetValue()
                min_pct = self._min_pct.GetValue()

                if result["picked"]:
                    background_colour = wx.LIGHT_GREY
                    text_font = bold_font
                elif (
                    result["indel"] / result["reads"] < min_pct / 100.0
                    or result["reads"] < min_reads
                ):
                    text_colour = wx.LIGHT_GREY
                elif any(peak["inframe"] for peak in result["peaks"]):
                    background_colour = wx.YELLOW
                else:
                    background_colour = wx.GREEN
            else:
                text_colour = wx.LIGHT_GREY

            self._output.SetItemBackgroundColour(row, background_colour)
            self._output.SetItemTextColour(row, text_colour)
            self._output.SetItemFont(row, text_font)

    def _get_selection(self) -> Optional[str]:
        targets = list(sorted(self._state.miseq))

        for index in self._targets.GetSelections():
            return targets[index]

        return None

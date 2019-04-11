#!/usr/bin/env python3
import wx

from typing import Any, List

from common import wx_bind, wx_find
from state import Clone, State


_COL_EXPORTED = 0
_COL_CLONE = 1
_COL_NUM_KOS = 2
_COL_KOS = 3
_COL_INDEX = 4
_COL_INDELS = 5
_COL_INDELS_PCT = 6
_COL_INDELS_PCT_TOTAL = 7
_COL_NUM_READS = 8
_COL_COMMENT = 9
_NUM_COLUMNS = 10


class StrRenderWithBorder(wx.grid.GridCellStringRenderer):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        wx.grid.GridCellStringRenderer.__init__(self, *args, **kwargs)

    def Draw(self, grid, attr, dc, rect, row, col, isSelected):
        wx.grid.GridCellStringRenderer.Draw(self, grid, attr, dc, rect, row, col, isSelected)

        dc.SetBrush(wx.TRANSPARENT_BRUSH)
        dc.SetPen(wx.Pen(wx.BLACK, 2, wx.SOLID))

        bottom = rect.y + rect.height
        dc.DrawLine(rect.x, bottom, rect.x + rect.width, bottom)


class ClonesWidget(object):
    def __init__(self, root: 'wx.App', state: State) -> None:
        self._root = root
        self._state = state
        self._clones = []  # type: List[Clone]

        self._sort_by_picked = wx_find('clones_sort_by_picked')
        self._show_picked = wx_find('clones_show_picked')
        self._groups = wx_find('clones_groups')

        self.grid = wx_find('clones_report')
        self.grid.CreateGrid(0, _NUM_COLUMNS)
        self.grid.EnableEditing(False)
        self.grid.HideRowLabels()

        for col, value in enumerate(('Export (Y/N)', 'Clone', '#KOs', 'KO',
                                     'Index', 'Indels', '%', 'Total%',
                                     '#Reads', 'Comments')):
            self.grid.SetColLabelValue(col, value)

        root.undo_buttons.append(wx.FindWindowByName('clones_button_undo'))
        root.redo_buttons.append(wx.FindWindowByName('clones_button_redo'))

        wx_bind('clones_groups', wx.EVT_LISTBOX, self.OnListBox)
        wx_bind('clones_report', wx.grid.EVT_GRID_CELL_LEFT_DCLICK,
                self.OnCellDoubleClick)

        wx_bind('clones_export_all', wx.EVT_BUTTON, self.OnExportAll)
        wx_bind('clones_export_everything', wx.EVT_BUTTON, self.OnExportEverything)
        wx_bind('clones_save', wx.EVT_BUTTON, root.save_state)
        wx_bind('clones_load', wx.EVT_BUTTON, root.load_state)
        wx_bind('clones_show_picked', wx.EVT_CHECKBOX, self.refresh_ui)
        wx_bind('clones_sort_by_picked', wx.EVT_CHECKBOX, self.refresh_ui)

        self.refresh_ui()

    def OnExportAll(self, _event: Any) -> None:
        print('ExportAll')
        self._state.export('exported.xlsx')
        print('Done')

    def OnExportEverything(self, _event: Any) -> None:
        print('ExportAll')
        self._state.export('exported.xlsx', everything=True)
        print('Done')

    def OnListBox(self, _event: Any) -> None:
        self.refresh_ui()

    def OnCellDoubleClick(self, event: Any) -> None:
        if self._clones:
            row = event.GetRow()

            result = None
            current_row = 0
            for clone in self._clones:
                knockouts = clone['knockouts']

                if current_row <= row < current_row + len(knockouts):
                    keys = sorted(knockouts)
                    key = keys[row - current_row]
                    result = clone['knockouts'][key]
                    break

                current_row += len(clone['knockouts'])

            if result is not None:
                if _COL_KOS <= event.GetCol() < _COL_COMMENT:
                    self._state.miseq_toggle_picked(result['target'],
                                                    result['index'])

                    self._root.refresh_ui()
                elif event.GetCol() == _COL_COMMENT:
                    dlg = wx.TextEntryDialog(self.grid,
                                             'Enter comment for knockout')

                    if dlg.ShowModal() == wx.ID_OK:
                        self._state.miseq_set_comment(result['target'],
                                                      result['index'],
                                                      dlg.GetValue())

                        self._root.refresh_ui()

    def refresh_ui(self, *_args: Any, **_kwargs: Any) -> None:
        groups = [k for k, _ in self._state.clones_groups()]
        ui_groups = [self._groups.GetString(idx)
                     for idx in range(self._groups.GetCount())]

        if groups != ui_groups:
            self._groups.Clear()
            if groups:
                self._groups.InsertItems(groups, 0)
                self._groups.SetSelection(0)

        group = None
        for idx in self._groups.GetSelections():
            group = self._groups.GetString(idx)

        if group is None:
            self._reset_grid(_NUM_COLUMNS, 0)
            return

        clones = self._state.clones_get_group(group)
        if self._show_picked.GetValue():
            clones = [clone for clone in clones if _picked_count(clone)]

        if self._sort_by_picked.GetValue():
            clones.sort(key=_picked_count_key)

        if clones != self._clones:
            n_rows = sum(max(1, len(clone['knockouts']))
                         for clone in clones)
            self._reset_grid(_NUM_COLUMNS, n_rows)

            row = 0
            for clone in clones:
                self._draw_clone(clone, row)

                row += max(1, len(clone['knockouts']))

            self._clones = clones

        for column in (_COL_KOS, _COL_INDELS, _COL_INDELS_PCT, _COL_COMMENT):
            self.grid.AutoSizeColumn(column)

    def _draw_clone(self, clone: Clone, row: int) -> None:
        if any(ko['picked'] for ko in clone['knockouts'].values() if ko):
            exported = 'Y'
        else:
            exported = 'N'

        self.grid.SetCellValue(row, _COL_EXPORTED, exported)
        self.grid.SetCellValue(row, _COL_CLONE, clone['label'])
        self.grid.SetCellValue(row, _COL_NUM_KOS, str(_picked_count(clone)))

        for idx, (label, knockout) in enumerate(sorted(clone['knockouts'].items())):
            self.grid.SetCellValue(row + idx, _COL_KOS, label)

            inframe = False
            if knockout:
                self.grid.SetCellValue(row + idx, _COL_INDEX, str(knockout['index']))

                indels = []
                indels_pct = []
                for peak in knockout['peaks']:
                    indels.append('%+i' % (peak['indel'],))
                    indels_pct.append('%i' % (peak['pct'] * 100,))
                    inframe = inframe or peak['inframe']

                self.grid.SetCellValue(row + idx, _COL_INDELS, ' / '.join(indels))
                self.grid.SetCellValue(row + idx, _COL_INDELS_PCT, ' / '.join(indels_pct))
                self.grid.SetCellValue(row + idx, _COL_INDELS_PCT_TOTAL,
                                       '%i' % (100 * (knockout['indel'] / knockout['reads']),))
                self.grid.SetCellValue(row + idx, _COL_NUM_READS, str(knockout['reads']))
                self.grid.SetCellValue(row + idx, _COL_COMMENT, knockout['comment'])
            else:
                self.grid.SetCellValue(row + idx, _COL_INDEX, '<NA>')

            if knockout and knockout['picked']:
                text_color = wx.BLACK
            else:
                text_color = wx.LIGHT_GREY
            bg_colour = wx.YELLOW if inframe else wx.WHITE

            for column in range(_COL_KOS, _NUM_COLUMNS):
                self.grid.SetCellTextColour(row + idx, column, text_color)
                self.grid.SetCellBackgroundColour(row + idx, column, bg_colour)

            for column in range(_NUM_COLUMNS):
                self.grid.SetCellRenderer(row + idx, column, wx.grid.GridCellStringRenderer())

        row += len(clone['knockouts']) - 1
        for column in range(_NUM_COLUMNS):
            self.grid.SetCellRenderer(row, column, StrRenderWithBorder())

    def _reset_grid(self, width: int, height: int) -> None:
        current_height = self.grid.GetNumberRows()
        if current_height > height:
            self.grid.DeleteRows(height, current_height, True)
        elif current_height < height:
            self.grid.AppendRows(height - current_height)

        # Prevent resizing of grids
        for row in range(height):
            self.grid.DisableRowResize(row)
        self.grid.ClearGrid()


def _picked_count_key(clone: Clone) -> int:
    picked = sorted(key for key, ko in clone['knockouts'].items()
                    if ko and ko['picked'])
    return (-len(picked), picked)


def _picked_count(clone: Clone) -> int:
    return -_picked_count_key(clone)[0]

#!/usr/bin/env python3
from typing import Any, Iterable, Tuple

import wx

from common import wx_bind
from state import State, SampleSheetError


class SampleSheetWidget(object):
    def __init__(self, root: 'wx.App', state: State) -> None:
        self._root = root
        self._state = state

        self.grid = wx.FindWindowByName('ss_grid')
        self.grid.CreateGrid(0, 0)
        self.grid.EnableEditing(False)
        self.grid.Bind(wx.grid.EVT_GRID_SELECT_CELL, self.OnGridSelectCell)

        for _, widget in self._get_radio_buttons():
            widget.Bind(wx.EVT_RADIOBUTTON, self.OnRadioButton)

        wx_bind('ss_load', wx.EVT_BUTTON, self.OnLoadButton)
        wx_bind('ss_add_verification', wx.EVT_BUTTON,
                lambda event: self.OnVerificationButton(event, True))
        wx_bind('ss_remove_verification', wx.EVT_BUTTON,
                lambda event: self.OnVerificationButton(event, False))

        root.undo_buttons.append(wx.FindWindowByName('ss_button_undo'))
        root.redo_buttons.append(wx.FindWindowByName('ss_button_redo'))

        self.refresh_ui()

    def OnVerificationButton(self, _event: Any, is_verification: bool) -> None:
        knockouts = self._state.samplesheet['knockouts']
        if self.grid.GridCursorCol >= len(knockouts):
            return

        group = knockouts[self.grid.GridCursorCol]['group']
        self._state.samplesheet_user_split(group, is_verification)

        self._root.refresh_ui()

    def OnGridSelectCell(self, event: Any) -> None:
        add_widget = wx.FindWindowByName('ss_add_verification')
        add_enabled = False

        rm_widget = wx.FindWindowByName('ss_remove_verification')
        rm_enabled = False

        if event.Selecting:
            knockouts = self._state.samplesheet['knockouts']
            if len(knockouts) > event.Col:
                knockout = knockouts[event.Col]

                if not any(knockout['split'].values()):
                    add_enabled = True
                elif knockout['split']['user']:
                    rm_enabled = True

        add_widget.Enable(add_enabled)
        rm_widget.Enable(rm_enabled)

    def OnRadioButton(self, event: Any) -> None:
        widget = wx.FindWindowById(event.Id)
        label = widget.GetName().split('_')[-1]

        if label != self._state.samplesheet['group_by']:
            self._state.samplesheet_group_by(label)

            self._root.refresh_ui()

    def OnLoadButton(self, _event: Any) -> None:
        with wx.FileDialog(self.grid, "Open SampleSheet",
                           wildcard="SampleSheet|*.xlsx",
                           style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST) as widget:

            if widget.ShowModal() != wx.ID_CANCEL:
                filename = widget.GetPath()

                try:
                    self._state.samplesheet_load(filename)
                except SampleSheetError as error:
                    wx.LogError(f'Could not open file "{filename}":\n{error}')

                self._root.refresh_ui()

    def refresh_ui(self) -> None:
        data = self._state.samplesheet
        knockouts = data['knockouts']

        self._reset_grid(data['width'], data['height'], len(data['headers']))
        for column, knockout in enumerate(knockouts):
            row = 0
            for key in data['headers']:
                header = knockout['headers'][key]

                if not column or header != knockouts[column - 1]['headers'][key]:
                    self.grid.SetCellValue(row, column, header)
                row += 1

            miseq = self._state.miseq.get(self._get_mapping(knockout))
            for idx, label in enumerate(knockout['column']):
                self.grid.SetCellAlignment(row + idx, column,
                                           wx.ALIGN_RIGHT,
                                           wx.ALIGN_CENTRE)

                if miseq is not None:
                    value = miseq.get(idx + 1, {}).get('reads', 0)
                    self.grid.SetCellValue(row + idx, column, str(value))
                    text_color = wx.BLACK if value or label else wx.LIGHT_GREY
                    self.grid.SetCellTextColour(row + idx, column, text_color)
                else:
                    self.grid.SetCellValue(row + idx, column, 'N/A')
                    self.grid.SetCellTextColour(row + idx, column, wx.RED)

        self._color_cells()

        for key, widget in self._get_radio_buttons():
            widget.Enable(key in data['headers'] or key == 'id')
            widget.SetValue(key == data['group_by'])

        self._reset_verification_list()

    def _get_radio_buttons(self) -> Iterable[Tuple[str, wx.RadioButton]]:
        for key in ('extraction', 'amplicon', 'id'):
            widget = wx.FindWindowByName(f'ss_group_by_{key}')
            if widget is not None:
                yield key, widget

    def _reset_verification_list(self) -> None:
        widget = wx.FindWindowByName('ss_verifications')
        widget.Clear()

        groups = set()
        data = self._state.samplesheet
        for knockout in data['knockouts']:
            for key, value in knockout['split'].items():
                if value:
                    groups.add(knockout['group'])

        for key in sorted(groups):
            widget.Append(key)

    def _reset_grid(self, width: int, height: int, n_headers: int) -> None:
        current_height = self.grid.GetNumberRows()
        if current_height > height:
            self.grid.DeleteRows(height, current_height, True)
        elif current_height < height:
            self.grid.AppendRows(height - current_height)

        current_width = self.grid.GetNumberCols()
        if current_width > width:
            self.grid.DeleteCols(width, current_width, True)
        elif current_width < width:
            self.grid.AppendCols(width - current_width)

        # Prevent resizing of grids
        for row in range(height):
            self.grid.DisableRowResize(row)

            label = '' if row < n_headers else str(row - n_headers + 1)
            self.grid.SetRowLabelValue(row, label)

    def _color_cells(self) -> None:
        reds = [wx.Colour(225, 161, 169), wx.Colour(255, 191, 199)]
        blues = [wx.Colour(135, 198, 215), wx.Colour(105, 168, 185)]
        greens = [wx.Colour(165, 198, 130), wx.Colour(195, 228, 160)]

        data = self._state.samplesheet
        row_offset = len(data['headers'])
        knockouts_row = group_by_row = len(data['headers']) - 1
        if data['group_by'] != 'id':
            group_by_row = data['headers'].index(data['group_by'])

        last_group = None
        for column, knockout in enumerate(data['knockouts']):
            is_verification = any(knockout['split'].values())
            if knockout['group'] != last_group or is_verification:
                reds, blues, greens = reds[::-1], blues[::-1], greens[::-1]
                last_group = knockout['group']

            for row in range(len(data['headers'])):
                self.grid.SetCellBackgroundColour(row, column, wx.WHITE)

            if is_verification or data['group_by'] == 'id':
                self.grid.SetCellBackgroundColour(knockouts_row, column, blues[0])
                clone_colour = blues[0]
            else:
                self.grid.SetCellBackgroundColour(group_by_row, column, greens[0])
                clone_colour = greens[0]

            default_colour = reds[0]
            for row, value in enumerate(knockout['column'], start=row_offset):
                self.grid.SetCellBackgroundColour(
                    row, column, clone_colour if value else default_colour)

    def _get_mapping(self, knockout):
        key = knockout['headers']['knockout']
        return self._state.ko_mapping.get(key)

#!/usr/bin/env python3
import argparse
import os
import sys

from pathlib import Path
from typing import Any, List, Optional

import wx
import wx.xrc

# Explicit import of wx.grid required to register widget for XRC
import wx.grid
import wx.propgrid

import ui
import state


class PropGridXMLHandler(wx.xrc.XmlResourceHandler):
    def CanHandle(self, node):
        return self.IsOfClass(node, "wxPropertyGridManager")

    def DoCreateResource(self):
        assert self.GetInstance() is None
        widget = wx.propgrid.PropertyGrid(
            self.GetParentAsWindow(),
            self.GetID(),
            self.GetPosition(),
            self.GetSize(),
            self.GetStyle(),
        )
        widget.SetName(self.GetName())
        self.SetupWindow(widget)
        return widget


class MyApp(wx.App):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        wx.App.__init__(self, *args, **kwargs)

    def OnInit(self) -> bool:
        resources = wx.xrc.XmlResource()
        resources.AddHandler(PropGridXMLHandler())

        xrc_filepath = os.path.join(os.path.dirname(__file__), "ui.xrc")
        resources.Load(xrc_filepath)

        self.frame = resources.LoadFrame(None, "frame")
        self.frame.SetInitialSize(wx.Size(1024, 768))
        self.frame.Show()

        self.state = state.State()
        self.undo_buttons = []  # type: List[Any]
        self.redo_buttons = []  # type: List[Any]
        self.samplesheet = ui.SampleSheetWidget(self, self.state)
        self.ko_mapping = ui.KOMappingWidget(self, self.state)
        self.miseq_output = ui.MiSeqOutputWidget(self, self.state)
        self.clones = ui.ClonesWidget(self, self.state)
        self.default_dir = ""

        for widget in self.undo_buttons:
            widget.Bind(wx.EVT_BUTTON, self.OnUndoButton)

        for widget in self.redo_buttons:
            widget.Bind(wx.EVT_BUTTON, self.OnRedoButton)

        self.frame.Bind(wx.EVT_CLOSE, self.OnClose)

        return True

    def OnClose(self, event: Any) -> None:
        if event.CanVeto() and not self.state.is_saved():
            if (
                wx.MessageBox(
                    "Unsaved changes exist, close program anyway?",
                    "Please confirm",
                    wx.ICON_QUESTION | wx.YES_NO,
                )
                != wx.YES
            ):
                event.Veto()
                return

        event.Skip()

    def refresh_ui(self, child: Optional[object] = None) -> None:
        children = [
            self.samplesheet,
            self.ko_mapping,
            self.miseq_output,
            self.clones,
        ]

        for widget in children:
            if child in (None, widget):
                widget.refresh_ui()

        if child is self.ko_mapping:
            self.samplesheet.refresh_ui()

        history_buttons = (
            ("Undo", self.undo_buttons, self.state.undo_count),
            ("Redo", self.redo_buttons, self.state.redo_count),
        )

        for text, widgets, count in history_buttons:
            for widget in widgets:
                widget.Enable(bool(count))
                widget.SetLabel(f"{text} ({count})" if count else text)

    def load_miseq_output(self) -> None:
        with wx.FileDialog(
            self.frame,
            "Open Hamplicon Output",
            wildcard="Hamplicons|*.xlsx;*.json",
            style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST,
            defaultDir=self.default_dir,
        ) as widget:

            if widget.ShowModal() != wx.ID_CANCEL:
                filename = widget.GetPath()
                self.default_dir = os.path.dirname(filename)

                try:
                    self.state.miseq_load(filename)
                except state.MiSeqOutputError as error:
                    wx.LogError(f'Could not open file "{filename}":\n{error}')

                self.refresh_ui()

    def load_state(self, *_args: Any, **_kwargs: Any) -> None:
        with wx.FileDialog(
            self.frame,
            "Open project",
            wildcard="Project|*.core",
            style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST,
            defaultDir=self.default_dir,
        ) as widget:
            if widget.ShowModal() != wx.ID_CANCEL:
                filename = widget.GetPath()
                self.default_dir = os.path.dirname(filename)

                try:
                    self.state.load_state(filename)
                except Exception as error:
                    wx.LogError(f'Could not open file "{filename}":\n{error}')
                    raise

                self.refresh_ui()

    def save_state(self, *_args: Any, **_kwargs: Any) -> None:
        with wx.FileDialog(
            self.frame,
            "Save project",
            wildcard="Project|*.core",
            style=wx.FD_SAVE,
            defaultDir=self.default_dir,
        ) as widget:
            if widget.ShowModal() != wx.ID_CANCEL:
                filename = widget.GetPath()
                self.default_dir = os.path.dirname(filename)

                try:
                    self.state.save_state(filename)
                except Exception as error:
                    wx.LogError(f'Could not open file "{filename}":\n{error}')
                    raise

    def OnUndoButton(self, _event: Any) -> None:
        self.state.undo()
        self.refresh_ui()

    def OnRedoButton(self, _event: Any) -> None:
        self.state.redo()
        self.refresh_ui()


class HelpFormatter(argparse.ArgumentDefaultsHelpFormatter):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("width", 79)

        super().__init__(*args, **kwargs)


def parse_args(argv):
    parser = argparse.ArgumentParser(formatter_class=HelpFormatter)
    parser.add_argument("--pooling-xlsx", type=Path)
    parser.add_argument("--hamplicons-xlsx", type=Path)
    parser.add_argument("--state-core", type=Path)

    return parser.parse_args(argv)


def main(argv: List[str]) -> int:
    args = parse_args(argv)
    app = MyApp(False)

    if args.pooling_xlsx:
        app.state.samplesheet_load(args.pooling_xlsx)

    if args.hamplicons_xlsx:
        app.state.miseq_load(args.hamplicons_xlsx)

    if args.state_core:
        app.state.load_state(args.state_core)

    app.refresh_ui()

    return app.MainLoop()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

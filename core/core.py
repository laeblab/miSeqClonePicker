from typing import Any, List, Optional
from mypy_extensions import TypedDict

from .samplesheet import SampleSheet


_Snapshot = TypedDict(
    "_Snapshot",
    {
        "_sheet": SampleSheet,
    },
)

_History = List[_Snapshot]


class Core:
    __slots__ = [
        "_undo_history",
        "_redo_history",
        "_sheet",
    ]

    def __init__(self) -> None:
        self._undo_history = []  # type: _History
        self._redo_history = []  # type: _History
        self._sheet = SampleSheet()

    def undo(self) -> None:
        """Undoes the last action; does nothing if no undo'able actions have
        been taken by the user.
        """
        raise NotImplementedError()

    def undo_count(self) -> int:
        """Returns the number of undo'able actions."""
        return len(self._redo_history)

    def redo(self) -> None:
        """Reodoes the last action; does nothing if no actions have been undone
        by the user since the last regular action.
        """
        raise NotImplementedError()

    def redo_count(self) -> int:
        """Returns the number of redo'able actions, corresponding to the number
        of actions undone by the user since the last regular action."""
        return len(self._redo_history)

    def load(self, filename: str) -> None:
        raise NotImplementedError()

    def save(self, filename: str) -> None:
        raise NotImplementedError()

    def import_samplesheet(self, filename: str) -> None:
        with self._create_snapshot():
            self._sheet = SampleSheet.load(filename)

    def import_miseq_table(self, filename: str) -> None:
        raise NotImplementedError()

    def export_report(self, filename: str) -> None:
        raise NotImplementedError()

    def _create_snapshot(self) -> "_CreateSnapshot":
        return _CreateSnapshot(self)


class _CreateSnapshot:
    __slots__ = [
        "_core",
        "_snapshot",
    ]

    def __init__(self, core: Core) -> None:
        self._core = core
        self._snapshot = None  # type: Optional[_Snapshot]

    def __enter__(self) -> "_CreateSnapshot":
        self._snapshot = {
            "_sheet": self._core._sheet,
        }

        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        if exc_type is None and self._snapshot is not None:
            self._core._undo_history.append(self._snapshot)
            self._core._redo_history.clear()

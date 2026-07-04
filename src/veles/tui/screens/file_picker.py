"""M78: pick a project file to reference from the Composer via `@`.

Lists files under the project root via `cli.repl.file_index.iter_project_files`
(excludes `.git`, `node_modules`, etc.; keeps `.veles/tmp/` so
clipboard-paste artifacts are reachable). Returns the chosen relative
path as a POSIX-style string ready to drop into the prompt; `None` on
cancel."""

from __future__ import annotations

from pathlib import Path

from veles.cli.repl.file_index import iter_project_files
from veles.tui.screens.base_picker import PickerItem, PickerScreen


class FilePickerScreen(PickerScreen[str]):
    """Returns the picked relative path. `None` on cancel."""

    def __init__(self, root: Path, *, initial_filter: str = "") -> None:
        self._root = root
        items = self._build_items()
        super().__init__(
            title="Pick a file to reference (Esc to cancel)",
            items=items,
            empty_message="no matching files",
            placeholder="filter by name / path…",
        )
        self._initial_filter = initial_filter

    def on_mount(self) -> None:
        super().on_mount()
        if self._initial_filter:
            from textual.widgets import Input

            inp = self.query_one("#veles-picker-filter", Input)
            inp.value = self._initial_filter

    def _build_items(self) -> list[PickerItem[str]]:
        items: list[PickerItem[str]] = []
        for rel in iter_project_files(self._root):
            posix = rel.as_posix()
            items.append(PickerItem(label=posix, haystack=posix, value=posix))
        return items

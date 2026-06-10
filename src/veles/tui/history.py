"""Persistent input history for the Composer.

JSON-Lines format: one entry per line, `{"text": "..."}`. Plain JSON keeps
the door open for adding metadata (timestamp, model) later without
breaking older readers — they'll still find the `text` field.

History persists at `~/.veles/tui_history.jsonl`. The legacy TUI used
`~/.veles/tui_history` (plain text); we ship a separate file rather than
migrating in place so a user who keeps both TUIs around doesn't get
their legacy file rewritten with the new schema.

Navigation has a draft anchor: the moment the user first presses Up,
the current composer text is captured so pressing Down past the most
recent entry restores it. This is the bash/zsh behaviour shells users
expect.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path


def default_history_path() -> Path:
    from veles.core.user_paths import user_home

    return user_home() / "tui_history.jsonl"


@dataclass(slots=True)
class InputHistory:
    path: Path
    items: list[str] = field(default_factory=list)
    _draft: str = ""
    _index: int | None = None  # cursor *into* items; None == not navigating

    # ---- load / save ----

    @classmethod
    def load(cls, path: Path | None = None) -> InputHistory:
        path = path or default_history_path()
        items: list[str] = []
        if path.is_file():
            try:
                for raw in path.read_text(encoding="utf-8").splitlines():
                    raw = raw.rstrip()
                    if not raw:
                        continue
                    try:
                        entry = json.loads(raw)
                        text = entry.get("text") if isinstance(entry, dict) else None
                    except json.JSONDecodeError:
                        text = raw  # tolerate legacy plain-text rows
                    if text:
                        items.append(text)
            except OSError:
                pass
        return cls(path=path, items=items)

    def append(self, text: str) -> None:
        text = text.strip()
        if not text:
            return
        # Skip immediate dupes — they bloat the file and clutter Up navigation.
        if self.items and self.items[-1] == text:
            self.reset()
            return
        self.items.append(text)
        self.reset()
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as f:
                f.write(json.dumps({"text": text}, ensure_ascii=False) + "\n")
        except OSError:
            # Best-effort: a broken disk shouldn't kill the TUI session.
            pass

    # ---- navigation ----

    def start_navigation(self, draft: str) -> None:
        """Snapshot the current draft so the first Up arrow remembers
        what to restore when we walk back past the newest entry."""
        if self._index is None:
            self._draft = draft

    @property
    def navigating(self) -> bool:
        return self._index is not None

    def previous(self) -> str | None:
        if not self.items:
            return None
        if self._index is None:
            # Step onto the most recent entry.
            self._index = len(self.items) - 1
            return self.items[self._index]
        if self._index > 0:
            self._index -= 1
            return self.items[self._index]
        return None  # already at the oldest; stay put

    def next(self) -> str | None:
        if self._index is None:
            return None
        if self._index < len(self.items) - 1:
            self._index += 1
            return self.items[self._index]
        # Stepped past the most recent entry → restore the saved draft.
        self._index = None
        return self._draft

    def reset(self) -> None:
        self._index = None
        self._draft = ""

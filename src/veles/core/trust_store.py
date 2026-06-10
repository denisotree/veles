"""Persisted trust grants for sensitive tool dispatch (M38).

A JSON document at `<project>/.veles/trust.json` (project scope) and
`~/.veles/trust.json` (user scope) records which tool names the user has
granted standing permission for. M38's evaluator (`core/trust.py`)
treats either scope as sufficient: if a tool is listed in *either* file,
no prompt is raised and dispatch proceeds. Absence of both falls back
to the interactive 4-option prompt — or refusal in non-TTY contexts.

Schema (identical for project and user files):

    {
        "tools": {
            "run_shell": {"granted_at": "2026-05-10T18:00:00Z"},
            "write_file": {"granted_at": "2026-05-10T18:01:00Z"}
        }
    }

Concurrent writers are serialised via `file_lock` on a sidecar
`trust.json.lock` so MCP-child grants don't collide with parent prompts.
File loads are permissive — corrupt JSON / missing keys / wrong types
all degrade to an empty store rather than crashing the run.
"""

from __future__ import annotations

import datetime as _dt
import json
import os
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from veles.core.file_lock import file_lock

_TRUST_FILENAME = "trust.json"


@dataclass(slots=True)
class TrustStore:
    path: Path
    tools: dict[str, str] = field(default_factory=dict)

    @classmethod
    def load(cls, path: Path) -> TrustStore:
        if not path.is_file():
            return cls(path=path)
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return cls(path=path)
        if not isinstance(data, dict):
            return cls(path=path)
        tools_raw = data.get("tools")
        if not isinstance(tools_raw, dict):
            return cls(path=path)
        tools: dict[str, str] = {}
        for name, entry in tools_raw.items():
            if not isinstance(name, str):
                continue
            if isinstance(entry, dict) and isinstance(entry.get("granted_at"), str):
                tools[name] = entry["granted_at"]
        return cls(path=path, tools=tools)

    def is_granted(self, tool_name: str) -> bool:
        return tool_name in self.tools

    def grant(self, tool_name: str) -> None:
        self.tools[tool_name] = _utc_now_iso()
        self._save()

    def revoke(self, tool_name: str) -> bool:
        if self.tools.pop(tool_name, None) is None:
            return False
        self._save()
        return True

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        body = {"tools": {name: {"granted_at": at} for name, at in sorted(self.tools.items())}}
        text = json.dumps(body, indent=2, ensure_ascii=False) + "\n"
        lock_path = self.path.parent / (self.path.name + ".lock")
        with file_lock(lock_path):
            fd, tmp_name = tempfile.mkstemp(
                prefix=self.path.name + ".", suffix=".tmp", dir=self.path.parent
            )
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as fh:
                    fh.write(text)
                os.replace(tmp_name, self.path)
            except Exception:
                Path(tmp_name).unlink(missing_ok=True)
                raise


def user_trust_path() -> Path:
    """Path to the user-scope trust file. `VELES_USER_HOME` overrides `~/`."""
    from veles.core.user_paths import user_home

    return user_home() / _TRUST_FILENAME


def _utc_now_iso() -> str:
    return _dt.datetime.now(_dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")

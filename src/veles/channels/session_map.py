"""SessionMap — `external chat_id → veles session_id` JSON-backed store.

Each channel keeps its own file at
`~/.veles/channels/<channel>-sessions.json` so a user's conversation
stays continuous across channel-process restarts and daemon restarts.
Mapping is `{external_chat_id: {session_id, last_used_at}}`.

Permissive load, atomic save (tempfile + `os.replace`). No file lock —
each channel process owns its own file; concurrent writes from a
sibling process would imply two channel instances for the same channel,
which is unsupported.

M74 extension: `SessionSource` dataclass captures richer chat context
(platform, chat_id, user_id, thread_id, guild_id) and produces a
deterministic string key via `.key()`. The string-keyed SessionMap is
unchanged — gateways that want thread/guild awareness build the key
through SessionSource. M52 flat-string usage continues to work.
"""

from __future__ import annotations

import json
import os
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(slots=True, frozen=True)
class SessionSource:
    """Rich identity of an inbound chat surface.

    `platform` is the channel name as registered in the platform registry
    (`"telegram"`, `"slack"`, …). `chat_id` is the per-platform conversation
    identifier (Telegram chat_id, Slack channel id). `user_id` is the sender
    (may equal chat_id in DMs). `thread_id` and `guild_id` are channel-specific
    nesting — Slack threads, Discord guild/thread combos. `message_id` is the
    inbound message id when available; some channels need it for edit-based
    replies.

    `.key()` is the deterministic string SessionMap stores. Including
    thread_id keeps threads as separate sessions (a Slack thread becomes its
    own Veles session). guild_id is informational only — Discord channel ids
    are already globally unique.
    """

    platform: str
    chat_id: str
    user_id: str | None = None
    thread_id: str | None = None
    guild_id: str | None = None
    message_id: str | None = None

    def key(self) -> str:
        if self.thread_id:
            return f"{self.platform}:{self.chat_id}:{self.thread_id}"
        return f"{self.platform}:{self.chat_id}"

    def label(self) -> str:
        """Human-readable identifier for logs / mirror headers."""
        return self.key()


def _default_channels_dir() -> Path:
    from veles.core.user_paths import user_home

    return user_home() / "channels"


def channel_session_path(channel: str, *, base_dir: Path | None = None) -> Path:
    target = base_dir or _default_channels_dir()
    return target / f"{channel}-sessions.json"


@dataclass(slots=True)
class SessionMap:
    path: Path
    entries: dict[str, dict[str, object]] = field(default_factory=dict)

    @classmethod
    def load(cls, path: Path) -> SessionMap:
        m = cls(path=path, entries={})
        if not path.is_file():
            return m
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return m
        if not isinstance(data, dict):
            return m
        raw = data.get("sessions")
        if not isinstance(raw, dict):
            return m
        for key, value in raw.items():
            if not isinstance(key, str) or not isinstance(value, dict):
                continue
            sid = value.get("session_id")
            if not isinstance(sid, str):
                continue
            last = value.get("last_used_at")
            ts = float(last) if isinstance(last, int | float) else time.time()
            m.entries[key] = {"session_id": sid, "last_used_at": ts}
        return m

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"sessions": self.entries}
        text = json.dumps(payload, indent=2, sort_keys=True) + "\n"
        fd, tmp = tempfile.mkstemp(prefix=self.path.name + ".", suffix=".tmp", dir=self.path.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                fh.write(text)
            os.replace(tmp, self.path)
        except Exception:
            Path(tmp).unlink(missing_ok=True)
            raise

    def get(self, chat_id: str) -> str | None:
        entry = self.entries.get(chat_id)
        if not entry:
            return None
        sid = entry.get("session_id")
        return sid if isinstance(sid, str) else None

    def set(self, chat_id: str, session_id: str) -> None:
        self.entries[chat_id] = {"session_id": session_id, "last_used_at": time.time()}
        self.save()

    def reset(self, chat_id: str) -> bool:
        if chat_id not in self.entries:
            return False
        del self.entries[chat_id]
        self.save()
        return True

    def list(self) -> list[tuple[str, str, float]]:
        out: list[tuple[str, str, float]] = []
        for key, value in self.entries.items():
            sid = value.get("session_id")
            last = value.get("last_used_at")
            if isinstance(sid, str) and isinstance(last, int | float):
                out.append((key, sid, float(last)))
        out.sort(key=lambda row: -row[2])
        return out

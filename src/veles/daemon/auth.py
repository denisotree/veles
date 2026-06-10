"""Daemon auth (M51) — bearer-token store + aiohttp middleware.

Tokens live at `~/.veles/daemon.tokens.json` (mode 0600) under a single
top-level `tokens` list of `{name, token, created_at}` entries. Token
strings are `vd_<32 hex>`; the `vd_` prefix is for grep-ability and to
namespace from other tokens a user might keep alongside.

The middleware blocks every request except `/v1/health` unless the
`Authorization: Bearer <token>` header verifies against the store. The
store is reloaded on each verify call so `veles daemon token add` from
another shell propagates without a daemon restart.
"""

from __future__ import annotations

import contextlib
import json
import os
import secrets
import tempfile
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from pathlib import Path

from aiohttp import web

Handler = Callable[[web.Request], Awaitable[web.StreamResponse]]

_TOKEN_PREFIX = "vd_"
_TOKEN_BYTES = 16


def _default_tokens_path() -> Path:
    from veles.core.user_paths import user_home

    return user_home() / "daemon.tokens.json"


@dataclass(slots=True, frozen=True)
class TokenEntry:
    name: str
    token: str
    created_at: float


@dataclass(slots=True)
class TokenStore:
    path: Path
    entries: list[TokenEntry] = field(default_factory=list)

    @classmethod
    def load(cls, path: Path | None = None) -> TokenStore:
        target = path or _default_tokens_path()
        store = cls(path=target, entries=[])
        if not target.is_file():
            return store
        try:
            data = json.loads(target.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return store
        tokens_raw = data.get("tokens") if isinstance(data, dict) else None
        if not isinstance(tokens_raw, list):
            return store
        for raw in tokens_raw:
            if not isinstance(raw, dict):
                continue
            name = raw.get("name")
            tok = raw.get("token")
            created_at = raw.get("created_at")
            if not isinstance(name, str) or not isinstance(tok, str):
                continue
            ts = float(created_at) if isinstance(created_at, int | float) else time.time()
            store.entries.append(TokenEntry(name=name, token=tok, created_at=ts))
        return store

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "tokens": [
                {"name": e.name, "token": e.token, "created_at": e.created_at} for e in self.entries
            ]
        }
        text = json.dumps(payload, indent=2, sort_keys=True) + "\n"
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
        with contextlib.suppress(OSError):
            os.chmod(self.path, 0o600)

    def add(self, name: str) -> TokenEntry:
        if any(e.name == name for e in self.entries):
            raise ValueError(f"token name {name!r} already exists")
        entry = TokenEntry(
            name=name,
            token=_TOKEN_PREFIX + secrets.token_hex(_TOKEN_BYTES),
            created_at=time.time(),
        )
        self.entries.append(entry)
        self.save()
        return entry

    def remove(self, name: str) -> bool:
        before = len(self.entries)
        self.entries = [e for e in self.entries if e.name != name]
        if len(self.entries) == before:
            return False
        self.save()
        return True

    def verify(self, token: str) -> str | None:
        """Return the entry name for `token`, or None if invalid."""
        for e in self.entries:
            if secrets.compare_digest(e.token, token):
                return e.name
        return None

    def list(self) -> list[TokenEntry]:
        return list(self.entries)


@web.middleware
async def bearer_auth_middleware(request: web.Request, handler: Handler) -> web.StreamResponse:
    """Reject any request without a valid bearer token, except `/v1/health`.

    The token store is looked up under `request.app["token_store"]`. It is
    re-read from disk on each call so token CRUD from a sibling shell
    propagates without restarting the daemon.
    """
    if request.path == "/v1/health":
        return await handler(request)
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return web.json_response({"error": "missing bearer token"}, status=401)
    token = auth_header[len("Bearer ") :].strip()
    if not token:
        return web.json_response({"error": "missing bearer token"}, status=401)
    store: TokenStore = request.app["token_store"]
    fresh = TokenStore.load(store.path)
    if fresh.verify(token) is None:
        return web.json_response({"error": "invalid token"}, status=401)
    return await handler(request)

"""Human approval for project MCP servers (stage 1b).

A `[mcp.servers.<name>]` entry names a command Veles spawns. A cloned project
(or a config edited behind the user's back) must not get that command run just by
opening it, so a server connects only when the SHA-256 of its **raw** recipe — the
table as written in `config.toml`, before `${VAR}` interpolation — matches the hash
the user approved. Secret values from the environment are therefore neither hashed
nor stored, and rotating a token does not revoke the approval; editing the recipe
(command, args, env, url, transport, …) does.

The store lives at `~/.veles/mcp-approvals.json`, outside the agent sandbox, keyed
by absolute project root then server name. Only `veles mcp approve` and a registry
install (which already passed `confirm_critical`) record an approval. A corrupt
store approves nothing.
"""

from __future__ import annotations

import hashlib
import json
import logging
from contextlib import AbstractContextManager
from pathlib import Path
from typing import Any, Literal

from veles.core.file_lock import file_lock
from veles.core.io_utils import atomic_write_json, load_optional_json
from veles.core.text import shown
from veles.core.user_paths import user_home
from veles.mcp.config import McpServerConfig

logger = logging.getLogger(__name__)

ApprovalState = Literal["yes", "no", "changed"]

# (project root, server name) already warned about in this process.
_warned: set[tuple[str, str]] = set()


def store_path() -> Path:
    """`~/.veles/mcp-approvals.json` — outside the agent write sandbox."""
    return user_home() / "mcp-approvals.json"


def recipe_hash(raw: dict[str, Any]) -> str:
    """SHA-256 of the canonical JSON of a raw recipe (keys sorted). Also the
    registry's install digest for an mcp extension — keep the encoding stable."""
    return hashlib.sha256(json.dumps(raw, sort_keys=True, default=str).encode()).hexdigest()


def describe_recipe(name: str, raw: dict[str, Any]) -> str:
    """The whole raw recipe as the user must review it before approving: every key
    (env values included — `PATH` decides which binary runs; `${VAR}` references
    appear verbatim), escaped because the config is untrusted, plus the short hash."""
    lines = [f"  MCP server {shown(name)}:"]
    for key in sorted(raw):
        value = json.dumps(raw[key], ensure_ascii=False, sort_keys=True, default=str)
        lines.append(f"    {shown(key)} = {shown(value)}")
    lines.append(f"    recipe sha256 {recipe_hash(raw)[:12]}")
    lines.append("  Approving lets Veles start this command whenever the project is opened.")
    return "\n".join(lines)


def _key(project_root: Path) -> str:
    return str(Path(project_root).resolve())


def _load() -> dict[str, Any]:
    data = load_optional_json(store_path(), default={})
    return data if isinstance(data, dict) else {}


def approval_state(project_root: Path, name: str, raw: dict[str, Any]) -> ApprovalState:
    """`yes` when `raw` matches the approved hash, `changed` when a different
    recipe was approved, `no` when nothing (readable) was."""
    entry = _load().get(_key(project_root))
    recorded = entry.get(name) if isinstance(entry, dict) else None
    if not isinstance(recorded, str):
        return "no"
    return "yes" if recorded == recipe_hash(raw) else "changed"


def _locked() -> AbstractContextManager[None]:
    """One writer at a time: `veles mcp approve` and a registry install can race."""
    path = store_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    return file_lock(path.parent / (path.name + ".lock"))


def approve(project_root: Path, name: str, raw: dict[str, Any]) -> str:
    """Record `raw` as the approved recipe for `name`. Returns the hash."""
    digest = recipe_hash(raw)
    with _locked():
        data = _load()
        entry = data.get(_key(project_root))
        if not isinstance(entry, dict):
            entry = data[_key(project_root)] = {}
        entry[name] = digest
        atomic_write_json(store_path(), data)
    return digest


def revoke(project_root: Path, name: str) -> None:
    with _locked():
        data = _load()
        entry = data.get(_key(project_root))
        if isinstance(entry, dict) and entry.pop(name, None) is not None:
            if not entry:
                del data[_key(project_root)]
            atomic_write_json(store_path(), data)


def only_approved(
    project_root: Path, configs: dict[str, McpServerConfig], raw: dict[str, Any]
) -> dict[str, McpServerConfig]:
    """The enabled servers of `configs` whose raw recipe is approved. Each other
    enabled server is warned about once per process. `configs` must be parsed
    from the same `raw` read, so what was checked is what gets spawned."""
    out: dict[str, McpServerConfig] = {}
    for name, cfg in configs.items():
        if not cfg.enabled:
            continue
        if approval_state(project_root, name, raw[name]) == "yes":
            out[name] = cfg
            continue
        key = (_key(project_root), name)
        if key not in _warned:
            _warned.add(key)
            logger.warning(
                "MCP server %s is not approved (or changed since approval) — review it, "
                "then `veles mcp approve %s`",
                shown(name),
                shown(name),
            )
    return out


__all__ = [
    "ApprovalState",
    "approval_state",
    "approve",
    "describe_recipe",
    "only_approved",
    "recipe_hash",
    "revoke",
    "store_path",
]

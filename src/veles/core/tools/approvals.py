"""M199 — human-approved SHA-256 hashes for self-authored tool files.

Self-authored tools (`<project>/.veles/tools/*.py`, `~/.veles/tools/*.py`) run
their module-level code the moment the loader imports them. The loader refuses
to `exec_module` a file whose current SHA-256 isn't recorded here, so code an
injection-steered agent drops into `.veles/tools/` never runs unattended.

**Security invariant — the store location is the whole property.** The store
lives at `~/.veles/tool-approvals.json`, which sits OUTSIDE the agent-writable
sandbox: `path_guard` admits only `~/.veles/{skills,locales}` for the agent's
`write_file`. So the same `write_file` that could drop `evil.py` cannot also drop
an approval for it — only `veles tool approve` records a hash: at a terminal, or
headless with `--sha256` (the hash a human reviewed). `--yes` needs a terminal,
which an agent's `run_shell` has not. A granted `run_shell` is still a shell and
could write this store directly; only an OS sandbox around `run_shell` closes that.
Co-locating the approval with the tool would let the agent self-approve; do not
move it into a project.

Known gaps (documented, not closed by M199): a sibling `_helper.py` imported by
an approved tool is not itself hashed (loader skips `_`-prefixed files); and the
call-time `risk_class=None → allow` floor is unchanged (see the milestone note).
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from veles.core.critical_ops import refuse_in_agent_shell
from veles.core.io_utils import atomic_write_json, load_optional_json
from veles.core.user_paths import user_home


def store_path() -> Path:
    """`~/.veles/tool-approvals.json` — outside the agent write sandbox."""
    return user_home() / "tool-approvals.json"


def file_sha256(path: Path) -> str:
    """SHA-256 of the file's bytes, or '' when unreadable."""
    try:
        return hashlib.sha256(Path(path).read_bytes()).hexdigest()
    except OSError:
        return ""


def _load() -> dict[str, str]:
    data = load_optional_json(store_path(), default={})
    return data if isinstance(data, dict) else {}


def _key(path: Path) -> str:
    return str(Path(path).resolve())


def is_approved(path: Path) -> bool:
    """True iff `path`'s current bytes match a recorded approval. A new or
    edited file is not approved — the loader must not run it."""
    sha = file_sha256(path)
    if not sha:
        return False
    return _load().get(_key(path)) == sha


def approve(path: Path, *, expected_sha256: str | None = None) -> str:
    """Record `path`'s current SHA-256 as human-approved. Returns the hash.
    `expected_sha256` is the hash the human reviewed: a file changed since is
    refused (ValueError). Called by `veles tool approve` — never by the agent."""
    refuse_in_agent_shell(f"approving {path.name}")
    sha = file_sha256(path)
    if not sha:
        raise FileNotFoundError(path)
    if expected_sha256 is not None and sha != expected_sha256:
        raise ValueError(f"{path.name} changed since the hash you reviewed (it is now {sha})")
    data = _load()
    data[_key(path)] = sha
    atomic_write_json(store_path(), data)
    return sha

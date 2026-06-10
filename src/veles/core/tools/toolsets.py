"""Toolset composition (Tier δ, M57).

Toolsets are named lists of tool names that the CLI hands to the agent via
`Registry.subset(...)`. Before M57 they lived as inline tuples in
`cli/_runtime.py`. Now they live in `core/tools/toolsets.toml` with an
`includes` mechanism so a derived toolset can pull from a base without
copy-paste. The legacy tuples re-export from here so existing call sites
keep working.

Loader rules:
  - Each section is `[<name>] tools=[...] includes=[<other>...]`.
  - `includes` is resolved transitively; cycles raise ValueError.
  - Duplicate tool names across includes are deduplicated; later additions
    win when ordering matters (only for trace stability, not behaviour).
"""

from __future__ import annotations

import tomllib
from collections.abc import Mapping
from pathlib import Path

_BUILTIN_TOML = Path(__file__).with_name("toolsets.toml")


def load_toolsets(path: Path | None = None) -> dict[str, tuple[str, ...]]:
    """Read a toolsets.toml file and return `name -> tuple[tool_name, ...]`.

    `path=None` loads the bundled `core/tools/toolsets.toml`. Caller-supplied
    paths let user/project overrides plug in later via the same loader.
    """
    src = path or _BUILTIN_TOML
    with src.open("rb") as f:
        raw: Mapping[str, Mapping[str, object]] = tomllib.load(f)
    out: dict[str, tuple[str, ...]] = {}
    for name in raw:
        out[name] = _resolve(name, raw, seen=set())
    return out


def _resolve(
    name: str,
    raw: Mapping[str, Mapping[str, object]],
    *,
    seen: set[str],
) -> tuple[str, ...]:
    if name in seen:
        raise ValueError(f"cycle in toolset includes: {' -> '.join(sorted(seen))} -> {name}")
    if name not in raw:
        raise KeyError(f"unknown toolset {name!r}")
    section = raw[name]
    out: list[str] = []
    seen2 = {*seen, name}
    includes_raw = section.get("includes") or []
    tools_raw = section.get("tools") or []
    if not isinstance(includes_raw, list) or not isinstance(tools_raw, list):
        raise ValueError(f"toolset {name!r}: includes/tools must be lists")
    for inc in includes_raw:
        for t in _resolve(str(inc), raw, seen=seen2):
            if t not in out:
                out.append(t)
    for t in tools_raw:
        ts = str(t)
        if ts not in out:
            out.append(ts)
    return tuple(out)


# Cached at import time; toolsets.toml is shipped with the wheel and never
# mutates at runtime. Re-export the canonical names so `cli/_runtime.py`'s
# legacy `_RUN_TOOLS` (etc.) can shed its inline tuples without changing
# any import paths.
TOOLSETS: dict[str, tuple[str, ...]] = load_toolsets()

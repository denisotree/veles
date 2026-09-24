"""CI invariant: each layer imports only what sits below it — lazy imports too.

    core      < runtime < cli, daemon, tui
    core      < adapters, channels, mcp, modules

`test_core_import_isolation.py` keeps core's *top-level* imports clean; this
lock covers every import, including the function-local ones that let a layer
quietly reach upward only when a code path runs. `core` importing `adapters`
(the provider factory) and `modules` (the plugin registries) is by design and
not a rule here.

`_KNOWN` lists the deliberate exceptions. It may shrink, never grow, and every
entry must still be a real import (a stale entry fails too).
"""

from __future__ import annotations

import ast
from pathlib import Path

_SRC = Path(__file__).resolve().parent.parent / "src"

# layer → the layers it must not import.
_RULES: dict[str, tuple[str, ...]] = {
    "veles.core": ("veles.cli", "veles.daemon", "veles.channels", "veles.tui", "veles.runtime"),
    "veles.adapters": ("veles.cli", "veles.daemon", "veles.channels", "veles.tui", "veles.runtime"),
    "veles.mcp": ("veles.cli", "veles.daemon", "veles.channels", "veles.tui", "veles.runtime"),
    "veles.runtime": ("veles.cli", "veles.daemon", "veles.channels", "veles.tui"),
    "veles.modules": ("veles.cli", "veles.daemon", "veles.tui"),
    "veles.channels": ("veles.cli", "veles.daemon", "veles.tui"),
    "veles.daemon": ("veles.cli", "veles.tui"),
}

_KNOWN: frozenset[tuple[str, str]] = frozenset(
    {
        # Self-knowledge: describes the CLI surface by walking its parser.
        ("veles.core.knowledge.skeleton", "veles.cli._parsers"),
        # Config validation knows which keys each registered channel accepts.
        ("veles.core.config_schema", "veles.channels.platform_registry"),
        # "Last active chat" is read from the channels' session maps.
        ("veles.core.proactive.target_resolver", "veles.channels.session_map"),
    }
)


def _module(path: Path) -> str:
    return ".".join(path.relative_to(_SRC).with_suffix("").parts)


def _resolve(module: str | None, level: int, importer: str) -> str:
    if level == 0:
        return module or ""
    base = importer.split(".")[:-1]
    base = base[: len(base) - (level - 1)]
    return ".".join([*base, module] if module else base)


def _in(name: str, package: str) -> bool:
    return name == package or name.startswith(package + ".")


def _violations() -> set[tuple[str, str]]:
    found: set[tuple[str, str]] = set()
    for path in _SRC.rglob("*.py"):
        importer = _module(path)
        layer = next((lay for lay in _RULES if _in(importer, lay)), None)
        if layer is None:
            continue
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Import):
                targets = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                targets = [_resolve(node.module, node.level, importer)]
            else:
                continue
            for target in targets:
                if any(_in(target, banned) for banned in _RULES[layer]):
                    found.add((importer, target))
    return found


def test_no_upward_imports() -> None:
    new = sorted(_violations() - _KNOWN)
    assert not new, "Imports that reach up a layer:\n" + "\n".join(f"  {a} -> {b}" for a, b in new)


def test_known_exceptions_still_exist() -> None:
    stale = sorted(_KNOWN - _violations())
    assert not stale, f"Remove these from _KNOWN, they no longer happen: {stale}"

"""CI invariant: no package imports another package's private names.

A leading underscore means "this module's business". Inside one top-level
package (`veles.core`, `veles.cli`, `veles.daemon`, …) reaching into a
sibling's `_helper` is fine; across packages it means the name is someone's
real API and should drop the underscore — or the caller is leaning on an
internal it should not know about. Both a `_name` and a name inside a
`_module` count.

`_BASELINE` lists what existed when the lock went in (M296). It may shrink,
never grow, and a stale entry fails too.
"""

from __future__ import annotations

import ast
from pathlib import Path

_SRC = Path(__file__).resolve().parent.parent / "src"

_BASELINE: frozenset[tuple[str, str]] = frozenset(
    {
        # The self-knowledge skeleton walks the CLI parser (see test_layering).
        ("veles.core.knowledge.skeleton", "veles.cli._parsers.build_parser"),
        # Type-checking-only import of the local provider base class.
        ("veles.core.provider_factory", "veles.adapters.local._base.LocalOpenAIBase"),
        # Tool-name qualification for the subscription CLIs' MCP bridge.
        ("veles.runtime.registry", "veles.adapters.cli._tool_namespace.claude_mcp_prefix"),
        ("veles.runtime.registry", "veles.adapters.cli._tool_namespace.gemini_mcp_prefix"),
        ("veles.runtime.registry", "veles.adapters.cli._tool_namespace.qualify_prompt"),
    }
)


def _module(path: Path) -> str:
    return ".".join(path.relative_to(_SRC).with_suffix("").parts)


def _package(module: str) -> str:
    parts = module.split(".")
    return ".".join(parts[:2])


def _resolve(module: str | None, level: int, importer: str) -> str:
    if level == 0:
        return module or ""
    base = importer.split(".")[:-1]
    base = base[: len(base) - (level - 1)]
    return ".".join([*base, module] if module else base)


def _private(name: str) -> bool:
    return name.startswith("_") and not name.startswith("__")


def _found() -> set[tuple[str, str]]:
    out: set[tuple[str, str]] = set()
    for path in _SRC.rglob("*.py"):
        importer = _module(path)
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if not isinstance(node, ast.ImportFrom):
                continue
            target = _resolve(node.module, node.level, importer)
            if not target.startswith("veles.") or _package(target) == _package(importer):
                continue
            private_module = any(_private(part) for part in target.split(".")[1:])
            for alias in node.names:
                if private_module or _private(alias.name):
                    out.add((importer, f"{target}.{alias.name}"))
    return out


def test_no_new_private_cross_imports() -> None:
    new = sorted(_found() - _BASELINE)
    assert not new, (
        "Imports of another package's private names — make the name public "
        "or stop depending on it:\n" + "\n".join(f"  {a} -> {b}" for a, b in new)
    )


def test_baseline_does_not_rot() -> None:
    stale = sorted(_BASELINE - _found())
    assert not stale, f"Remove these from _BASELINE, they no longer happen: {stale}"

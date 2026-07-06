"""M194 CI invariant: `veles.core` must not import `veles.cli`,
`veles.daemon`, or `veles.channels` at module top level.

Core is the reusable kernel (agent loop, memory, permission, tools). The
CLI, daemon, and channels layers sit *above* it and may import core; core
importing *up* into them creates a cycle and drags the whole surface into
any `import veles.core.*`. Function-local (lazy) imports are allowed — a
few genuine upward reaches exist (config-schema needs the channel
registry; the knowledge skeleton walks the CLI parser) but only when the
relevant code path runs, not on import.

Static AST scan (side-effect free, precise top-level-vs-nested, exact
file:line:symbol on failure). Relative imports are resolved against the
file's package because ruff `TID`/tidy-imports is OFF (see pyproject
`select`), so `from ..daemon import x` is not lint-banned and would be a
real bypass vector.
"""

from __future__ import annotations

import ast
from pathlib import Path

_FORBIDDEN = ("veles.cli", "veles.daemon", "veles.channels")
_SRC = Path(__file__).resolve().parent.parent / "src"
_CORE = _SRC / "veles" / "core"


def _module_name(path: Path) -> str:
    """Dotted module name for a file under src/ (e.g. veles.core.model_resolver)."""
    rel = path.relative_to(_SRC).with_suffix("")
    return ".".join(rel.parts)


def _resolve(module: str | None, level: int, importer: str) -> str:
    """Resolve a possibly-relative ImportFrom target to an absolute module.

    `importer` is the dotted name of the file doing the import; its package
    is everything but the last component. `level` N walks N packages up.
    """
    if level == 0:
        return module or ""
    pkg_parts = importer.split(".")[:-1]  # containing package of the module
    base = pkg_parts[: len(pkg_parts) - (level - 1)]
    return ".".join([*base, module]) if module else ".".join(base)


def _is_type_checking(node: ast.If) -> bool:
    test = node.test
    if isinstance(test, ast.Name) and test.id == "TYPE_CHECKING":
        return True
    return (
        isinstance(test, ast.Attribute)
        and test.attr == "TYPE_CHECKING"
        and isinstance(test.value, ast.Name)
        and test.value.id == "typing"
    )


def _leaks(path: Path) -> list[str]:
    """Return 'file:line: name' for every top-level import of a forbidden layer."""
    importer = _module_name(path)
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found: list[str] = []

    def visit(node: ast.AST, *, in_function: bool, in_type_checking: bool) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                visit(child, in_function=True, in_type_checking=in_type_checking)
            elif isinstance(child, ast.If) and _is_type_checking(child):
                visit(child, in_function=in_function, in_type_checking=True)
            elif isinstance(child, (ast.Import, ast.ImportFrom)):
                if in_function or in_type_checking:
                    continue
                names: list[str] = []
                if isinstance(child, ast.Import):
                    names = [alias.name for alias in child.names]
                else:
                    names = [_resolve(child.module, child.level, importer)]
                for name in names:
                    if any(name == f or name.startswith(f + ".") for f in _FORBIDDEN):
                        rel = path.relative_to(_SRC.parent)
                        found.append(f"{rel}:{child.lineno}: {name}")
            else:
                visit(child, in_function=in_function, in_type_checking=in_type_checking)

    visit(tree, in_function=False, in_type_checking=False)
    return found


def test_core_has_no_top_level_upward_imports() -> None:
    leaks: list[str] = []
    for path in sorted(_CORE.rglob("*.py")):
        leaks.extend(_leaks(path))
    assert not leaks, "veles.core has top-level imports of an upper layer:\n" + "\n".join(leaks)

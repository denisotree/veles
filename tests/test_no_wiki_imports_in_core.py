"""Release A lock: core never imports the wiki engine.

Everything the wiki adds reaches core through `api.contribute(...)`
(`veles.core.contributions`). An `import veles.modules.wiki…` anywhere in these
packages — at module level or inside a function, even under TYPE_CHECKING —
re-couples core to one content engine. Since release B (the wiki ships from the
registry) this covers the CLI, the TUI and the SDK too.
"""

from __future__ import annotations

import ast
from pathlib import Path

_SRC = Path(__file__).resolve().parent.parent / "src" / "veles"
_LOCKED = ("core", "runtime", "adapters", "daemon", "cli", "tui", "sdk")
_ENGINE = "veles.modules.wiki"


def _wiki_imports(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names = [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module:
            names = [node.module]
        else:
            continue
        found += [
            f"{path.relative_to(_SRC)}:{node.lineno} {n}" for n in names if n.startswith(_ENGINE)
        ]
    return found


def test_core_does_not_import_the_wiki_engine() -> None:
    hits = [
        hit
        for pkg in _LOCKED
        for p in sorted((_SRC / pkg).rglob("*.py"))
        for hit in _wiki_imports(p)
    ]
    assert not hits, "core imports the wiki engine — use a contribution instead:\n" + "\n".join(
        hits
    )

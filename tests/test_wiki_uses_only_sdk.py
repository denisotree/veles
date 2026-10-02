"""The wiki module imports Veles only through `veles.sdk` — the same rule
`veles registry validate` enforces on registry modules, checked here before the
wiki moves to the registry. Its own files are imported relatively: in the
registry it loads as `_veles_module_wiki`, not `veles.modules.wiki`."""

from __future__ import annotations

import ast
from pathlib import Path

_MODULE = Path(__file__).resolve().parent.parent / "src" / "veles" / "modules" / "wiki"
_ALLOWED = ("veles.sdk",)


def _allowed(name: str) -> bool:
    return not (name == "veles" or name.startswith("veles.")) or any(
        name == a or name.startswith(a + ".") for a in _ALLOWED
    )


def test_wiki_module_imports_only_the_sdk() -> None:
    bad: list[str] = []
    for path in sorted(_MODULE.rglob("*.py")):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                names = [node.module]
            else:
                continue
            bad += [f"{path.name}:{node.lineno} {n}" for n in names if not _allowed(n)]
    assert not bad, "import from veles.sdk instead:\n" + "\n".join(bad)

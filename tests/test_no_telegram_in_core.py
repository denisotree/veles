"""Core names no messaging platform (release C)."""

import ast
from pathlib import Path

_SRC = Path(__file__).resolve().parent.parent / "src" / "veles"
_LOCKED = [
    *(_SRC / "daemon").rglob("*.py"),
    *(_SRC / "channels").rglob("*.py"),
    *(_SRC / "sdk").rglob("*.py"),
    _SRC / "cli" / "commands" / "channel.py",
    _SRC / "cli" / "_parsers" / "channel.py",
    _SRC / "core" / "config_schema.py",
    _SRC / "core" / "platforms.py",
    _SRC / "core" / "channel_setup.py",
]


def _docstrings(tree: ast.AST) -> set[int]:
    ids: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            body = getattr(node, "body", [])
            if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
                ids.add(id(body[0].value))
    return ids


def test_no_telegram_import_anywhere() -> None:
    for path in _SRC.rglob("*.py"):
        assert "veles.channels.telegram" not in path.read_text(encoding="utf-8"), path


def test_locked_code_has_no_telegram_strings_or_names() -> None:
    bad: list[str] = []
    for path in _LOCKED:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        docs = _docstrings(tree)
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                if id(node) not in docs and "telegram" in node.value.lower():
                    bad.append(f"{path}:{node.lineno}")
            elif isinstance(node, ast.Name) and "telegram" in node.id.lower():
                bad.append(f"{path}:{node.lineno}")
    assert bad == []

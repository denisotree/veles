"""Release E: nothing outside the catalogue branches on a provider id."""

from __future__ import annotations

import ast
from pathlib import Path

_SRC = Path(__file__).resolve().parent.parent / "src" / "veles"
_IDS = {"claude-cli", "gemini-cli", "ollama", "llamacpp", "openai-compat", "openrouter"}
_ROOTS = ("core", "runtime", "cli", "daemon", "tui")
_ALLOWED = {
    "core/providers.py",
    "core/provider_kinds.py",
    "core/defaults.py",
    "core/routing/ensemble.py",  # parse_spec: a bare slug is an OpenRouter model
    "cli/repl/model_catalog.py",  # curated model suggestions keyed by id
}
_GONE = {
    "PROVIDER_CHOICES",
    "PROVIDER_API_KEY_ENVS",
    "ALL_PROVIDERS",
    "PROVIDER_VALUES",
    "LOCAL_PROVIDERS",
    "CLI_PROVIDERS",
}


def _hits(tree: ast.AST) -> list[int]:
    lines: list[int] = []
    for node in ast.walk(tree):
        consts: list[ast.expr] = []
        if isinstance(node, ast.Compare):
            consts = [node.left, *node.comparators]
        elif isinstance(node, (ast.Set, ast.Tuple, ast.List)):
            consts = list(node.elts)
        lines += [
            c.lineno
            for c in consts
            if isinstance(c, ast.Constant) and isinstance(c.value, str) and c.value in _IDS
        ]
    return lines


def test_no_provider_id_branches_outside_the_catalogue() -> None:
    bad = []
    for root in _ROOTS:
        for path in (_SRC / root).rglob("*.py"):
            rel = path.relative_to(_SRC).as_posix()
            if rel in _ALLOWED:
                continue
            bad += [f"{rel}:{n}" for n in _hits(ast.parse(path.read_text(encoding="utf-8")))]
    assert bad == []


def test_the_hand_kept_provider_lists_stay_gone() -> None:
    for path in _SRC.rglob("*.py"):
        names = {
            n.id
            for n in ast.walk(ast.parse(path.read_text(encoding="utf-8")))
            if isinstance(n, ast.Name)
        }
        assert not (names & _GONE), path

"""CI invariant: comments and docstrings are written in English.

Project convention: code, identifiers, filenames and commit messages are
English. Russian belongs in `docs/<lang>/` and `src/veles/locales/*.toml` — the
two places whose entire purpose is to be in another language.

**Comments and docstrings only.** String *literals* are deliberately not checked,
because Russian in a literal is almost always data the code operates on rather
than something a reader has to understand:

- `core/fts.py::_STOPWORDS_RU` — the Russian stopword list itself;
- `cli/repl/terminal.py::_jcuken` — the JCUKEN keyboard layout, for
  transliterating a mis-layout keystroke;
- `core/modes/goal.py` — the affirmative vocabulary an intent matcher compares
  against;
- prompts that show a model bilingual examples so it recognises an instruction
  in either language;
- test fixtures that feed Russian input to code whose job is to handle it;
- every `locales/*.toml`.

Translating any of those would break them. A Russian *comment*, by contrast, is
only ever prose, and prose in the repository is English.

`_ALLOWED` lists the files where an English comment legitimately **quotes** a
Russian token — the quote is the specification. `core/modes/goal.py` carries the
sharpest example: `"продолж"` is a stem, and the comment
`# продолжи / продолжай / продолжить` is what tells a reader which word forms it
covers. Rendering that in English would delete the information.
"""

from __future__ import annotations

import ast
import io
import re
import tokenize
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_ROOTS = (_ROOT / "src" / "veles", _ROOT / "tests")
_CYRILLIC = re.compile(r"[Ѐ-ӿ]")

# file -> why an English comment there quotes Russian.
_ALLOWED = {
    "src/veles/core/fts.py": "names the stopwords being filtered",
    "src/veles/core/insight_extractor.py": "lists the trigger words the regex matches",
    "src/veles/core/modes/goal.py": "spells out which word forms each stem covers",
    "src/veles/modules/agentops/tools.py": "quotes example phrases the tool matches",
    "tests/test_repl_prototype.py": "quotes the leaked UI string under guard",
    "tests/test_telegram_forward_grouping.py": "quotes the message used as input",
    # This file explains the rule by showing the exception, so it is one.
    "tests/test_code_is_english.py": "quotes the stem example in its own docstring",
}


def _prose_with_cyrillic(path: Path) -> list[tuple[int, str]]:
    """(line, text) for every comment or docstring containing Cyrillic."""
    source = path.read_text(encoding="utf-8")
    out: list[tuple[int, str]] = []
    try:
        for token in tokenize.generate_tokens(io.StringIO(source).readline):
            if token.type == tokenize.COMMENT and _CYRILLIC.search(token.string):
                out.append((token.start[0], token.string.strip()))
    except (tokenize.TokenError, IndentationError):  # pragma: no cover
        pass
    try:
        tree = ast.parse(source)
    except SyntaxError:  # pragma: no cover
        return out
    for node in ast.walk(tree):
        if not isinstance(node, ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef):
            continue
        doc = ast.get_docstring(node, clean=False)
        if not doc or not _CYRILLIC.search(doc):
            continue
        line = node.body[0].lineno if node.body else 1
        first = next(line_ for line_ in doc.splitlines() if _CYRILLIC.search(line_))
        out.append((line, first.strip()))
    return out


def find_russian_prose() -> dict[str, list[tuple[int, str]]]:
    """Relative path -> offending comments/docstrings, excluding `_ALLOWED`."""
    out: dict[str, list[tuple[int, str]]] = {}
    for root in _ROOTS:
        for path in sorted(root.rglob("*.py")):
            rel = str(path.relative_to(_ROOT))
            if rel in _ALLOWED:
                continue
            hits = _prose_with_cyrillic(path)
            if hits:
                out[rel] = hits
    return out


def test_comments_and_docstrings_are_english() -> None:
    offenders = find_russian_prose()
    assert not offenders, (
        "Russian prose in comments/docstrings — the repository writes these in "
        "English (Russian belongs in docs/<lang>/ and locales/*.toml):\n"
        + "\n".join(
            f"  {path}:{line}  {text[:90]}"
            for path, hits in sorted(offenders.items())
            for line, text in hits
        )
    )


def test_allowlist_entries_still_apply() -> None:
    """An allowlisted file that no longer quotes Russian should leave the list,
    or it becomes cover for a comment someone writes there later."""
    stale = sorted(rel for rel in _ALLOWED if not _prose_with_cyrillic(_ROOT / rel))
    assert not stale, f"No longer needed in _ALLOWED — remove: {stale}"

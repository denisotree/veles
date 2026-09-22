"""CI invariant: a function must not be reachable only from tests.

**The defect this exists to catch.** `core/tools/persistence.py::record_use` was
written in M120, covered by tests, and had **no production caller at all** for
five months. `tool_uses` was empty in every project that ever existed, so
`veles tool list`'s telemetry columns were blank and the M121b pattern detector —
the "offer to turn three repetitions into a skill" loop — could never fire. Its
own e2e test called `record_use` by hand and passed, which is exactly why nobody
noticed: every test proved the persistence layer worked, none proved anything
called it. M252 wired it up; this test is the lock so the next one cannot hide
as long.

The same shape bit twice more in the same sprint: `load_into_registry` was called
without `conn=`, so its catalogue sync never ran while a docstring claimed it
did, and `_warn_if_agents_md_invalid` was nearly left defined with zero callers.

**The signature.** A public function whose name appears in `src/` *only* at its
own definition, but does appear in `tests/`. That is not "unused" — unused code
is harmless. It is "someone built a mechanism, tested it, and never connected
it", which reads as working from every angle except the one that matters.

**Why references rather than a call graph.** A dispatch-table entry, a lazy
import and a decorator registration are all wiring, and none of them is a call
expression; a call graph would report them as dead. Counting AST references
catches every form — see `_referenced_names` for the one form it must NOT count,
found by testing this lock against the defect it was written for.

**Verified against `record_use` itself** (2026-09-18): removing the `_dispatch`
call restores the M252 state, and the lock fails naming
`persistence.py:137`. A lock that has not been shown to catch its own
motivating case is decoration.

`_BASELINE` held the 54 findings that already existed when the lock went in; a
per-function review on 2026-09-22 (plan `dev-requests-2026-09-22.md`, step 10)
took it to 37. That review found the list was *not* all harmless leftovers:
three entries were features a user could see failing — `set_title` (no session
had ever been titled), `recent_error_events` (`/errors` lost earlier runs in
M187) and `update_settings` (the daemon picker showed a stale model and port) —
and were wired up rather than deleted. So an entry here is a question, not a
verdict. **The list may shrink, never grow.** Deleting one is welcome; adding
one means a mechanism was built and left disconnected.
"""

from __future__ import annotations

import ast
from collections import Counter
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_SRC = _ROOT / "src" / "veles"
_TESTS = _ROOT / "tests"

# Dispatched by name rather than called, so a name scan cannot see the wiring.
_SKIP_PREFIXES = (
    "cmd_",  # CLI verb handlers, dispatched from a command table
    "action_",  # Textual bindings, dispatched by name
    "on_",  # Textual / prompt_toolkit event handlers
    "reset_",  # test hooks, by design test-only
    "clear_",  # ditto
)
_SKIP_EXACT = {"main", "run"}
# A decorator that registers the function elsewhere (the registry calls it).
_REGISTERING_DECORATORS = ("tool", "property", "hook", "setter", "command")

_BASELINE = frozenset(
    {
        "available_locales",
        # Kept on purpose (reviewed 2026-09-22): an observation hook that lets
        # tests read state from outside instead of reaching into `_active_state`.
        # Test-only by design, not by neglect.
        "current_state",
        "delete_embedding",
        "denied",
        "event_decision_str",
        "find_parent_project",
        "get_embedding",
        "get_provider",
        "get_skill",
        "get_skill_tool_refs",
        "list_completed",
        "list_skills",
        "parse_plan_ref",
        "parse_tool_calls",
        "set_project_wizard_prompter",
        "set_wizard_prompter",
        "skeleton_ref_index",
        "stable_text",
        "unregister_platform",
        "update_status",
    }
)


def _public_functions() -> dict[str, tuple[str, int]]:
    """name -> (relative path, line) for every candidate definition in src/."""
    out: dict[str, tuple[str, int]] = {}
    for path in sorted(_SRC.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                continue
            name = node.name
            if name.startswith("_") or name.startswith(_SKIP_PREFIXES) or name in _SKIP_EXACT:
                continue
            decorators = " ".join(ast.unparse(d) for d in node.decorator_list)
            if any(d in decorators for d in _REGISTERING_DECORATORS):
                continue
            out.setdefault(name, (str(path.relative_to(_ROOT)), node.lineno))
    return out


def _referenced_names(root: Path) -> Counter[str]:
    """Identifiers referenced *as code* under `root`, counted in one pass.

    **Not a text scan.** The first cut counted raw tokens and did not catch the
    very defect it was written for: `record_use` was listed in its module's
    `__all__` the entire five months it went uncalled, and a string in `__all__`
    looks identical to a use. An export is a promise that something *may* call
    this, which is precisely what was never true.

    So: AST names only — `Name`, `Attribute`, and `from x import y` aliases.
    String constants are excluded, which drops `__all__` and `getattr(o, "x")`.
    An import with no call still counts as wiring, because ruff's F401 makes
    that state unable to persist.

    One pass over the tree rather than a regex per candidate: the latter is
    O(names × bytes) and took ~56s here. A test that slow gets skipped locally,
    and a lock nobody runs is not a lock."""
    counts: Counter[str] = Counter()
    for path in root.rglob("*.py"):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:  # pragma: no cover - a fixture with deliberate junk
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Name):
                counts[node.id] += 1
            elif isinstance(node, ast.Attribute):
                counts[node.attr] += 1
            elif isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    counts[alias.name] += 1
            elif isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                counts[node.name] += 1  # the definition itself
    return counts


def find_unwired() -> dict[str, tuple[str, int]]:
    """Public functions mentioned in `src/` only at their own definition, and
    mentioned at least once in `tests/`. Exposed so the same scan can be run by
    hand while cleaning the baseline down."""
    in_src = _referenced_names(_SRC)
    in_tests = _referenced_names(_TESTS)
    return {
        name: where
        for name, where in _public_functions().items()
        # >1 in src means something other than the `def` line mentions it — a
        # call, an import, a dispatch-table entry, an `__all__` export.
        if in_src[name] <= 1 and in_tests[name] > 0
    }


def test_no_new_test_only_functions() -> None:
    """A mechanism that only tests reach is one nobody connected."""
    unwired = find_unwired()
    new = {n: w for n, w in unwired.items() if n not in _BASELINE}
    assert not new, (
        "These functions are reachable only from tests — they were built, covered, "
        "and never wired into a production path (the M252 `record_use` defect):\n"
        + "\n".join(f"  {n}  {w[0]}:{w[1]}" for n, w in sorted(new.items()))
        + "\n\nWire it up, or delete it. Add to _BASELINE only with a reason."
    )


def test_baseline_does_not_rot() -> None:
    """Every baseline entry must still be a real finding. When one gets wired up
    or deleted, it leaves this list — the list only ever shrinks, so a stale
    entry would quietly re-open the hole it was meant to document."""
    stale = sorted(_BASELINE - set(find_unwired()))
    assert not stale, (
        "Baseline entries that are no longer test-only (wired up or deleted) — "
        f"remove them from _BASELINE: {stale}"
    )


# ---- M277: the same defect one level up — a whole module nothing imports ----
#
# The function lock cannot see it: every function in an orphan module is
# referenced by its siblings, so none of them is "only at its definition".
# Measured 2026-09-22: 8 of 385 modules had no importer in src/. Two were wired
# by name (`mcp_server` is launched with `-m`; `graphify_rebuild` is a template
# copied into projects) — the rules below recognise both without a list. The
# other six were reviewed one by one in M279 and all deleted, so the baseline is
# empty: any module nothing imports now fails this test.
_MODULE_BASELINE: frozenset[str] = frozenset()


def _module_name(path: Path) -> str:
    parts = list(path.relative_to(_SRC.parent).with_suffix("").parts)
    return ".".join(parts[:-1] if parts[-1] == "__init__" else parts)


def _entry_point_modules() -> set[str]:
    import tomllib

    scripts = tomllib.loads((_ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"][
        "scripts"
    ]
    return {target.split(":", 1)[0] for target in scripts.values()}


def find_unimported_modules() -> set[str]:
    """Modules under src/ that nothing in src/ imports or launches by name."""
    modules = {
        _module_name(p): p
        for p in _SRC.rglob("*.py")
        if "templates" not in p.relative_to(_SRC).parts  # data copied into projects
    }
    reached: set[str] = set(_entry_point_modules())
    for path in _SRC.rglob("*.py"):
        here = _module_name(path)
        package = here if path.name == "__init__.py" else here.rpartition(".")[0]
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Import):
                targets = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                base = node.module or ""
                if node.level:
                    anchor = package.split(".")[: len(package.split(".")) - node.level + 1]
                    base = ".".join(anchor + ([node.module] if node.module else []))
                targets = [base] + [f"{base}.{alias.name}" for alias in node.names]
            elif isinstance(node, ast.Constant) and isinstance(node.value, str):
                targets = [node.value]  # `python -m veles.x.y`: the exact dotted name
            else:
                continue
            for target in targets:
                parts = target.split(".")  # importing a.b.c runs a and a.b too
                reached.update(".".join(parts[: k + 1]) for k in range(len(parts)))
    return {
        name
        for name in modules
        if name not in reached and not name.endswith("__main__") and name != "veles"
    }


def test_no_new_unimported_modules() -> None:
    new = sorted(find_unimported_modules() - _MODULE_BASELINE)
    assert not new, (
        "These modules are imported by nothing in src/ — built and never connected:\n"
        + "\n".join(f"  {m}" for m in new)
        + "\n\nImport it where it belongs, or delete it."
    )


def test_module_baseline_does_not_rot() -> None:
    stale = sorted(_MODULE_BASELINE - find_unimported_modules())
    assert not stale, f"Now imported or deleted — remove from _MODULE_BASELINE: {stale}"

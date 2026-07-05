# Veles Self-Knowledge (how-to answers) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give Veles a framework-global usage-knowledge source so the agent answers "how do I do X in Veles" from real docs (fresh facts + curated depth), injected via recall and a deep-lookup tool, working even on weak models.

**Architecture:** New `core/knowledge/` module = single source, two surfaces. A *live skeleton* (`skeleton.py`) derives "what exists" from code (argparse commands/flags, builtin skills, builtin tools) so it never goes stale; *curated notes* (`src/veles/knowledge/notes/*.md`) add depth. `store.py` (`KnowledgeStore`) ranks both with lightweight token-overlap + a threshold that self-gates non-Veles queries. Surface 1: a new engine-independent `_collect_about_veles` stream in `MemoryRouter.recall`. Surface 2: a `veles_help` builtin tool. A CI freshness test fails if a note references a command/flag/skill that no longer exists.

**Tech Stack:** Python 3, argparse introspection, `hatchling` (ships `.md` under `src/veles/` automatically), pytest, ruff, mypy.

## Global Constraints

- **Milestone:** M186 (ceiling M185 at authoring time — verify with `grep -oE "M1[0-9][0-9]" MILESTONES.md` before writing the MILESTONES entry).
- **Line length:** 100 cols; run `uv run ruff format src tests` + `uv run ruff check --fix src tests` before every commit (`uv` at `~/.local/bin/uv`).
- **Local CI parity before any push:** `uv run ruff check src tests` → `uv run ruff format --check src tests` → `uv run mypy` → `pytest`.
- **Temp dirs:** never `/tmp`; pytest already uses `--basetemp=./tmp/pytest`.
- **Edits:** use Edit/Write only — never shell redirection.
- **Commit messages:** English, describe the change, no Claude/Anthropic attribution.
- **Notes language:** English (matches code); the agent answers in the user's language via model translation.
- **No back-compat needed:** this is all-new; no shims.
- **Engine-independence invariant:** the `about-veles` recall source and `veles_help` MUST NOT consult `wiki_enabled` — they work in every layout.

---

### Task 1: `notes.py` — Note dataclass + parser

**Files:**
- Create: `src/veles/core/knowledge/__init__.py` (empty)
- Create: `src/veles/core/knowledge/notes.py`
- Test: `tests/knowledge/test_notes.py`

**Interfaces:**
- Consumes: `veles.core.skills.parse_frontmatter(text) -> tuple[dict, str]` (existing).
- Produces:
  - `Note(slug: str, title: str, topics: list[str], related: list[str], body: str)` — frozen dataclass.
  - `parse_note(path: pathlib.Path) -> Note`.
  - `load_notes(root: pathlib.Path | None = None) -> list[Note]` — parses every `*.md` under `root` (default: `src/veles/knowledge/notes/`), sorted by slug.

- [ ] **Step 1: Create the empty package marker**

Create `src/veles/core/knowledge/__init__.py` with a one-line docstring:

```python
"""Framework-global Veles self-knowledge (skeleton + curated notes) — M186."""
```

- [ ] **Step 2: Write the failing test**

Create `tests/knowledge/test_notes.py`:

```python
from pathlib import Path

from veles.core.knowledge.notes import Note, load_notes, parse_note


def _write(tmp_path: Path, name: str, text: str) -> Path:
    p = tmp_path / name
    p.write_text(text, encoding="utf-8")
    return p


def test_parse_note_reads_frontmatter_and_body(tmp_path):
    p = _write(
        tmp_path,
        "run-a-session.md",
        "---\n"
        "title: Run an interactive agent session\n"
        "topics: [run, session, prompt]\n"
        'related: ["cmd:run", "flag:run:--manager"]\n'
        "---\n"
        "Use `veles run \"your prompt\"` to start a session.\n",
    )
    note = parse_note(p)
    assert isinstance(note, Note)
    assert note.slug == "run-a-session"
    assert note.title == "Run an interactive agent session"
    assert note.topics == ["run", "session", "prompt"]
    assert note.related == ["cmd:run", "flag:run:--manager"]
    assert "veles run" in note.body


def test_load_notes_sorted_by_slug(tmp_path):
    _write(tmp_path, "b.md", "---\ntitle: B\n---\nbody b\n")
    _write(tmp_path, "a.md", "---\ntitle: A\n---\nbody a\n")
    notes = load_notes(tmp_path)
    assert [n.slug for n in notes] == ["a", "b"]


def test_load_default_notes_ship_in_package():
    # The real seeded notes must be discoverable with no argument.
    notes = load_notes()
    assert len(notes) >= 1
    assert all(n.title for n in notes)
```

- [ ] **Step 3: Run test to verify it fails**

Run: `pytest tests/knowledge/test_notes.py -v`
Expected: FAIL — `ModuleNotFoundError: veles.core.knowledge.notes` (and the default-notes test fails until Task 4 seeds notes; that is expected here).

- [ ] **Step 4: Write `notes.py`**

```python
"""Curated how-to notes: parse `knowledge/notes/*.md` into `Note` objects.

Each note is frontmatter (`title`, `topics`, `related`) + a markdown body.
`related` holds typed refs (`cmd:`, `flag:<cmd>:`, `skill:`, `tool:`) that the
freshness guard (tests/knowledge/test_knowledge_freshness.py) validates against
the live skeleton so a note can never lie about what Veles offers.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from veles.core.skills import parse_frontmatter

# Notes ship inside the package, next to this module's parent:
# src/veles/knowledge/notes/*.md
_NOTES_ROOT = Path(__file__).resolve().parent.parent.parent / "knowledge" / "notes"


@dataclass(frozen=True, slots=True)
class Note:
    slug: str
    title: str
    body: str
    topics: list[str] = field(default_factory=list)
    related: list[str] = field(default_factory=list)


def _as_str_list(value: object) -> list[str]:
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def parse_note(path: Path) -> Note:
    fm, body = parse_frontmatter(path.read_text(encoding="utf-8"))
    return Note(
        slug=path.stem,
        title=str(fm.get("title", path.stem)).strip(),
        body=body.strip(),
        topics=_as_str_list(fm.get("topics")),
        related=_as_str_list(fm.get("related")),
    )


def load_notes(root: Path | None = None) -> list[Note]:
    base = root or _NOTES_ROOT
    if not base.is_dir():
        return []
    return [parse_note(p) for p in sorted(base.glob("*.md"))]
```

- [ ] **Step 5: Run the parser tests (default-notes test still red until Task 4)**

Run: `pytest tests/knowledge/test_notes.py -v -k "not default"`
Expected: PASS for `test_parse_note_reads_frontmatter_and_body` and `test_load_notes_sorted_by_slug`.

- [ ] **Step 6: Commit**

```bash
git add src/veles/core/knowledge/__init__.py src/veles/core/knowledge/notes.py tests/knowledge/test_notes.py
git commit -m "feat(knowledge): Note dataclass + notes parser (M186)"
```

---

### Task 2: `skeleton.py` — live capabilities from code

**Files:**
- Create: `src/veles/core/knowledge/skeleton.py`
- Test: `tests/knowledge/test_skeleton.py`

**Interfaces:**
- Consumes:
  - `veles.cli._parsers.build_parser() -> argparse.ArgumentParser` (existing; lazy-imported to avoid a core→cli import cycle).
  - `veles.core.skills.mount_builtin_skills() -> list[Skill]` (existing; `Skill.name`, `Skill.description`).
  - `veles.core.tools.registry.registry` + `import veles.core.tools.builtin` to populate it.
- Produces:
  - `SkeletonEntry(kind: str, name: str, summary: str, aliases: list[str])` — `kind ∈ {"cmd","flag","skill","tool"}`. For a flag, `name` is `"<cmd>:<flag>"` (e.g. `"run:--manager"`).
  - `build_skeleton() -> list[SkeletonEntry]`.
  - `skeleton_ref_index(entries) -> set[str]` — the set of valid `related`-ref strings (`"cmd:run"`, `"flag:run:--manager"`, `"skill:tool_authoring"`, `"tool:read_file"`) for the freshness guard.

- [ ] **Step 1: Write the failing test**

Create `tests/knowledge/test_skeleton.py`:

```python
from veles.core.knowledge.skeleton import (
    build_skeleton,
    skeleton_ref_index,
)


def test_skeleton_includes_core_commands():
    entries = build_skeleton()
    cmds = {e.name for e in entries if e.kind == "cmd"}
    assert {"run", "init", "skill"} <= cmds


def test_skeleton_includes_a_known_flag():
    entries = build_skeleton()
    flags = {e.name for e in entries if e.kind == "flag"}
    # `veles run --manager` exists (VISION §5.3 / M122f).
    assert "run:--manager" in flags


def test_skeleton_includes_builtin_skills_and_tools():
    entries = build_skeleton()
    skills = {e.name for e in entries if e.kind == "skill"}
    tools = {e.name for e in entries if e.kind == "tool"}
    assert "tool_authoring" in skills
    assert "read_file" in tools


def test_ref_index_shape():
    idx = skeleton_ref_index(build_skeleton())
    assert "cmd:run" in idx
    assert "flag:run:--manager" in idx
    assert "skill:tool_authoring" in idx
    assert "tool:read_file" in idx
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/knowledge/test_skeleton.py -v`
Expected: FAIL — `ModuleNotFoundError: veles.core.knowledge.skeleton`.

- [ ] **Step 3: Write `skeleton.py`**

```python
"""Live "what exists in Veles" skeleton, derived from code so it never rots.

Sources: the argparse command/flag tree (`cli._parsers.build_parser`), builtin
skills (`mount_builtin_skills`), and builtin tools (the `@tool` registry). The
skeleton backs both the knowledge search (fresh facts) and the freshness guard
(`related` refs in curated notes are validated against `skeleton_ref_index`).
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class SkeletonEntry:
    kind: str  # "cmd" | "flag" | "skill" | "tool"
    name: str
    summary: str
    aliases: list[str] = field(default_factory=list)


def _walk_commands(entries: list[SkeletonEntry]) -> None:
    from veles.cli._parsers import build_parser

    parser = build_parser()
    for action in parser._actions:
        if not isinstance(action, argparse._SubParsersAction):
            continue
        for cmd_name, subparser in action.choices.items():
            help_text = (subparser.description or "").strip()
            sub_names: list[str] = []
            entries.append(
                SkeletonEntry(kind="cmd", name=cmd_name, summary=help_text)
            )
            for sub_action in subparser._actions:
                # Flags on this command.
                for opt in sub_action.option_strings:
                    if opt.startswith("--"):
                        entries.append(
                            SkeletonEntry(
                                kind="flag",
                                name=f"{cmd_name}:{opt}",
                                summary=(sub_action.help or "").strip(),
                            )
                        )
                # Nested subcommands (e.g. `skill list`) recorded as aliases.
                if isinstance(sub_action, argparse._SubParsersAction):
                    sub_names.extend(sub_action.choices.keys())
            if sub_names:
                entries.append(
                    SkeletonEntry(
                        kind="cmd",
                        name=cmd_name,
                        summary=help_text,
                        aliases=sorted(set(sub_names)),
                    )
                )


def _walk_skills(entries: list[SkeletonEntry]) -> None:
    from veles.core.skills import mount_builtin_skills

    for skill in mount_builtin_skills():
        entries.append(
            SkeletonEntry(kind="skill", name=skill.name, summary=skill.description or "")
        )


def _walk_tools(entries: list[SkeletonEntry]) -> None:
    import veles.core.tools.builtin  # noqa: F401  (fires @tool registration)
    from veles.core.tools.registry import registry

    for name in registry.list_names():
        try:
            desc = registry.get(name).description or ""
        except KeyError:
            desc = ""
        entries.append(SkeletonEntry(kind="tool", name=name, summary=desc))


def build_skeleton() -> list[SkeletonEntry]:
    entries: list[SkeletonEntry] = []
    _walk_commands(entries)
    _walk_skills(entries)
    _walk_tools(entries)
    return entries


def skeleton_ref_index(entries: list[SkeletonEntry]) -> set[str]:
    """Valid `related`-ref strings for the freshness guard."""
    return {f"{e.kind}:{e.name}" for e in entries}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/knowledge/test_skeleton.py -v`
Expected: PASS (4 tests). If `run:--manager` is missing, confirm the flag name with `grep -n "add_argument(\"--manager\"" src/veles/cli/_parsers/agent_loop.py` and adjust the test's expected flag to a real one.

- [ ] **Step 5: Commit**

```bash
git add src/veles/core/knowledge/skeleton.py tests/knowledge/test_skeleton.py
git commit -m "feat(knowledge): live capability skeleton from argparse+skills+tools (M186)"
```

---

### Task 3: `store.py` — `KnowledgeStore` search/get + token-overlap ranking

**Files:**
- Create: `src/veles/core/knowledge/store.py`
- Test: `tests/knowledge/test_store.py`

**Interfaces:**
- Consumes: `Note`, `load_notes` (Task 1); `SkeletonEntry`, `build_skeleton` (Task 2).
- Produces:
  - `KnowledgeHit(source: str, ref: str, title: str, body: str, score: int)` — `source ∈ {"note","skeleton"}`; `ref` is a stable id (note slug or skeleton `kind:name`).
  - `KnowledgeStore(notes: list[Note], skeleton: list[SkeletonEntry])` with:
    - `search(query: str, *, limit: int = 5) -> list[KnowledgeHit]` — token-overlap ranked, threshold-gated, highest score first.
    - `get(topic: str) -> KnowledgeHit | None` — exact match by note slug / skeleton ref / case-insensitive title.
  - `get_default_store() -> KnowledgeStore` — process-cached store built from packaged notes + live skeleton.
  - Module constant `SCORE_THRESHOLD: int = 3`.

- [ ] **Step 1: Write the failing test**

Create `tests/knowledge/test_store.py`:

```python
from veles.core.knowledge.notes import Note
from veles.core.knowledge.skeleton import SkeletonEntry
from veles.core.knowledge.store import (
    KnowledgeStore,
    get_default_store,
)


def _store() -> KnowledgeStore:
    notes = [
        Note(
            slug="run-session",
            title="Run an interactive agent session",
            body='Use `veles run "prompt"` to start a session in the current project.',
            topics=["run", "session", "prompt", "interactive"],
            related=["cmd:run"],
        ),
        Note(
            slug="add-source",
            title="Add a source file to the wiki",
            body="`veles add <file>` reads a source and writes a wiki page.",
            topics=["add", "ingest", "wiki", "source"],
            related=["cmd:add"],
        ),
    ]
    skeleton = [
        SkeletonEntry(kind="cmd", name="run", summary="interactive agent run"),
        SkeletonEntry(kind="cmd", name="add", summary="read a source into a wiki page"),
    ]
    return KnowledgeStore(notes, skeleton)


def test_search_surfaces_relevant_note_first():
    hits = _store().search("how do I run a session")
    assert hits, "expected at least one hit"
    assert hits[0].source == "note"
    assert hits[0].ref == "run-session"


def test_search_gates_out_non_veles_queries():
    # A generic coding query mentioning none of the notes' terms → no hits.
    assert _store().search("refactor this failing unit test suite") == []


def test_search_orders_by_score():
    hits = _store().search("add a source to the wiki")
    assert hits[0].ref == "add-source"


def test_get_by_slug_and_ref():
    st = _store()
    assert st.get("run-session").title == "Run an interactive agent session"
    assert st.get("cmd:add").source == "skeleton"
    assert st.get("nonexistent") is None


def test_default_store_builds_from_package():
    st = get_default_store()
    # Skeleton always yields entries even before notes are seeded.
    assert st.search("run") != [] or st.get("cmd:run") is not None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/knowledge/test_store.py -v`
Expected: FAIL — `ModuleNotFoundError: veles.core.knowledge.store`.

- [ ] **Step 3: Write `store.py`**

```python
"""KnowledgeStore: token-overlap search over curated notes + live skeleton.

Right-sized for a curated set of tens of entries — no FTS index, no embeddings,
deterministic and offline. The `SCORE_THRESHOLD` gate is what makes the recall
surface self-gating: a generic coding query scores below it and yields nothing,
so normal turns are never polluted with Veles docs.
"""

from __future__ import annotations

import functools
import re
from dataclasses import dataclass

from veles.core.knowledge.notes import Note, load_notes
from veles.core.knowledge.skeleton import SkeletonEntry, build_skeleton

_TOKEN_RE = re.compile(r"[a-z0-9_]+")
# "veles" is dropped: every entry is about Veles, so it is not discriminative.
_STOPWORDS = frozenset(
    {
        "the", "a", "an", "to", "in", "of", "how", "do", "i", "is", "it",
        "for", "and", "with", "my", "me", "on", "can", "what", "this", "that",
        "veles", "you", "your", "when", "where", "which", "use", "using", "get",
    }
)

SCORE_THRESHOLD = 3
_TITLE_WEIGHT = 3
_BODY_WEIGHT = 1


def _tokens(text: str) -> set[str]:
    return {t for t in _TOKEN_RE.findall(text.lower()) if t not in _STOPWORDS and len(t) > 1}


@dataclass(frozen=True, slots=True)
class KnowledgeHit:
    source: str  # "note" | "skeleton"
    ref: str
    title: str
    body: str
    score: int


@dataclass(frozen=True, slots=True)
class _Indexed:
    hit_ref: str
    source: str
    title: str
    body: str
    title_tokens: frozenset[str]
    body_tokens: frozenset[str]


class KnowledgeStore:
    def __init__(self, notes: list[Note], skeleton: list[SkeletonEntry]) -> None:
        self._entries: list[_Indexed] = []
        self._by_ref: dict[str, _Indexed] = {}
        self._by_title: dict[str, _Indexed] = {}
        for n in notes:
            self._add(
                ref=n.slug,
                source="note",
                title=n.title,
                body=n.body,
                title_text=n.title + " " + " ".join(n.topics),
                body_text=n.body,
            )
        for e in skeleton:
            self._add(
                ref=f"{e.kind}:{e.name}",
                source="skeleton",
                title=e.name,
                body=e.summary,
                title_text=e.name + " " + " ".join(e.aliases),
                body_text=e.summary,
            )

    def _add(
        self, *, ref: str, source: str, title: str, body: str, title_text: str, body_text: str
    ) -> None:
        idx = _Indexed(
            hit_ref=ref,
            source=source,
            title=title,
            body=body,
            title_tokens=frozenset(_tokens(title_text)),
            body_tokens=frozenset(_tokens(body_text)),
        )
        self._entries.append(idx)
        self._by_ref.setdefault(ref, idx)
        self._by_title.setdefault(title.lower(), idx)

    def _score(self, q: set[str], e: _Indexed) -> int:
        title_hits = len(q & e.title_tokens)
        body_hits = len(q & e.body_tokens)
        return _TITLE_WEIGHT * title_hits + _BODY_WEIGHT * body_hits

    def search(self, query: str, *, limit: int = 5) -> list[KnowledgeHit]:
        q = _tokens(query)
        if not q:
            return []
        scored: list[tuple[int, _Indexed]] = []
        for e in self._entries:
            s = self._score(q, e)
            if s >= SCORE_THRESHOLD:
                scored.append((s, e))
        # Highest score first; ties keep insertion order (notes before skeleton).
        scored.sort(key=lambda pair: pair[0], reverse=True)
        return [
            KnowledgeHit(source=e.source, ref=e.hit_ref, title=e.title, body=e.body, score=s)
            for s, e in scored[:limit]
        ]

    def get(self, topic: str) -> KnowledgeHit | None:
        key = topic.strip()
        idx = self._by_ref.get(key) or self._by_title.get(key.lower())
        if idx is None:
            return None
        return KnowledgeHit(
            source=idx.source, ref=idx.hit_ref, title=idx.title, body=idx.body, score=0
        )


@functools.lru_cache(maxsize=1)
def get_default_store() -> KnowledgeStore:
    """Process-cached store from packaged notes + the live skeleton."""
    return KnowledgeStore(load_notes(), build_skeleton())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/knowledge/test_store.py -v`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add src/veles/core/knowledge/store.py tests/knowledge/test_store.py
git commit -m "feat(knowledge): KnowledgeStore token-overlap search + threshold gate (M186)"
```

---

### Task 4: Seed the initial curated notes

**Files:**
- Create: `src/veles/knowledge/notes/run-a-session.md`
- Create: `src/veles/knowledge/notes/init-a-project.md`
- Create: `src/veles/knowledge/notes/add-a-source.md`
- Create: `src/veles/knowledge/notes/curate-memory.md`
- Create: `src/veles/knowledge/notes/skills-overview.md`
- Create: `src/veles/knowledge/notes/modules-overview.md`
- Create: `src/veles/knowledge/notes/sessions.md`
- Create: `src/veles/knowledge/notes/multi-project.md`
- Create: `src/veles/knowledge/notes/routing.md`
- Create: `src/veles/knowledge/notes/trust-ladder.md`
- Create: `src/veles/knowledge/notes/mcp-servers.md`
- Create: `src/veles/knowledge/notes/daemon-and-channels.md`
- Create: `src/veles/knowledge/notes/manager-mode.md`
- Test: reuses `tests/knowledge/test_notes.py::test_load_default_notes_ship_in_package` (Task 1).

**Interfaces:**
- Consumes: `parse_note` / `load_notes` (Task 1); `related` refs must resolve in `skeleton_ref_index` (Task 2) — enforced by Task 7.
- Produces: the seeded note corpus that recall + `veles_help` serve.

**Note-authoring rules (apply to every file below):**
- Frontmatter: `title`, `topics: [...]` (search keywords), `related: [...]` (only refs that exist in the skeleton — verify each `cmd:`/`flag:`/`skill:`/`tool:` against `veles --help` and the source before writing).
- Body: 3-8 lines — the exact command, when/why to use it, one concrete example. Lead with the command.
- Verify every command/flag against the CLI before committing (`veles <cmd> --help`).

- [ ] **Step 1: Write `run-a-session.md`**

```markdown
---
title: Run an interactive agent session
topics: [run, session, prompt, interactive, agent, repl]
related: ["cmd:run"]
---

Start a one-shot agent run with `veles run "your prompt"`. It executes in the
current project, loading that project's `AGENTS.md` context and memory.

For an interactive REPL instead, run bare `veles` (no subcommand).

Example: `veles run "summarise today's changes and write a wiki page"`.
```

- [ ] **Step 2: Write the remaining 12 notes**

Follow the same shape for each. Content guide (verify refs against source first):

- `init-a-project.md` — `veles init` (+ `--layout notes|bare`). topics: [init, project, scaffold, layout]. related: `["cmd:init"]` (add `flag:init:--layout` only if that flag exists — check `src/veles/cli/_parsers/project.py`).
- `add-a-source.md` — `veles add <file>` reads a source → writes a wiki page (was `ingest`). related: `["cmd:add"]`.
- `curate-memory.md` — `veles curate` compacts a session into project memory. related: `["cmd:curate"]`.
- `skills-overview.md` — `veles skill {list,show,add,remove,promote,demote}`; skills accumulate capability. related: `["cmd:skill"]`.
- `modules-overview.md` — `veles module {list,show,add,remove}`. related: `["cmd:module"]`.
- `sessions.md` — `veles sessions {list,show,delete,search}`. related: `["cmd:sessions"]`.
- `multi-project.md` — `veles project {list,add,remove,switch}` + `veles subproject {...}`. related: `["cmd:project", "cmd:subproject"]`.
- `routing.md` — `veles route {show,set,reset,refresh}` for ensemble routing. related: `["cmd:route"]`.
- `trust-ladder.md` — `veles trust {list,set,revoke,clear}` gates sensitive tools. related: `["cmd:trust"]`.
- `mcp-servers.md` — `veles mcp {list,test}`; external MCP servers via `[mcp.servers.*]`. related: `["cmd:mcp"]`.
- `daemon-and-channels.md` — `veles daemon {start,stop,status,token}` + `veles channel ...`. related: `["cmd:daemon", "cmd:channel"]`.
- `manager-mode.md` — hierarchical orchestration via `veles run --manager` (default off). related: `["cmd:run", "flag:run:--manager"]`.

- [ ] **Step 3: Verify all notes parse and ship**

Run: `pytest tests/knowledge/test_notes.py -v`
Expected: PASS — including `test_load_default_notes_ship_in_package` (now that notes exist).

- [ ] **Step 4: Smoke-test search over the real corpus**

Run:
```bash
~/.local/bin/uv run python -c "from veles.core.knowledge.store import get_default_store as g; print([h.ref for h in g().search('how do I run an interactive session')])"
```
Expected: a list containing `run-a-session` (and possibly related skeleton refs).

- [ ] **Step 5: Commit**

```bash
git add src/veles/knowledge/notes/
git commit -m "feat(knowledge): seed initial Veles how-to notes (M186)"
```

---

### Task 5: Recall integration — `_collect_about_veles`

**Files:**
- Modify: `src/veles/core/memory/router.py` (add collector + wire into `recall`)
- Test: `tests/knowledge/test_recall_about_veles.py`

**Interfaces:**
- Consumes: `get_default_store()` → `KnowledgeHit` (Task 3); `RecallHit` (existing, `router.py:47`).
- Produces: `MemoryRouter._collect_about_veles(query, *, limit) -> list[RecallHit]`, added as the **first** stream in `recall()`'s `streams` list.
- Invariant: MUST NOT call `wiki_enabled` — engine-independent.

- [ ] **Step 1: Write the failing test**

Create `tests/knowledge/test_recall_about_veles.py`:

```python
from veles.core.memory.router import MemoryRouter


def _router(tmp_path):
    from veles.core.project import init_project

    project = init_project(tmp_path)
    # No SessionStore/extras: isolates the about-veles stream.
    return MemoryRouter(project)


def test_recall_surfaces_about_veles_on_howto_query(tmp_path):
    hits = _router(tmp_path).recall("how do I run an interactive session in veles")
    refs = [h.rel_path for h in hits]
    assert any(r.startswith("about-veles:") for r in refs), refs


def test_recall_silent_on_plain_coding_query(tmp_path):
    hits = _router(tmp_path).recall("null pointer dereference in the parser loop")
    assert not any(h.rel_path.startswith("about-veles:") for h in hits)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/knowledge/test_recall_about_veles.py -v`
Expected: FAIL — no `about-veles:` hits (collector not wired yet).

- [ ] **Step 3: Add the collector and wire it into `recall`**

In `src/veles/core/memory/router.py`, add the collector method to `MemoryRouter` (place it right after `_collect_extra`, before `_collect_wiki`):

```python
    def _collect_about_veles(self, query: str, *, limit: int) -> list[RecallHit]:
        """Framework-global Veles usage knowledge (M186). Engine-independent:
        the store is package-shipped, so this never consults `wiki_enabled`.
        Below-threshold queries return [], keeping non-Veles turns clean."""
        from veles.core.knowledge.store import get_default_store

        hits: list[RecallHit] = []
        for h in get_default_store().search(query, limit=limit):
            summary = h.body.strip().replace("\n", " ")
            if len(summary) > _TURN_SUMMARY_CAP:
                summary = summary[: _TURN_SUMMARY_CAP - 1].rstrip() + "…"
            hits.append(
                RecallHit(
                    rel_path=f"about-veles:{h.ref}",
                    title=h.title,
                    summary=summary or h.title,
                    score=float(h.score),
                )
            )
        return hits
```

Then, in `recall()`, add the stream **first** so authoritative Veles docs lead the round-robin when relevant. Change:

```python
        wiki_hits = self._collect_wiki(query, limit=limit)
        insight_hits = self._collect_insights(query, limit=limit)
        turn_hits = self._collect_turns(query, limit=limit)
        extra_hits = self._collect_extra(query, limit=limit)
        streams = [wiki_hits, insight_hits, turn_hits, extra_hits]
```

to:

```python
        about_hits = self._collect_about_veles(query, limit=limit)
        wiki_hits = self._collect_wiki(query, limit=limit)
        insight_hits = self._collect_insights(query, limit=limit)
        turn_hits = self._collect_turns(query, limit=limit)
        extra_hits = self._collect_extra(query, limit=limit)
        streams = [about_hits, wiki_hits, insight_hits, turn_hits, extra_hits]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/knowledge/test_recall_about_veles.py -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Run the memory suite for regressions**

Run: `pytest tests/ -k "recall or router or memory" -q`
Expected: PASS (no regressions from the new stream).

- [ ] **Step 6: Commit**

```bash
git add src/veles/core/memory/router.py tests/knowledge/test_recall_about_veles.py
git commit -m "feat(knowledge): engine-independent about-veles recall stream (M186)"
```

---

### Task 6: `veles_help` builtin tool

**Files:**
- Create: `src/veles/core/tools/builtin/veles_help.py`
- Modify: `src/veles/core/tools/builtin/__init__.py` (add `veles_help` to the import block)
- Modify: `src/veles/core/tools/toolsets.toml` (add `veles_help` to `[builtin]` so every agent surface gets it)
- Test: `tests/knowledge/test_veles_help_tool.py`

**Interfaces:**
- Consumes: `get_default_store()` (Task 3); `@tool` decorator + `RiskClass.SEARCH_ONLY` (existing).
- Produces: registered tool `veles_help(query: str, limit: int = 3) -> str` returning full matching note bodies + skeleton lines as markdown.

- [ ] **Step 1: Write the failing test**

Create `tests/knowledge/test_veles_help_tool.py`:

```python
import veles.core.tools.builtin  # noqa: F401  (fires registration)
from veles.core.tools.registry import registry


def test_veles_help_registered():
    assert "veles_help" in registry.list_names()


def test_veles_help_returns_full_note_body():
    out = registry.get("veles_help").handler("how do I run an interactive session")
    assert "veles run" in out.lower()


def test_veles_help_handles_no_match():
    out = registry.get("veles_help").handler("zzzz nonexistent qqqq topic")
    assert "no matching veles documentation" in out.lower()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/knowledge/test_veles_help_tool.py -v`
Expected: FAIL — `veles_help` not in registry.

- [ ] **Step 3: Write `veles_help.py`**

```python
"""`veles_help` tool (M186): deep lookup into Veles self-knowledge.

The recall surface injects short digests automatically; this tool is the
deep-dive path — the agent calls it when it needs the full note text for a
how-to question. Same `KnowledgeStore` as recall: one source, two surfaces.
"""

from __future__ import annotations

from veles.core.risk import RiskClass
from veles.core.tools.registry import tool


@tool(risk_class=RiskClass.SEARCH_ONLY, side_effects=[])
def veles_help(query: str, limit: int = 3) -> str:
    """Answer "how do I do X in Veles" from Veles' own documentation.

    Returns the most relevant curated how-to notes plus live command/skill/tool
    facts. Use this whenever the user asks how to use a Veles feature and the
    recalled `<memory-context>` digest is not enough. `limit` caps the number of
    entries (default 3, max 8).
    """
    from veles.core.knowledge.store import get_default_store

    limit = max(1, min(limit, 8))
    hits = get_default_store().search(query, limit=limit)
    if not hits:
        return (
            "(no matching Veles documentation — rephrase, or check `veles --help`)"
        )
    blocks: list[str] = []
    for h in hits:
        body = h.body.strip() or "(no detail)"
        blocks.append(f"## {h.title}\n\n{body}")
    return "\n\n".join(blocks)
```

- [ ] **Step 4: Register the tool**

In `src/veles/core/tools/builtin/__init__.py`, add `veles_help` to the import tuple (keep alphabetical-ish order, next to `web_search`):

```python
    task_tools,
    veles_help,
    web_search,
    write_file,
)
```

In `src/veles/core/tools/toolsets.toml`, add `"veles_help"` to the `[builtin]` section's `tools = [...]` list (so it is available to `run`, which `includes = ["builtin"]`).

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/knowledge/test_veles_help_tool.py -v`
Expected: PASS (3 tests).

- [ ] **Step 6: Verify the toolset wiring**

Run:
```bash
~/.local/bin/uv run python -c "from veles.core.tools.toolsets import TOOLSETS; print('veles_help' in TOOLSETS['run'])"
```
Expected: `True`.

- [ ] **Step 7: Commit**

```bash
git add src/veles/core/tools/builtin/veles_help.py src/veles/core/tools/builtin/__init__.py src/veles/core/tools/toolsets.toml tests/knowledge/test_veles_help_tool.py
git commit -m "feat(knowledge): veles_help builtin tool for deep self-doc lookup (M186)"
```

---

### Task 7: CI freshness guard

**Files:**
- Create: `tests/knowledge/test_knowledge_freshness.py`

**Interfaces:**
- Consumes: `load_notes` (Task 1); `build_skeleton`, `skeleton_ref_index` (Task 2).
- Produces: a test that fails when any seeded note's `related` ref is missing from the live skeleton.

- [ ] **Step 1: Write the freshness test**

Create `tests/knowledge/test_knowledge_freshness.py`:

```python
from veles.core.knowledge.notes import load_notes
from veles.core.knowledge.skeleton import build_skeleton, skeleton_ref_index


def test_every_note_related_ref_exists_in_skeleton():
    idx = skeleton_ref_index(build_skeleton())
    dangling: list[str] = []
    for note in load_notes():
        for ref in note.related:
            if ref not in idx:
                dangling.append(f"{note.slug}: {ref}")
    assert not dangling, (
        "curated notes reference commands/flags/skills that no longer exist — "
        "update the note(s):\n  " + "\n  ".join(dangling)
    )


def test_notes_have_titles_and_bodies():
    for note in load_notes():
        assert note.title, f"{note.slug}: missing title"
        assert note.body.strip(), f"{note.slug}: empty body"
```

- [ ] **Step 2: Run test to verify it passes**

Run: `pytest tests/knowledge/test_knowledge_freshness.py -v`
Expected: PASS. If it fails, a seeded note's `related` ref is wrong — fix the note's frontmatter (the failure message names the note + dangling ref). Do NOT loosen the test.

- [ ] **Step 3: Prove the guard bites (manual, revert after)**

Temporarily add `"cmd:does-not-exist"` to one note's `related`, rerun the test, confirm it FAILS naming that ref, then revert the note.

Run: `pytest tests/knowledge/test_knowledge_freshness.py -v`
Expected: FAIL naming `cmd:does-not-exist`; after revert, PASS.

- [ ] **Step 4: Commit**

```bash
git add tests/knowledge/test_knowledge_freshness.py
git commit -m "test(knowledge): freshness guard — notes cannot reference removed capabilities (M186)"
```

---

### Task 8: Docs + full CI parity

**Files:**
- Modify: `MILESTONES.md` (add the M186 entry)
- Modify: `CLAUDE.md` (touch the status line — mention M186 self-knowledge)
- Test: full local CI parity run.

**Interfaces:**
- Consumes: nothing new.
- Produces: recorded milestone + a green local CI run mirroring GitHub CI.

- [ ] **Step 1: Confirm the milestone number**

Run: `grep -oE "M1[0-9][0-9]" MILESTONES.md | grep -oE "[0-9]+" | sort -n | tail -1`
Expected: `185` (→ use M186). If higher, use ceiling+1 and update this plan's references.

- [ ] **Step 2: Add the MILESTONES.md entry**

Append an `M186 — Veles self-knowledge (how-to answers)` entry describing: new `core/knowledge/` module (skeleton + notes + store), engine-independent `about-veles` recall stream, `veles_help` tool, CI freshness guard. Follow the existing entry format in that file.

- [ ] **Step 3: Touch the CLAUDE.md status line**

Update the "Project status" milestone list to mention M186 (self-knowledge). Keep it one clause; do not rewrite the section.

- [ ] **Step 4: Run full local CI parity**

Run:
```bash
~/.local/bin/uv run ruff check src tests && \
~/.local/bin/uv run ruff format --check src tests && \
~/.local/bin/uv run mypy && \
~/.local/bin/uv run pytest tests/knowledge -q && \
~/.local/bin/uv run pytest -q
```
Expected: all green. Fix any ruff/mypy issues (run `~/.local/bin/uv run ruff format src tests` + `ruff check --fix src tests` first).

- [ ] **Step 5: Commit**

```bash
git add MILESTONES.md CLAUDE.md
git commit -m "docs: record M186 Veles self-knowledge milestone"
```

---

## Self-Review

**1. Spec coverage:**
- Hybrid source (skeleton + curated notes) → Tasks 2 + 4. ✓
- Hybrid delivery (auto-recall + tool) → Tasks 5 + 6. ✓
- Ships in package, skeleton generated → Task 2 (generated), Task 4 (package notes; hatchling auto-includes). ✓
- CI guard → Task 7. ✓
- Token-overlap ranking + threshold self-gating → Task 3 (+ negative test). ✓
- Engine-independent (no `wiki_enabled`) → Task 5 invariant + `test_recall_silent_on_plain_coding_query`. ✓
- `self_doc` untouched/complementary → no task modifies it. ✓
- English notes → Task 4 authoring rules. ✓

**2. Placeholder scan:** Task 4 intentionally lists 12 notes by content-guide rather than full text — this is content authoring with explicit per-note command/topic/related specs and a hard "verify refs against source" rule + the Task 7 guard catching any bad ref. The one fully-worked note (`run-a-session.md`) is the template. All code steps show complete code.

**3. Type consistency:** `KnowledgeHit(source, ref, title, body, score)` used identically in Tasks 3/5/6. `SkeletonEntry(kind, name, summary, aliases)` and `skeleton_ref_index → {kind:name}` consistent across Tasks 2/7. `Note(slug, title, body, topics, related)` consistent Tasks 1/3/4/7. `RecallHit.rel_path = "about-veles:<ref>"` prefix consistent Tasks 5 test + collector. `get_default_store()` name consistent Tasks 3/5/6.

## Config-schema note (deferred)

The spec mentioned `config:` refs in the skeleton. Deferred from MVP to avoid a brittle dependency on a config-schema introspection surface — the skeleton covers `cmd`/`flag`/`skill`/`tool`, which is enough for the seeded notes. Add `config:` refs in a follow-up if notes need to cite config keys.

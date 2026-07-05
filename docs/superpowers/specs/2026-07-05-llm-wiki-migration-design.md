# Design: Layout-declared behaviour prompt + permissive llm-wiki + wiki migration/log-patch

**Date:** 2026-07-05
**Status:** approved (brainstorming)
**Branch:** `feat/wiki-migration-engine`
**Milestones:** M188 → M189 → M190 (ceiling M187; verify before numbering)

## Problem

The `llm-wiki` layout can only WRITE into `wiki/` (`sources/` is hard-readonly, everything
else refused). So a user request like "read all files in the current directory and migrate
them into the wiki layout" fails: the agent can read any project file (reads are already
project-wide) but cannot relocate raw files into `sources/` or write pages freely, and
`move_file` guards both endpoints so relocating an arbitrary project file is refused.

Two capability gaps and one behaviour gap:
1. A layout pack cannot declare a **behavioural prompt** — the only pack-authored prose that
   reaches the agent is the `AGENTS.md` template (seeded at init, doesn't reach existing
   projects) + `context_file` (INDEX.md) + a hardcoded `_RUN_WIKI_RAG_BLOCK`.
2. The **write-permission model** forces `llm-wiki` into `wiki/`-only. It should instead be a
   *universal, opt-in* per-layout permission mechanism: a layout MAY declare zones+permissions;
   if it declares none, the agent is unrestricted (read/write anywhere in the project root).
   `llm-wiki` should be permissive; the sources/wiki discipline moves to the prompt.
3. No **migration + log-patch behaviour**: articles/facts → wiki pages, raw → `sources/`, and
   "log-type" records (tasks/diaries/meetings — dated remarks) → merged as additions into the
   relevant existing wiki page (created if none).

## Approved decisions (from brainstorming)

- **Prompt-driven**, not a dedicated `migrate` command. The agent migrates in a normal `veles
  run` when asked, steered by a layout-declared behavioural prompt.
- **LLM classifies** log-type vs article by content (criteria live in the prompt); no `type:`
  schema.
- **Raw → `sources/`** (audit trail); the log's essence is **semantically merged** into the
  target wiki page (not raw-appended); **create the page if none exists**.
- **Permission model:** `writable_zones` is a universal, opt-in, layout-level permission
  mechanism. **No zones declared → NO restriction** (agent reads/writes anywhere in the project
  root; only `path_guard`'s project boundary + `..`/symlink rules apply). A layout that wants
  hard rules declares zones (e.g. `wiki → writable`, `sources → readonly`). `llm-wiki` becomes
  **permissive** (drops its restrictive zones); discipline lives in the prompt.
- **Read-gating is out of scope** for now: the mechanism gates writes (writable vs readonly);
  per-zone read/none can be a later milestone (YAGNI).

## Milestone decomposition (implement in sequence)

### M188 — Layout-declared behavioural prompt (infrastructure)
Give a layout pack a first-class way to inject behavioural instructions into the run system
prompt, read from the PACK (so edits reach existing projects, unlike `AGENTS.md`).

- **`core/layout/manifest.py`** — add `prompt_file: str | None = None` to `LayoutManifest`
  (path to a `.md` inside the pack root, e.g. `templates/behaviour.md`), parsed from
  `layout.toml` alongside `context_file`.
- **`cli/_runtime.py::build_run_system_prompt`** — read the active pack's `prompt_file` (via
  `find_layout`), scrub through `scan_for_injection`, cap length, and inject as a dedicated
  **stable** block ("Layout behaviour"). Engine-independent (works for any pack, not just
  wiki). Place it deterministically among the stable parts (near the other pack-authored
  blocks) so the cache prefix stays stable.
- No behaviour change until a pack ships a `prompt_file` (M190 does).
- **Tests:** manifest parses `prompt_file`; missing file / no field → no injection; a pack with
  `prompt_file` injects its content into the stable prompt (via a temp pack fixture).

### M189 — Universal opt-in layout permission mechanism + permissive llm-wiki
Make the write-permission contract explicit and general, and make `llm-wiki` permissive.

- **`core/layout/writable.py`** — make the "no declared zones → permissive (writable anywhere
  in project root)" contract explicit and documented (it is already the fallback at
  `writable.py:89-91`; lock it with a test and a clear docstring). Keep `is_writable` gating
  **writes only**; keep `readonly` zones enforced. The mechanism stays the single chokepoint
  the builtin write tools call via `_fs_write_guard.guard_write`.
- **`src/veles/layouts/llm-wiki/layout.toml`** — REMOVE the `[[layout.writable_zones]]`
  entries (`wiki/` writable, `sources/` readonly). llm-wiki thus declares no zones → permissive
  → agent may read/write/relocate any file under the project root. (`path_guard` still bounds
  to the project root.) Update the pack's AGENTS.md template prose that claims `sources/` is
  read-only (that becomes a prompt convention in M190, not a hard guard).
- Custom/alternative layouts keep declaring zones to hard-restrict (e.g. `wiki → writable`,
  `sources → readonly`) — mechanism unchanged and enforced for them.
- **Tests:** a layout with NO zones → `is_writable` True anywhere in project (and refuses
  outside project via path_guard); a layout WITH `sources/ readonly` → write to `sources/`
  refused, write to `wiki/` allowed; `llm-wiki` (post-change) → write to project-root file
  allowed; `move_file` relocating an arbitrary project file into `wiki/`/`sources/` now allowed
  under llm-wiki (both endpoints permissive).

### M190 — llm-wiki migration & log-patch behaviour (content)
Ship the behavioural prompt (via M188) that turns the now-permissive llm-wiki into a
migration + log-patch layout.

- **`src/veles/layouts/llm-wiki/layout.toml`** — set `prompt_file = "templates/behaviour.md"`.
- **`src/veles/layouts/llm-wiki/templates/behaviour.md`** (new) — the behavioural prompt:
  - The agent may read/move/write any project file; on a migration request it processes the
    whole directory.
  - **Raw source material → `sources/`** (immutable by convention; the agent doesn't edit files
    already under `sources/`).
  - **Article/fact** → a distilled **wiki page** under `wiki/<category>/` (existing ingest
    behaviour), raw copy relocated to `sources/`.
  - **Log-type record** (dated/periodic remark: task/diary/meeting — classified by content):
    `wiki_search`/`wiki_read_page` for a topical page → **semantically weave** the record's
    substance into the page body (e.g. "Already sent books B1, B2, B3 for restoration") →
    `wiki_write_page` (overwrite with merged body); **if no page exists, create one**; raw
    record also relocated to `sources/`.
- **Tool wiring** — confirm the `run` toolset (used for prompt-driven migration) exposes
  `wiki_search`, `wiki_read_page`, `wiki_write_page`, `wiki_list_pages`, `move_file`, and a way
  to land raw under `sources/` (`save_source`/`wiki_ingest` or `move_file`). Add any missing
  tool to the run/engine-wiki toolset. No new `wiki_append_to_page` primitive needed —
  semantic merge = read → integrate → overwrite.
- **Tests:** headless can't verify agentic behaviour; add (a) a smoke that the llm-wiki prompt
  block is present in the run system prompt (ties M188+M190), (b) tool-availability assertions,
  and note a **manual/eval** migration smoke (article→page, log→merge/create, raw→sources/) as
  a release gate.

## Components & boundaries

| Unit | Milestone | Does | Depends on |
|---|---|---|---|
| `LayoutManifest.prompt_file` + parse | M188 | Declare a pack behavioural prompt | manifest.py |
| prompt injection in `build_run_system_prompt` | M188 | Inject pack prompt into stable system prompt | `find_layout`, `scan_for_injection` |
| explicit permissive-default + docs | M189 | "no zones → unrestricted" contract | `writable.py`, `_fs_write_guard` |
| llm-wiki → permissive (drop zones) | M189 | Let llm-wiki write/relocate all project files | layout.toml |
| `templates/behaviour.md` | M190 | Migration + log-patch behaviour | M188 field, M189 writes |
| tool wiring (run toolset) | M190 | search/read/write/move/save-source available | toolsets.toml |

## Open risks
- **Losing the hard `sources/` immutability** for llm-wiki (now prompt-soft): acceptable per the
  user's decision; a determined/erroneous run could overwrite a source. Mitigated by the prompt
  convention + the raw copy living in `sources/` and the wiki being the working surface.
- **Agentic behaviour is not unit-testable**: M190 relies on a manual/eval smoke; keep the unit
  tests to the mechanical surfaces (prompt present, tools available, permissions correct).
- **Migration has no cross-file context** in the current batch-ingest path; prompt-driven
  migration runs in one agent turn/session so it can hold context — fine for the prompt-driven
  approach (we are NOT using the batch-ingest fan-out).

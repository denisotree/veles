# ADR-002: CLI surface — per-command verdict (M123)

- **Status**: Accepted
- **Date**: 2026-05-25
- **Supersedes**: —
- **Related**: `VISION.md` §7, `MILESTONES.md` Roadmap → M123,
  `docs/adr/001-memory-storage.md`

---

## Context

VISION §7 names a focused **core CLI**: `run`, `project`,
`skill|module|tool add|remove`, `curate` + an operational minimum
(`tui`, `daemon`, `channel`, `autopilot`, `trust`, `sessions`,
`init`). The pre-2026-05-25 `veles --help` carried **17+ additional
verbs** that accreted across milestones. The roadmap entry M123 said
each verb gets an **individual audit** (not a batch deprecation pass)
before any removal lands — per the recorded user feedback
"решения по CLI деpreсации — индивидуально, не batch".

This ADR captures the audit verdicts for the ten commands flagged
during M115's inventory phase. The verdicts are intentionally
conservative: when a command exposes operational utility that
doesn't map cleanly to a slash-command, a skill, or a daemon
endpoint, it stays — the cost of removing a sysadmin tool that no
TUI substitute exists for outweighs the cost of one extra `--help`
line.

Two verbs are already covered by other milestones:

- `dream` and `goal` are **modes**, not user-facing CLI verbs — they
  remain accessible primarily via the `/dream` / `/goal <task>`
  slash-commands in the TUI and channels, with thin CLI wrappers for
  scripting. See the auto-memory `project-modes-dream-goal`.
- `wiki`, `ingest`, `query`, `lint` are scheduled for migration into
  the `llm-wiki` layout-pack as skills (M117 + M117b). They are not
  audited here — their deprecation lives on the M117 follow-up.

---

## Audit verdicts

Each command was inspected for: (1) what it actually does, (2)
whether the function is reachable through another surface (slash,
daemon API, skill), (3) script-friendly use cases that justify a
shell verb. Outcomes: **keep** (stays in `veles --help`),
**move to skill** (functionality belongs in a layout-pack or skill),
**deprecate** (genuinely obsolete).

### `veles models <provider>` → **keep**

- Lists models a provider exposes (with `--refresh` to bypass the
  cache and `--as-json` for scripts).
- Thin wrapper over `tui.screens._model_fetcher.fetch_models`, so it
  shares the cache and curated-fallback path with the TUI picker.
- Script-friendly: `veles models openrouter | grep claude`.
- No equivalent slash-command (the picker is interactive only).

### `veles route {show,set,reset,refresh}` → **keep**

- Inspects and edits ensemble routing configuration in
  `<project>/.veles/routing.toml` (M43).
- Routing is core to the M5.7 advisor / ensemble behaviour from
  VISION § 5.7 — operational configuration, not content.
- Per-project state means it belongs in CLI under the project root,
  not in a global skill.

### `veles schema {validate,fix}` → **keep**

- Validates `AGENTS.md` against the recommended-section schema, and
  drives a fix wizard.
- M117's layout-pack architecture *extends* AGENTS.md (writable-zones
  declaration is M117b). This verb stays as the canonical entry
  point for schema validation; M117b expands its scope rather than
  replacing it.

### `veles subproject {init,list,switch,remove,suggest}` → **keep**

- Manages the vertical-subproject registry (M41) — VISION §5.6's
  "horizontal/vertical decomposition" feature.
- `init` / `remove` mutate the parent's `.veles/subprojects.json`,
  `switch` prints the path so `cd $(veles subproject switch frontend)`
  works. Operational; no TUI equivalent ships today.
- Core feature; not a candidate for removal.

### `veles secret {set,get,list,delete}` → **keep**

- Keychain-backed CLI for storing API keys (used heavily by the
  first-run wizard and by users rotating keys outside the wizard).
- Critical for VISION §8 (security: secrets stay in OS keychain, not
  in `~/.veles/config.toml`).
- Hosts behavioural code (`get_secret` raises `KeyringUnavailable`
  when keyring lib is missing) that downstream callers depend on.

### `veles doctor [--json] [--strict]` → **keep**

- Health check across user-global + active project (M59). Reports
  warnings/errors and exits non-zero on errors.
- The `--strict` mode is designed for CI gating after releases.
- No slash equivalent; the diagnostic surface is too coarse for the
  TUI inspector.

### `veles export {full,template} <path>` / `veles import <path>` → **keep**

- VISION §9 (portability) — the *only* way to take a project off the
  current machine. `full` produces a bit-for-bit bundle; `template`
  produces a sanitised export with PII redaction.
- Core feature; the only realistic argument against keeping it would
  be moving it under `veles project` as a subcommand (`veles project
  export/import`). That's a UX nit, not a deprecation; leave it for a
  future shell-level cleanup.

### `veles self-doc {refresh,show}` → **keep, mark for renaming**

- Generates and displays project self-documentation
  (`<project>/.veles/wiki/self_doc.md` historically; M117 will move
  the destination per the layout pack's writable-zone declaration).
- Functionality lands inside the active project's writable zone, so
  the command runs an *agent turn* under the hood — it's neither a
  pure CLI utility nor a skill yet.
- Rename to `veles describe` (or fold under `veles project describe`)
  in a future UX pass — captured as a follow-up below, not a
  blocker.

### `veles browse {modules,skills} [<query>]` → **keep**

- Surface for the curated `github.com/<veles>/modules` and `…/skills`
  registries from VISION §6. Returns matching entries from the
  cached registry.
- Script-friendly (lets users grep the registry without a network
  round-trip if `--source` points at a local copy).
- No TUI substitute; the wizard's add flow doesn't expose registry
  search directly.

### `veles job {list,show,run,tick,...}` → **keep**

- Daemon-side scheduled jobs (M75) — CRUD-symmetric with the
  `JobRunner` background loop that powers `dream` consolidation on a
  cron-like schedule (VISION §5.1).
- `veles job tick` is the synchronous test path used by integration
  suites; removing it would force every test to spin up the daemon.
- Operational; daemon-adjacent; out of scope for slash-commands
  because jobs are persistent across sessions.

---

## Summary

| Command | Verdict | Reasoning (one-line) |
|---|---|---|
| `models` | keep | script-friendly model listing, no slash equivalent |
| `route` | keep | core ensemble routing config |
| `schema` | keep | canonical AGENTS.md validator; M117b extends it |
| `subprojects` | keep | VISION §5.6 vertical decomposition core |
| `secrets` | keep | OS keychain integration; security-critical |
| `doctor` | keep | health checks + CI gating with `--strict` |
| `portability` (`export`/`import`) | keep | VISION §9 portability core |
| `self_doc` | keep (rename later) | agent-turn under the hood; M117b destination |
| `browse` | keep | curated registry search; no TUI substitute |
| `job` | keep | daemon scheduled-jobs CRUD, persists across sessions |

**No command was deprecated by this audit.** That's the right outcome
for a per-command pass that resisted the urge to batch — each verb
has a concrete operational role that doesn't map cleanly to the
slash / skill / daemon-API alternatives.

The pre-set deletions from M117 (`wiki`, `ingest`, `query`, `lint`)
are tracked separately and remain on the M117b follow-up.

---

## Follow-ups not in M123

These are intentionally out of scope here — recorded so future
sessions don't re-litigate them:

1. **`self_doc` → rename** to `veles describe` (or fold under
   `veles project describe`). UX-only; functional shape stays.
2. **`portability` → reorganise** under `veles project export/import`
   for symmetry with the rest of the `project` subcommand surface.
   Optional.
3. **`route` schema awareness** of layout-pack manifest (M117) — when
   a layout-pack declares its own routing preferences in
   `layout.toml`, `veles route show` should surface that as a layer.
4. **`browse` → embedding-aware search** once M119b lands sqlite-vec.
   The current TF-IDF substring match is fine for catalogues with
   <500 entries; growth past that will benefit from semantic ranking.

---

## Verification

This ADR is a decision document, not code. The verdicts above are
verifiable by:

1. **Re-running the audit:** `head -30
   src/veles/cli/commands/{models,route,schema,subprojects,secrets,doctor,portability,self_doc,browse,job}.py`
   and confirming the docstrings and entry points match the
   summaries above.
2. **Cross-checking the help surface:** `veles --help` lists every
   shipped verb; none of the ten audited names is missing.
3. **Test suite:** the full regression (2490 passed, 10 skipped as
   of M122 MVP) stays green — no code changes here.

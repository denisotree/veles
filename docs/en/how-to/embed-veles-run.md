# How to embed `veles run` in another program

> 🌐 **Languages:** **English** (other locales still to sync)

`veles run` is the supported way to call Veles from another system — a monitoring
pipeline, a CI step, a cron script. It is a plain subprocess: prompt in, answer on
stdout, diagnostics on stderr, outcome in the exit code. No daemon, no HTTP, no
WebSocket.

Prefer this over the [daemon](run-as-daemon.md) unless you need a persistent
session or channels. `POST /v1/runs` returns a run id, not the answer — the text
only reaches a WebSocket subscriber, so a headless caller has nothing to read.

## The call

```python
subprocess.run(
    ["veles", "run", "--verbose", prompt],
    cwd=project_dir,
    capture_output=True, text=True,
    stdin=subprocess.DEVNULL,
    timeout=600,
)
```

Four things in that snippet are load-bearing.

**Flags go after the verb.** `veles run --verbose "…"`, never
`veles --verbose run "…"`. Both parse, but only the first is honoured — see
[Flag position](#flag-position) below.

**`stdin=subprocess.DEVNULL` is mandatory.** The permission gates refuse
automatically when there is no TTY, and that check reads `sys.stdin` only. A
parent that captures stdout and stderr but leaves stdin attached to a terminal
reaches an interactive menu and blocks until your timeout.

**Set `timeout` yourself.** Veles has no wall-clock limit of its own. The
internal ceilings are `--max-tokens-total` (default 100 000) and
`--max-iterations` (default 1000, a runaway backstop rather than a task budget).

**`cwd` decides where relative paths land.** `--project-root` redirects Veles'
own path resolution (memory, tool discovery, artifacts) but not the working
directory, so a custom tool doing `open("out.json", "w")` still writes relative
to `cwd`.

## Output contract

| Stream | Contents |
|---|---|
| stdout | the final answer text, plus one trailing newline. Nothing else. |
| stderr | `<session=…>`, `<finished after …>`, `error: …`, `warning: …`, progress |

Both are asserted by `tests/test_cli_run_contract.py`, so they are a contract
rather than an observation.

`--verbose` adds the per-turn progress log and the closing summary line, which is
where the stop reason and the token spend appear:

```
<finished after 7 turns, reason=completed, budget=8412/100000>
```

Two flags fall **outside** this contract:

- `--stream` sends every round's prose to stdout, including narration emitted
  before a tool call — not just the final answer. Do not use it if you parse stdout.
- `--manager` returns before the session line and the exit-code mapping.

## Exit codes

| Code | Meaning | What the caller should do |
|---|---|---|
| 0 | completed | use the answer |
| 1 | provider error, or an unrecognised non-completion | retry |
| 2 | no model configured, missing API key, unknown `--resume` id, no project | fix the setup; never retry |
| 3 | `max_iterations` | re-scope the task or raise `--max-iterations` |
| 4 | `budget_exhausted` | raise `--max-tokens-total` |
| 5 | `empty` — the model produced no final text | retry |
| 6 | `cancelled` | interrupted |

A stop reason added in a later version maps to 1, so an unknown outcome can never
be mistaken for success.

## Custom tools

A tool is a `@tool()`-decorated function in `<project>/.veles/tools/*.py`; type
annotations become its JSON schema. Two gates catch people out.

**`veles trust set <tool>` does nothing for an ordinary custom tool.** The trust
ladder only fires for tools declared `sensitive=True`. A plain `@tool()` has no
risk class, resolves to `allow`, and is never gated — the grant is written and
never read.

**The real gate is `veles tool approve`**, and it is keyed on a hash of the file:

```bash
veles tool approve my_tool --yes    # --yes skips the prompt; no TTY needed
```

**Every edit invalidates the approval.** An unapproved file is skipped — the model
sees neither the tool nor a refusal, so the agent can answer confidently having
never reached its data source. Since v0.30 the skip prints
`warning: N self-authored tool file(s) not loaded (unapproved): …` to stderr;
watch for it, and re-approve after every write.

Two more sharp edges:

- `@tool(timeout_s=…)` is advisory — nothing enforces it. Bound slow work inside
  the tool (a client-side query timeout), not with the decorator.
- A `str` return longer than `max_result_chars` (default 8000) is spilled to
  `.veles/artifacts/` and replaced with a preview. Aggregate server-side.

### Structured results without prose parsing

Tool-call arguments are schema-validated already, so a second tool is the cheapest
machine-readable channel — no core support needed:

```python
@tool()
def emit_result(status: str, detail: str) -> str:
    """Record the final structured result. Call exactly once, last."""
    out = Path(".veles/tmp/result.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"status": status, "detail": detail}))
    return "recorded"
```

Read the file after the process exits; if it is absent, fall back to the prose on
stdout rather than dropping the result. Clear it before each run so you cannot
read a stale one.

### Restricting the toolset

There is no per-project toolset file yet, and `[permissions]` has no `deny` —
the values are `allow`, `approval_required`, and `always_confirm`. Since a
non-TTY run auto-refuses, `always_confirm` is an effective deny for a headless
caller:

```toml
# <project>/.veles/config.toml
[permissions]
fetch_url  = "always_confirm"
web_search = "always_confirm"
```

## Memory across invocations

Each run is its own session, and everything is written to `memory.db`
unconditionally. What varies is whether the *next* run can find it.

**The prompt is the recall query, verbatim.** Short queries are ANDed — good for
a keyword lookup. Longer ones are ORed and ranked by relevance, because demanding
that one stored row contain *every* token of a paragraph matches nothing once
timestamps, ids and metric values are in the mix. Before v0.31 long queries were
ANDed too, and retrieved nothing at all, silently.

Ranked overlap is still weaker than a precise query, so keep the prompt short and
stable and pass bulk data by file:

```python
(project_dir / ".veles/tmp/input.json").write_text(json.dumps(payload))
prompt = f"Investigate {stable_topic_key}. Input: .veles/tmp/input.json"
```

**Write what matters deterministically.** The automatic insight extractor only
fires on explicit cues ("remember…", "never…") or a tool error, so a routine run
usually writes nothing durable. Insert the row yourself — plain SQLite works, and
the FTS triggers index it:

```python
with sqlite3.connect(project_dir / ".veles/memory.db") as c:
    c.execute(
        "INSERT INTO insights(title, body, category, created_at, confidence) "
        "VALUES (?,?,?,?,?)",
        (title, body, f"topic/{stable_topic_key}", time.time(), 1.0),
    )
```

**Read it back deterministically too.** `memory_query` is read-only SQL over
`memory.db` and is in the default toolset. Instruct the agent to start with it,
and retrieval no longer depends on ranking luck:

```sql
SELECT title, body, created_at FROM insights
WHERE category = 'topic/<key>' OR category = 'curated-session'
ORDER BY created_at DESC LIMIT 10
```

Note the second clause: the curator files its distillations under
`curated-session`, not your key.

Worth knowing:

- **`rules` skip the ranking entirely.** The rules digest goes into the stable
  part of the system prompt, unlike recalled insights which compete for five
  slots. Durable operational facts belong there (`memory_save_rule`); the digest
  holds 12, so spend them deliberately.
- **Tool output is not indexed.** Turn search covers user and assistant messages
  only. Evidence that must survive has to reach an insight or the answer text.
- **`.veles/memory/insights/*.md` is a rendered view, never searched.** Dropping
  markdown there does nothing.
- Recall prunes insights below confidence 0.3.
- There is no update/delete API for insights. Retire one by superseding it via
  `insight_refs`, which recall filters out.

### Flags that change what accumulates

- **`--resume` disables learning.** It skips the curator and the insight
  extractor, and it reuses the system prompt frozen when the session started —
  so no fresh recall, no fresh rules digest. Use a fresh session per invocation
  and let memory carry the continuity.
- **`--no-insights`** turns off insight extraction. Leave it on.
- **`--no-curator`** also disables the post-turn dream, skill suggestions, and the
  proposers. Its one merit is latency: the curator is a synchronous LLM pass that
  delays process exit. If you set it, run `veles curate` on a schedule instead.
- **`veles dream --include-consolidation`** — the flag matters. Insight dedup and
  embedding backfill run only under it, so a plain `veles dream` leaves duplicate
  insights uncollapsed and vectors unwritten.

Semantic recall of insights additionally needs a **local** embedding backend
(Ollama with `nomic-embed-text`); a cloud API key does not enable it, by design —
project text is never sent to a cloud embedder. Without one, recall stays
keyword-only. `veles doctor` reports which backend is active.

## Concurrency

One `memory.db` per project, so serialise runs against the same project in the
caller. Separate projects (`--project-root`) are independent.

## Flag position

`veles` accepts the shared agent-loop flags both before and after the verb,
because bare `veles` starts the REPL and needs them at the top level. Before
v0.30 a flag placed *before* the verb was silently discarded — `veles --verbose
run "x"` lost `--verbose`, and `veles --provider anthropic run "x"` ran on
openrouter while suppressing the project's configured provider. Both positions
are equivalent now, but if you are pinned to an older version, put flags after
the verb.

## See also

- [CLI reference](../reference/cli.md) — every flag on `run`
- [Security: trust, autopilot, secrets](security-and-permissions.md)
- [Run Veles as a daemon](run-as-daemon.md) — when you want sessions and channels

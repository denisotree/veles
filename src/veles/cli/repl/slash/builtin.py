"""Slash-commands as pure handlers (line, ctx) -> SlashResult.

Removed in M80: `/load`, `/show`, `/search`, `/theme`, `/init` (all picker-only,
via the Textual chat UI's Ctrl+R / Ctrl+T hotkeys). Project init is handled by
the project wizard on first run (M82). M187 (Task 5) reinstated `/theme` as a
slash command once the Textual chat UI was deleted and its Ctrl+T theme picker
had no replacement: `/theme` opens an inline filterable picker in the App
(mirrors `/model`), `/theme <name>` sets one directly.

The dispatcher in `registry.py` strips the leading `/` and command word
before calling each handler — every handler receives just the remaining
text in `line`.
"""

from __future__ import annotations

import contextlib
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from veles.cli.repl.slash.registry import SlashContext, SlashRegistry, SlashResult
from veles.core.text import first_heading
from veles.core.timeutil import local_stamp

if TYPE_CHECKING:
    from veles.core.project import Project

# ---------------- helpers ----------------


def _parse_int(text: str, default: int) -> int:
    text = (text or "").strip()
    if not text:
        return default
    try:
        return max(1, int(text.split()[0]))
    except ValueError:
        return default


_HOTKEYS = (
    ("@", "open the project file picker, insert a path"),
    ("Ctrl+I / Ctrl+O", "toggle the inspector (tool activity + status/duration)"),
    ("Ctrl+X Ctrl+E", "open the current draft in $EDITOR"),
    ("Ctrl+V", "paste an image from the clipboard (or plain text)"),
    ("Shift+Tab", "cycle mode (auto, planning, writing, goal)"),
    ("Ctrl+J / Shift+Enter", "insert a newline (Enter submits)"),
    ("Up / Down", "input history"),
    ("Esc", "cancel a picker/question, or stop generation"),
    ("Ctrl+C", "cancel a picker/stop generation/clear input; twice on an empty line to exit"),
    ("Ctrl+D", "exit"),
    ("⌘C / Ctrl+Shift+C", "native terminal copy (the REPL writes to the normal screen)"),
)


# ---------------- basics ----------------


def _help(registry: SlashRegistry) -> SlashResult:
    """Every registered command with its usage and aliases, then the hotkeys —
    built from the registry, so a new command shows up without editing a list."""
    rows = ["Slash commands:"]
    for cmd in registry.commands():
        names = ", ".join([cmd.usage or cmd.name, *cmd.aliases])
        rows.append(f"  {names:<30} {cmd.summary}")
    rows += ["", "Hotkeys:", *(f"  {key:<30} {what}" for key, what in _HOTKEYS)]
    return SlashResult.ok("\n".join(rows))


# `/errors` also reaches back past this process: a failure in an earlier REPL
# run, a `veles run` or the daemon is in `events.jsonl` and would otherwise be
# invisible after a restart. Bounded so a days-old, already-fixed failure doesn't
# resurface on a fresh start.
_EARLIER_ERRORS_WINDOW_S = 24 * 60 * 60
_EARLIER_ERRORS_LIMIT = 10


def _earlier_errors(project, current_session_id: str | None) -> list[tuple[str, str]]:
    """`(ts, text)` for recent `error` events from other runs. Best-effort: a
    missing or unreadable log yields nothing rather than breaking `/errors`."""
    if project is None:
        return []
    from veles.core.events import events_path_for_project, read_events, recent_error_events

    try:
        events = read_events(events_path_for_project(project.state_dir))
    except OSError:
        return []
    recent = recent_error_events(
        events, within_seconds=_EARLIER_ERRORS_WINDOW_S, limit=_EARLIER_ERRORS_LIMIT
    )
    return [
        (str(e.get("ts", "")), f"{e.get('error_type', 'error')}: {e.get('message', '')}")
        for e in recent
        # This session's own failures are already in the in-memory list.
        if not current_session_id or e.get("session_id") != current_session_id
    ]


def _errors(line: str, ctx: SlashContext) -> SlashResult:
    """This session's failures, plus other runs' from the last 24h."""
    del line
    earlier = _earlier_errors(ctx.project, getattr(ctx.state, "session_id", None))
    if not ctx.errors and not earlier:
        return SlashResult.ok("  no errors in this session or the last 24h")
    rows = [f"  · {e}" for e in ctx.errors[-20:]]
    if earlier:
        rows.append("  earlier runs, last 24h:")
        rows += [f"  · {ts} {text}" for ts, text in earlier]
    return SlashResult.ok("\n".join(rows))


def _sessions(line: str, ctx: SlashContext) -> SlashResult:
    del line, ctx
    return SlashResult(open_picker="sessions")


def _resume(line: str, ctx: SlashContext) -> SlashResult:
    prefix = line.strip()
    match = (
        next((s for s in ctx.store.list_sessions(limit=50) if s.id.startswith(prefix)), None)
        if prefix
        else None
    )
    if match is None:
        return SlashResult.err("/resume <id-prefix> — see /sessions for ids")
    ctx.state.session_id = match.id
    return SlashResult.ok(f"  resumed {match.id}")


def _quit(line: str, ctx: SlashContext) -> SlashResult:
    del line, ctx
    return SlashResult(quit=True)


def _clear(line: str, ctx: SlashContext) -> SlashResult:
    del line
    ctx.state.session_id = None
    ctx.state.last_assistant_text = None
    # A fresh session starts its counters from zero — the status bar kept
    # showing the OLD session's cumulative totals after /clear (live
    # 2026-07-08: `tok 4M/108k · ctx 58k · cache 178k` on an empty chat).
    ctx.state.tokens_in = 0
    ctx.state.tokens_out = 0
    ctx.state.last_turn_total_tokens = 0
    ctx.state.last_prompt_tokens = 0
    ctx.state.last_turn_cache_read = 0
    return SlashResult(clear_chat=True, text="session cleared")


def _session(line: str, ctx: SlashContext) -> SlashResult:
    del line
    return SlashResult.ok(f"session={ctx.state.session_id or '<no session yet>'}")


# ---------------- save / history / load / show ----------------


def _save(line: str, ctx: SlashContext) -> SlashResult:
    """`/save <slug>` — keep the last assistant reply: as `wiki/queries/<slug>.md`
    when the layout has a wiki, otherwise as a memory insight.

    M87 also had `/save` with no argument list "pending insight candidates",
    and a matching slug commit one. Nothing ever produced a candidate — not in
    the Textual UI and not after M187 — so that branch always answered "needs a
    slug" and was removed. Insights are extracted automatically by the curator
    and dream passes.
    """
    from veles.core.layout.engines import wiki_enabled

    if not line:
        return SlashResult.err("/save needs a slug, e.g. `/save graph-traversal-notes`")
    slug = line.split()[0]
    last = ctx.state.last_assistant_text
    if not last or not last.strip():
        return SlashResult.err("/save: nothing to save yet (no assistant response in this run)")
    title = first_heading(last) or slug.replace("-", " ").title()

    # On layouts without the wiki engine (bare/notes), there is no
    # `wiki/queries/` to write to — keep the reply as a memory insight
    # instead of crashing on a Wiki the layout never created.
    if not wiki_enabled(ctx.project):
        from veles.core.memory.artefacts import append_memory_log
        from veles.core.tools.builtin.memory_save import save_insight_row

        rid = save_insight_row(
            title=title, body=last, category="tui-save", project=ctx.project, origin="stated"
        )
        if rid == 0:
            return SlashResult.err("/save failed: could not write insight to memory.db")
        with contextlib.suppress(Exception):
            append_memory_log(ctx.project, op="tui-save-insight", summary=f"-> insight #{rid}")
        return SlashResult.ok(f"saved insight #{rid}")

    # Legacy path: save the last assistant reply under wiki/queries/. Import
    # the wiki module only here, after the engine gate above — a non-wiki
    # project never reaches this branch and never imports it.
    from veles.modules.wiki.wiki import Wiki

    wiki = Wiki(ctx.project.wiki_root)
    try:
        rel = wiki.write_page(category="queries", slug=slug, title=title, content=last)
    except ValueError as exc:
        return SlashResult.err(f"/save failed: {exc}")
    wiki.append_log(op="tui-save", summary=f"saved last response to {rel}")
    return SlashResult.ok(f"saved to {rel}")


def _history(line: str, ctx: SlashContext) -> SlashResult:
    limit = _parse_int(line, ctx.state.history_limit)
    sessions = ctx.store.list_sessions(limit=limit)
    if not sessions:
        return SlashResult.ok("no sessions yet")
    rows = [f"recent sessions ({len(sessions)}):"]
    for info in sessions:
        marker = " *" if info.id == ctx.state.session_id else "  "
        title = info.title or "(untitled)"
        when = local_stamp(info.last_activity_at)
        rows.append(f"{marker}{info.id}  {when}  turns={info.turn_count}  {title}")
    return SlashResult.ok("\n".join(rows))


# ---------------- wiki (M83) ----------------


def _wiki(line: str, ctx: SlashContext) -> SlashResult:
    """`/wiki add <path|url>` — agent ingests a source into the wiki.
    `/wiki query <question>` — agent answers from the wiki using
    wiki_search/wiki_read_page. Both delegate to the live agent turn so
    the TUI doesn't fork a second runtime."""
    from veles.core.layout.engines import wiki_enabled

    if not wiki_enabled(ctx.project):
        return SlashResult.err(
            f"/wiki: the active layout pack {ctx.project.layout_name!r} does "
            "not enable the wiki engine"
        )
    del ctx
    if not line:
        return SlashResult.err("/wiki: expected add <path|url> | query <question>")
    parts = line.split(maxsplit=1)
    sub = parts[0]
    arg = parts[1].strip() if len(parts) > 1 else ""
    if sub == "add":
        return _wiki_add(arg)
    if sub == "query":
        return _wiki_query(arg)
    return SlashResult.err(f"/wiki: unknown subcommand {sub!r}; try add/query")


def _wiki_add(source: str) -> SlashResult:
    from veles.modules.wiki.ingest import ingest_user_message

    if not source:
        return SlashResult.err("/wiki add needs a path or URL")
    return SlashResult(
        text=f"ingesting {source} into the wiki…",
        submit_prompt=ingest_user_message(source),
    )


def _wiki_query(question: str) -> SlashResult:
    if not question:
        return SlashResult.err("/wiki query needs a question string")
    prompt = (
        f"Search the project wiki to answer: {question}\n\n"
        "Use wiki_search and wiki_read_page tools to find relevant pages, "
        "then summarize what we already know. Cite page paths in your reply."
    )
    return SlashResult(
        text=f"querying wiki for: {question}",
        submit_prompt=prompt,
    )


# ---------------- /model ----------------


def _model(line: str, ctx: SlashContext) -> SlashResult:
    """Three shapes:
    - `/model` — open the picker (cached when available).
    - `/model refresh` — open the picker and force a live re-fetch
      (relevant for cloud providers; local providers are always live).
    - `/model <id>` — set the model directly without opening the picker.
    """
    new = line.split()[0] if line else ""
    if not new:
        del ctx
        return SlashResult(open_picker="models")
    if new == "refresh":
        del ctx
        return SlashResult(open_picker="models:refresh")
    ctx.state.model = new
    # M81 + resolver-cascade fix: persist into tui_state.json **and**
    # `<project>/.veles/config.toml [engine] model`. The model resolver
    # consults project config above tui_state, so writing only the latter
    # would lose the user's pick on next boot whenever the wizard had
    # seeded a model into config.toml.
    from veles.core.tui_state import persist_model_choice

    persist_model_choice(ctx.project, new)
    return SlashResult.ok(f"model set to {new}")


# ---------------- /theme ----------------


def _theme(line: str, ctx: SlashContext) -> SlashResult:
    """Two shapes, mirroring `/model`:
    - `/theme` — open the inline filterable picker (App-side; the fallback
      simple-loop REPL instead prints the list, see `_print_theme_list`).
    - `/theme <name>` — set a theme directly without opening the picker.
    """
    from veles.cli.tui_theme import list_themes, load_theme
    from veles.core.user_config import persist_tui_theme

    new = line.split()[0] if line else ""
    if not new:
        return SlashResult(open_picker="themes")
    if load_theme(new) is None:
        return SlashResult.err(
            f"/theme: unknown theme {new!r}; try one of: {', '.join(list_themes())}"
        )
    ctx.state.theme_name = new
    persist_tui_theme(new)
    return SlashResult.ok(f"theme set to {new}")


# ---------------- /schema ----------------


def _schema(line: str, ctx: SlashContext) -> SlashResult:
    sub = (line or "validate").strip()
    if sub in ("", "validate"):
        from veles.core.agents_md_schema import validate

        agents_md = ctx.project.agents_md_path
        if not agents_md.is_file():
            return SlashResult.err(f"AGENTS.md not found at {agents_md}")
        result = validate(agents_md.read_text(encoding="utf-8", errors="replace"))
        if result.ok:
            return SlashResult.ok("✓ AGENTS.md has all recommended sections")
        return SlashResult.err(f"Missing sections: {', '.join(result.missing)}")
    if sub == "fix":
        return SlashResult.err(
            "/schema fix: interactive wizard not ported yet; "
            "run `veles schema fix` from the shell, then reload the TUI."
        )
    return SlashResult.err(f"/schema: unknown subcommand {sub!r}; try validate or fix")


# ---------------- /mode ----------------


def _mode(line: str, ctx: SlashContext) -> SlashResult:
    """`/mode` lists known modes and the active one. `/mode <name>` sets
    it directly (Shift+Tab cycles; this slash is the explicit form, and
    the headless path for scripts that drive the TUI). Persists to
    `<project>/.veles/tui_state.json` so the next boot honours it."""
    from veles.core.modes import CYCLE_ORDER
    from veles.core.tui_state import TuiPersistentState, save_for_project

    arg = (line or "").split()
    if not arg:
        rows = ["available modes:"]
        for name in CYCLE_ORDER:
            marker = " *" if name == ctx.state.mode else "  "
            rows.append(f"{marker}{name}")
        return SlashResult.ok("\n".join(rows))
    new = arg[0]
    if new not in CYCLE_ORDER:
        return SlashResult.err(f"/mode: unknown mode {new!r}; one of: {', '.join(CYCLE_ORDER)}")
    ctx.state.mode = new  # type: ignore[assignment]
    # Best-effort persistence; the in-memory switch already succeeded.
    with contextlib.suppress(OSError):
        save_for_project(
            ctx.project,
            TuiPersistentState(
                mode=new,
                active_goal_id=ctx.state.active_goal_id,
                model=ctx.state.model,
            ),
        )
    return SlashResult.ok(f"mode set to {new}")


# ---------------- /tokens, /context, /status (M115.1) ----------------
#
# Dedicated inspector commands per VISION §7.2. The StatusBar chip shows
# a single-line summary; these slash-commands return the per-session
# / per-turn / per-model breakdown that doesn't fit in a chip. Pure
# handlers: no UI imports, no side effects, results are testable
# string-payloads.


def _fmt_tokens_full(n: int) -> str:
    """Like `_fmt_tokens` in status_bar.py but always emits the raw
    number alongside the compact form so users see both `1234 (1k)`
    and don't lose precision."""
    if n < 1_000:
        return str(n)
    if n < 1_000_000:
        return f"{n} ({n // 1_000}k)"
    return f"{n} ({n // 1_000_000}M)"


def _tokens(line: str, ctx: SlashContext) -> SlashResult:
    """Per-session and per-turn token totals. The chip in StatusBar
    only shows in/out; this command also surfaces last-turn total and
    is honest about an empty session (prints zeros instead of going
    silent)."""
    del line
    st = ctx.state
    rows = [
        "tokens (this TUI session):",
        f"  in:        {_fmt_tokens_full(st.tokens_in)}",
        f"  out:       {_fmt_tokens_full(st.tokens_out)}",
        f"  total:     {_fmt_tokens_full(st.tokens_in + st.tokens_out)}",
        f"  last turn: {_fmt_tokens_full(st.last_turn_total_tokens)}",
    ]
    return SlashResult.ok("\n".join(rows))


def _context(line: str, ctx: SlashContext) -> SlashResult:
    """Live context occupancy against the model's window. Uses the same
    per-model registry (M177) the StatusBar chip uses, so the two surfaces
    never disagree on the window — and reports the last request's prompt
    size (resident context) rather than cumulative run usage."""
    del line
    from veles.core.model_windows import context_window_for

    st = ctx.state
    limit = context_window_for(st.model)
    used = st.last_prompt_tokens or st.last_turn_total_tokens
    pct = (used * 100) // max(limit, 1) if used else 0
    rows = [
        "context window:",
        f"  model: {st.model or '<none>'}",
        f"  used:  {_fmt_tokens_full(used)}",
        f"  limit: {_fmt_tokens_full(limit)}",
        f"  fill:  {pct}%",
    ]
    return SlashResult.ok("\n".join(rows))


def _daemon(line: str, ctx: SlashContext) -> SlashResult:
    """Open the daemon control panel (the `DaemonPickerScreen`) as a modal
    over the chat — start/stop/restart/delete daemons without leaving the TUI."""
    del line, ctx
    return SlashResult(open_picker="daemon")


def _status(line: str, ctx: SlashContext) -> SlashResult:
    """One-screen snapshot of the TUI: model, mode, session, provider,
    busy, queue depth. Useful when handing the machine to a fresh session
    and you need to know what's loaded."""
    del line
    st = ctx.state
    rows = [
        "status:",
        f"  model:    {st.model or '<none>'}",
        f"  provider: {st.provider_name or '<none>'}",
        f"  mode:     {st.mode}",
        f"  session:  {st.session_id or '<no session yet>'}",
        f"  busy:     {'yes' if st.busy else 'no'}",
        f"  queue:    {len(st.queue)} pending",
    ]
    return SlashResult.ok("\n".join(rows))


# ---------------- /insights ----------------


def _filter_and_limit(line: str, default_limit: int = 10) -> tuple[str | None, int]:
    """`/insights` and `/rules` arguments: `[<filter>|all] [<N>]`."""
    parts = (line or "").strip().split()
    if not parts:
        return None, default_limit
    first = parts[0].lower()
    limit = _parse_int(parts[1], default_limit) if len(parts) > 1 else default_limit
    return (None if first == "all" else first), limit


def _query_memory(ctx: SlashContext, command: str, fetch: Callable[[Any], list]) -> Any:
    """Run `fetch(connection)` against the project's memory store; a store
    that won't open comes back as the command's error result."""
    from veles.core.memory import aio
    from veles.core.memory.store import open_store

    try:
        store = open_store(ctx.project)
    except Exception as exc:
        return SlashResult.err(f"{command}: cannot open memory.db: {exc}")
    try:
        return fetch(store.raw())
    finally:
        aio.submit(store.close())


def _insights(line: str, ctx: SlashContext) -> SlashResult:
    """Show recent rows from the M119 `insights` table.

    Surfaces categories the user actually wants to act on:
    - **setup-hint** — embedding backend not configured (M-embedding)
    - **skill-suggestion** — pattern detector found a recipe
      (M121d hook surfaces these from `surface_skill_suggestions`)
    - **manager-report** — mini-reports the manager writes at the
      end of a multi-agent run (M122 `mini_report`)
    - **format / do / dont / preference** — generic insight categories
      written by insight_extractor (Curator → SQL bridge)

    Default shows 10 most recent across all categories. `/insights
    <category>` filters to one. `/insights all <N>` shows up to N rows.
    """
    from veles.core.memory.inspectors import recent_insights

    category_filter, limit = _filter_and_limit(line)
    rows = _query_memory(
        ctx, "/insights", lambda c: recent_insights(c, category=category_filter, limit=limit)
    )
    if isinstance(rows, SlashResult):
        return rows

    if not rows:
        scope = f"category {category_filter!r}" if category_filter else "any category"
        return SlashResult.ok(f"no insights yet ({scope}).")

    header_bits = [f"insights (latest {len(rows)}"]
    if category_filter:
        header_bits.append(f", category={category_filter}")
    header_bits.append("):")
    out_lines = ["".join(header_bits)]
    for row in rows:
        ts = local_stamp(row.created_at) if row.created_at else "—"
        cat = row.category or "—"
        title = row.title or "(no title)"
        # M260: a hidden row is still listed — the inspector's job is to show
        # what memory holds, and "why did the agent stop using this?" is only
        # answerable if the reason is visible next to the fact.
        hidden = f"  (hidden: {row.hidden_reason or 'unspecified'})" if row.hidden else ""
        out_lines.append(f"  [{cat}] {title}  · {ts}{hidden}")
    out_lines.append("")
    out_lines.append("Filter by category: /insights setup-hint | skill-suggestion | manager-report")
    return SlashResult.ok("\n".join(out_lines))


# ---------------- /rules ----------------


def _rules(line: str, ctx: SlashContext) -> SlashResult:
    """Show recent rows from the M119 `rules` table.

    Rules are behavioral preferences the agent should follow across
    sessions — extracted by the curator (`memory_save_rule`) or
    written explicitly via `/rules add` (future).

    Default shows 10 most recent across all kinds. `/rules <kind>`
    filters to one of `format`, `do`, `dont`, `preference`.
    `/rules all <N>` shows up to N rows.
    """
    from veles.core.memory.inspectors import recent_rules

    kind_filter, limit = _filter_and_limit(line)
    rows = _query_memory(ctx, "/rules", lambda c: recent_rules(c, kind=kind_filter, limit=limit))
    if isinstance(rows, SlashResult):
        return rows

    if not rows:
        scope = f"kind {kind_filter!r}" if kind_filter else "any kind"
        return SlashResult.ok(f"no rules yet ({scope}).")

    header_bits = [f"rules (latest {len(rows)}"]
    if kind_filter:
        header_bits.append(f", kind={kind_filter}")
    header_bits.append("):")
    out_lines = ["".join(header_bits)]
    for row in rows:
        ts = local_stamp(row.created_at) if row.created_at else "—"
        kind = row.kind or "—"
        body = (row.body or "(no body)").strip()
        if len(body) > 120:
            body = body[:117] + "…"
        src = row.source or "—"
        out_lines.append(f"  [{kind}] {body}  · {src} · {ts}")
    out_lines.append("")
    out_lines.append("Filter by kind: /rules format | do | dont | preference")
    return SlashResult.ok("\n".join(out_lines))


# ---------------- /self-doc ----------------


def _self_doc(line: str, ctx: SlashContext) -> SlashResult:
    del line
    try:
        from veles.core.safety import scan_for_injection
        from veles.core.self_doc import refresh_self_doc

        rel = refresh_self_doc(ctx.project)
        raw = (ctx.project.root / rel).read_text(encoding="utf-8", errors="replace")
        content, _ = scan_for_injection(raw, source_label=rel)
    except Exception as exc:
        return SlashResult.err(f"self-doc failed: {exc}")
    return SlashResult.ok(content)


# ---------------- registry assembly ----------------


def build_default_registry(project: Project | None = None) -> SlashRegistry:
    """Wires every shipped command. New phases extend the registry by
    importing this and calling `register` on the returned instance.

    `/wiki` is registered only when the active layout enables the wiki engine
    (so it never shows in `/help` or completion on bare/notes layouts). When
    `project` is None (e.g. unit tests), the wiki command is kept — the
    omission is opt-out, scoped to a project that explicitly has no wiki."""
    from veles.core.layout.engines import wiki_enabled

    wiki_on = project is None or wiki_enabled(project)

    reg = SlashRegistry()

    reg.register("/help", lambda _line, _ctx: _help(reg), summary="show this help", aliases=("/h",))
    reg.register("/quit", _quit, summary="exit (or Ctrl+D)", aliases=("/q", "/exit"))
    reg.register("/clear", _clear, summary="start a fresh session", aliases=("/new",))
    reg.register("/session", _session, summary="print current session id")
    reg.register("/sessions", _sessions, summary="list recent sessions and resume one")
    reg.register(
        "/resume", _resume, summary="resume a session by id prefix", usage="/resume <id-prefix>"
    )
    reg.register("/history", _history, summary="list recent sessions", usage="/history [N]")
    reg.register(
        "/errors", _errors, summary="errors from this session, plus earlier runs in the last 24h"
    )

    save_summary = (
        "save last answer as wiki/queries/<slug>.md"
        if wiki_on
        else "save last answer to project memory"
    )
    reg.register("/save", _save, summary=save_summary, usage="/save <slug>")

    if wiki_on:
        reg.register(
            "/wiki",
            _wiki,
            summary="add <path|url>: ingest a source · query <q>: answer from the wiki",
            usage="/wiki add|query <arg>",
        )

    reg.register("/model", _model, summary="show or set the active model", usage="/model [<id>]")
    reg.register(
        "/theme", _theme, summary="show or set the active TUI theme", usage="/theme [<name>]"
    )
    reg.register(
        "/mode",
        _mode,
        summary="show or set the mode (auto|planning|writing|goal)",
        usage="/mode [<name>]",
    )
    reg.register(
        "/schema",
        _schema,
        summary="inspect or fix AGENTS.md sections",
        usage="/schema [validate|fix]",
    )
    reg.register("/self-doc", _self_doc, summary="refresh project self-documentation")
    reg.register("/tokens", _tokens, summary="per-session and per-turn token totals")
    reg.register("/context", _context, summary="current context size vs model window")
    reg.register("/status", _status, summary="snapshot: model/mode/session/provider/busy/queue")
    reg.register(
        "/insights",
        _insights,
        summary="recent insights (skill suggestions, setup hints, manager reports)",
        usage="/insights [category] [N]",
    )
    reg.register(
        "/rules",
        _rules,
        summary="recent behavioral rules (format, do, dont, preference)",
        usage="/rules [kind] [N]",
    )
    reg.register("/daemon", _daemon, summary="open the daemon control panel")

    return reg

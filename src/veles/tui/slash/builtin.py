"""Slash-commands as pure handlers (line, ctx) -> SlashResult.

Removed in M80: `/load`, `/show`, `/search`, `/theme`, `/init`. Sessions
and themes are now picker-only (Ctrl+R / Ctrl+T). Project init is
handled by the project wizard on first run (M82).

The dispatcher in `registry.py` strips the leading `/` and command word
before calling each handler — every handler receives just the remaining
text in `line`.
"""

from __future__ import annotations

import contextlib
import datetime as dt
from typing import TYPE_CHECKING

from veles.tui.slash.registry import SlashContext, SlashRegistry, SlashResult

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


def _title_from_text(text: str) -> str:
    """First markdown heading (or first non-empty line, trimmed)."""
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("#"):
            return stripped.lstrip("# ").strip()
        return stripped[:80]
    return ""


def _fmt_ts(ts: float) -> str:
    return dt.datetime.fromtimestamp(ts, tz=dt.UTC).strftime("%Y-%m-%d %H:%M")


# ---------------- basics ----------------


def _help(line: str, ctx: SlashContext) -> SlashResult:
    del line
    from veles.core.layout.engines import wiki_enabled

    wiki_on = ctx.project is not None and wiki_enabled(ctx.project)
    save_help = (
        "  /save <slug>                 save last answer as wiki/queries/<slug>.md"
        if wiki_on
        else "  /save <slug>                 save last answer to project memory"
    )
    rows = [
        "Slash commands:",
        "  /help                        show this help",
        "  /quit, /q, /exit             exit the TUI",
        "  /clear                       start a fresh session (clears chat)",
        "  /session                     print current session id",
        save_help,
        "  /history [N]                 list recent sessions (default 20)",
    ]
    if wiki_on:
        rows += [
            "  /wiki add <path|url>         agent ingests a source into the wiki",
            "  /wiki query <question>       agent answers from the wiki",
        ]
    rows += [
        "  /model [<id>]                show or set the active model",
        "  /mode [<name>]               show or set the active mode (Shift+Tab cycles)",
        "                               modes: auto, planning, writing, goal",
        "  /schema [validate|fix]       inspect or fix AGENTS.md sections",
        "  /self-doc                    refresh project self-documentation",
        "  /tokens                      per-session and per-turn token totals",
        "  /context                     current context size vs model window",
        "  /status                      snapshot: model/mode/session/provider/busy/queue",
        "  /insights [category] [N]     recent insights (setup-hint, skill-suggestion, …)",
        "  /rules [kind] [N]            recent behavioral rules (format, do, dont, preference)",
        "",
        "Hotkeys:",
        "  Ctrl+R                       open session picker",
        "  Ctrl+T                       open theme picker",
        "  Shift+Tab                    cycle mode",
        "  Mouse wheel / trackpad       scroll the chat (back to bottom re-arms follow)",
        "  Drag-select output           selects text (does NOT copy on its own)",
        "  ⌘C (macOS) / Ctrl+Shift+C    copy the current selection to the clipboard",
        "  Option+drag then ⌘C          native terminal select+copy (iTerm2/macOS)",
        "  (keyboard focus stays on the input; set VELES_TUI_MOUSE=0 to disable the wheel)",
    ]
    return SlashResult.ok("\n".join(rows))


def _quit(line: str, ctx: SlashContext) -> SlashResult:
    del line, ctx
    return SlashResult(quit=True)


def _clear(line: str, ctx: SlashContext) -> SlashResult:
    del line
    ctx.state.session_id = None
    ctx.state.last_assistant_text = None
    return SlashResult(clear_chat=True, text="session cleared")


def _session(line: str, ctx: SlashContext) -> SlashResult:
    del line
    return SlashResult.ok(f"session={ctx.state.session_id or '<no session yet>'}")


# ---------------- save / history / load / show ----------------


def _save(line: str, ctx: SlashContext) -> SlashResult:
    """M87 shapes:
    - `/save` (no args) — list pending insight candidates the periodic
      extractor surfaced; user reruns with a slug to commit.
    - `/save <slug>` — if the slug matches a pending candidate, save
      it into the project's insight memory (M161: SQL row + rendered
      view under `.veles/memory/insights/`). Otherwise fall back to
      the legacy behaviour: save the last assistant reply to
      `wiki/queries/<slug>.md` (user content).
    """
    from veles.core.layout.engines import wiki_enabled

    candidates = list(ctx.state.insight_candidates)
    if not line:
        if not candidates:
            return SlashResult.err("/save needs a slug, e.g. `/save graph-traversal-notes`")
        rows = [f"insight candidates ({len(candidates)}). Run `/save <slug>` to keep one:"]
        for slug, title, _body in candidates:
            rows.append(f"  - {slug}  —  {title}")
        return SlashResult.ok("\n".join(rows))

    slug = line.split()[0]
    # First, try matching a pending candidate.
    for cand_slug, title, body in candidates:
        if cand_slug == slug:
            from veles.core.memory.artefacts import append_memory_log
            from veles.core.tools.builtin.memory_save import save_insight_row

            rid = save_insight_row(title=title, body=body, category="tui-save", project=ctx.project)
            if rid == 0:
                return SlashResult.err("/save failed: could not write insight to memory.db")
            with contextlib.suppress(Exception):
                append_memory_log(ctx.project, op="tui-save-insight", summary=f"-> insight #{rid}")
            ctx.state.insight_candidates = [c for c in candidates if c[0] != slug]
            return SlashResult.ok(f"saved insight #{rid}")
    # Fall back to saving the last assistant reply.
    last = ctx.state.last_assistant_text
    if not last or not last.strip():
        return SlashResult.err("/save: nothing to save yet (no assistant response in this run)")
    title = _title_from_text(last) or slug.replace("-", " ").title()

    # On layouts without the wiki engine (bare/notes), there is no
    # `wiki/queries/` to write to — keep the reply as a memory insight
    # instead of crashing on a Wiki the layout never created.
    if not wiki_enabled(ctx.project):
        from veles.core.memory.artefacts import append_memory_log
        from veles.core.tools.builtin.memory_save import save_insight_row

        rid = save_insight_row(title=title, body=last, category="tui-save", project=ctx.project)
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
        rows.append(
            f"{marker}{info.id}  {_fmt_ts(info.last_activity_at)}  turns={info.turn_count}  {title}"
        )
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
    busy, queue depth, insight candidates. Useful when handing the
    machine to a fresh session and you need to know what's loaded."""
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
        f"  insights: {len(st.insight_candidates)} candidate(s)",
    ]
    return SlashResult.ok("\n".join(rows))


# ---------------- /insights ----------------


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
    from veles.core.memory import SessionStore

    parts = (line or "").strip().split()
    category_filter: str | None = None
    limit = 10
    if parts:
        first = parts[0].lower()
        if first == "all":
            if len(parts) > 1:
                limit = _parse_int(parts[1], limit)
        else:
            category_filter = first
            if len(parts) > 1:
                limit = _parse_int(parts[1], limit)

    try:
        store = SessionStore(ctx.project.memory_db_path)
    except Exception as exc:
        return SlashResult.err(f"/insights: cannot open memory.db: {exc}")
    try:
        if category_filter:
            rows = store._conn.execute(
                "SELECT id, title, category, created_at FROM insights"
                " WHERE category = ?"
                " ORDER BY created_at DESC, id DESC LIMIT ?",
                (category_filter, limit),
            ).fetchall()
        else:
            rows = store._conn.execute(
                "SELECT id, title, category, created_at FROM insights"
                " ORDER BY created_at DESC, id DESC LIMIT ?",
                (limit,),
            ).fetchall()
    finally:
        store._conn.close()

    if not rows:
        scope = f"category {category_filter!r}" if category_filter else "any category"
        return SlashResult.ok(f"no insights yet ({scope}).")

    header_bits = [f"insights (latest {len(rows)}"]
    if category_filter:
        header_bits.append(f", category={category_filter}")
    header_bits.append("):")
    out_lines = ["".join(header_bits)]
    for row in rows:
        ts = _fmt_ts(row["created_at"]) if row["created_at"] else "—"
        cat = row["category"] or "—"
        title = row["title"] or "(no title)"
        out_lines.append(f"  [{cat}] {title}  · {ts}")
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
    from veles.core.memory import SessionStore

    parts = (line or "").strip().split()
    kind_filter: str | None = None
    limit = 10
    if parts:
        first = parts[0].lower()
        if first == "all":
            if len(parts) > 1:
                limit = _parse_int(parts[1], limit)
        else:
            kind_filter = first
            if len(parts) > 1:
                limit = _parse_int(parts[1], limit)

    try:
        store = SessionStore(ctx.project.memory_db_path)
    except Exception as exc:
        return SlashResult.err(f"/rules: cannot open memory.db: {exc}")
    try:
        if kind_filter:
            rows = store._conn.execute(
                "SELECT id, kind, body, source, created_at FROM rules"
                " WHERE kind = ?"
                " ORDER BY created_at DESC, id DESC LIMIT ?",
                (kind_filter, limit),
            ).fetchall()
        else:
            rows = store._conn.execute(
                "SELECT id, kind, body, source, created_at FROM rules"
                " ORDER BY created_at DESC, id DESC LIMIT ?",
                (limit,),
            ).fetchall()
    finally:
        store._conn.close()

    if not rows:
        scope = f"kind {kind_filter!r}" if kind_filter else "any kind"
        return SlashResult.ok(f"no rules yet ({scope}).")

    header_bits = [f"rules (latest {len(rows)}"]
    if kind_filter:
        header_bits.append(f", kind={kind_filter}")
    header_bits.append("):")
    out_lines = ["".join(header_bits)]
    for row in rows:
        ts = _fmt_ts(row["created_at"]) if row["created_at"] else "—"
        kind = row["kind"] or "—"
        body = (row["body"] or "(no body)").strip()
        if len(body) > 120:
            body = body[:117] + "…"
        src = row["source"] or "—"
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

    reg.register("/help", _help, summary="show this help")
    reg.register(
        "/quit",
        _quit,
        summary="exit the TUI",
        aliases=("/q", "/exit"),
    )
    reg.register("/clear", _clear, summary="start a fresh session")
    reg.register("/session", _session, summary="print current session id")

    save_summary = (
        "save last answer as wiki/queries/<slug>.md" if wiki_on else "save last answer to memory"
    )
    reg.register("/save", _save, summary=save_summary)
    reg.register("/history", _history, summary="list recent sessions")

    if wiki_on:
        reg.register("/wiki", _wiki, summary="wiki: add <path|url> | query <question>")

    reg.register("/model", _model, summary="show or set the active model")
    reg.register("/mode", _mode, summary="show or set the active mode (auto|planning|writing|goal)")
    reg.register("/schema", _schema, summary="schema: validate | fix")
    reg.register("/self-doc", _self_doc, summary="refresh project self-documentation")

    # M115.1: dedicated inspector commands (VISION §7.2).
    reg.register("/tokens", _tokens, summary="per-session and per-turn token totals")
    reg.register("/context", _context, summary="current context size vs model window")
    reg.register("/status", _status, summary="snapshot: model/mode/session/provider/busy/queue")
    # M-insights: surface skill suggestions + setup hints + manager
    # reports from the M119 `insights` table.
    reg.register(
        "/insights",
        _insights,
        summary="recent insights (skill suggestions, setup hints, manager reports)",
    )
    # M125: surface behavioral rules curator extracts from sessions.
    reg.register(
        "/rules",
        _rules,
        summary="recent behavioral rules (format, do, dont, preference)",
    )
    # M138: open the daemon control panel (start/stop/restart/delete) from the TUI.
    reg.register("/daemon", _daemon, summary="open the daemon control panel")

    return reg

"""Rendering a turn in the inline REPL: streamed Markdown blocks and edit diffs.

`_make_turn_callbacks` builds the callbacks a mode turn streams into; answer
text is rendered block by block (`_split_blocks` + `_render_answer`) so output is
both progressive and formatted, and file edits are previewed as coloured diffs.
"""

from __future__ import annotations


def _make_turn_callbacks(console, theme, errors: list[str], on_meta=None, stop_check=None):
    """Build (post, on_text, on_event) for a `ModeContext`, plus a holder for
    the final `RunResult`.

    These **stream by block**: answer tokens accumulate in a buffer, and each
    completed Markdown block (paragraph, list, table, fenced code) is rendered
    formatted as soon as its terminating blank line arrives — progressive AND
    formatted. `flush()` renders the trailing block at end of turn. Under the
    Application's `patch_stdout`, writes from the executor thread appear above
    the live input box.

    `on_meta(kind, text, *, tool_call_id="", error=None)` (optional) is the
    live-generation HUD sink: it receives ``("stream", chunk)`` for every
    answer chunk (so the app can show a running token estimate), ``("mode",
    text)`` on a mode switch, ``("tool", text, tool_call_id=...)`` on each tool
    call (the id starts the inspector's per-tool timer/status row), and
    ``("tool_result", "", tool_call_id=..., error=...)`` when that call's
    result comes back — the inspector uses it to mark the row done/failed and
    freeze its duration. When it's None (the fallback simple loop) mode
    switches print inline instead.

    Returns ``(post, on_text, on_event, holder, flush)``.
    """
    from veles.core.agent_events import AgentError, ChatDelta, SystemLine, TurnDone

    holder: dict[str, object] = {}
    buf = [""]  # mutable string cell shared across chunks

    def _emit(chunk: str) -> None:
        # Esc-to-stop: once the turn is cancelled, drop further tokens at the
        # source so visible output halts instantly (the cooperative cancel in
        # the agent loop only unwinds at the next ~100ms check).
        if stop_check is not None and stop_check():
            return
        if on_meta is not None:
            on_meta("stream", chunk)
        buf[0] += chunk
        blocks, buf[0] = _split_blocks(buf[0])
        for block in blocks:
            if block.strip():
                _render_answer(console, block)

    def flush() -> None:
        if stop_check is not None and stop_check():
            buf[0] = ""
            return
        if buf[0].strip():
            _render_answer(console, buf[0])
        buf[0] = ""

    def post(msg) -> None:
        if isinstance(msg, TurnDone):
            holder["result"] = msg.result
        elif isinstance(msg, SystemLine):
            # A mode switch etc. — into the live meta HUD, or inline as a dim
            # line when there's no HUD (fallback loop).
            if on_meta is not None:
                on_meta("mode", msg.text)
            else:
                console.print(f"  ⋅ {msg.text}", style=theme.muted, markup=False)
        elif isinstance(msg, ChatDelta):
            _emit(msg.text)
        elif isinstance(msg, AgentError):
            errors.append(str(msg.exc))
            console.print(f"\nerror: {msg.exc}", style=theme.error, markup=False)

    def on_text(text: str) -> None:
        _emit(text)

    def on_event(event) -> None:
        etype = getattr(event, "type", "")
        if etype == "round_usage":
            # Real cumulative output tokens for the HUD — a tool-call-only
            # turn streams no text, so the chars/4 estimate alone reads ≈0.
            if on_meta is not None:
                on_meta("usage", str(getattr(event, "cumulative_completion", 0)))
            return
        if etype == "tool_result":
            # Completion signal for the inspector's per-tool status/duration —
            # correlated with the tool_call above via tool_call_id. Carries no
            # display text of its own (the "tool" line was already pushed).
            if on_meta is not None:
                on_meta(
                    "tool_result",
                    "",
                    tool_call_id=getattr(event, "tool_call_id", "") or "",
                    error=getattr(event, "error", None),
                )
            return
        if etype != "tool_call":
            return
        name = getattr(event, "name", "")
        args = getattr(event, "arguments", {}) or {}
        if on_meta is not None:
            label = f"{name} {args.get('path', '')}".strip()
            on_meta("tool", label, tool_call_id=getattr(event, "tool_call_id", "") or "")
        # Preview file edits as a coloured diff, in order with the answer text.
        if name in ("edit_file", "write_file"):
            flush()  # render any pending answer text first, so ordering holds
            _render_edit_diff(console, theme, name, args)

    return post, on_text, on_event, holder, flush


def _render_answer(console, text: str) -> None:
    """Pretty-print a Markdown block — headings, lists, tables, links,
    bold/italic, and syntax-highlighted code blocks. Falls back to plain text
    if rendering ever raises so a glitch never eats the answer."""
    from rich.markdown import Markdown

    try:
        console.print(Markdown(text))
    except Exception:
        console.print(text, markup=False)


def _render_edit_diff(console, theme, name: str, arguments: dict) -> None:
    """Show a coloured unified diff (red = removed, green = added) for a file
    edit, in a code block. `edit_file` diffs its old_string → new_string;
    `write_file` diffs the file's current content → the new content (read before
    the write lands, since the tool-call event fires ahead of execution)."""
    import difflib

    from rich.syntax import Syntax

    path = str(arguments.get("path", "?"))
    if name == "edit_file":
        old = str(arguments.get("old_string", ""))
        new = str(arguments.get("new_string", ""))
    else:  # write_file
        new = str(arguments.get("content", ""))
        old = ""
        try:
            from veles.core.path_guard import resolve_safe

            p = resolve_safe(path)
            if p.is_file():
                old = p.read_text(encoding="utf-8")
        except Exception:
            old = ""

    diff = "\n".join(
        difflib.unified_diff(
            old.splitlines(),
            new.splitlines(),
            fromfile=f"a/{path}",
            tofile=f"b/{path}",
            lineterm="",
        )
    )
    if not diff.strip():
        return
    console.print(f"  ✎ {path}", style=theme.accent, markup=False)
    console.print(Syntax(diff, "diff", background_color="default", word_wrap=True))


def _split_blocks(buf: str) -> tuple[list[str], str]:
    """Split a growing Markdown buffer into (complete_blocks, remainder).

    Blocks are separated by blank lines OUTSIDE fenced code (``` / ~~~). The
    trailing incomplete block — everything after the last blank-line boundary,
    an unterminated code fence, or a partial final line — is the remainder,
    kept buffered until more tokens arrive. This lets the REPL render each
    finished block (paragraph, list, table, code fence) as it completes,
    streaming *and* formatted."""
    lines = buf.split("\n")
    tail = lines.pop()  # text after the final "\n" — a partial line (or "")
    blocks: list[str] = []
    cur: list[str] = []
    in_fence = False
    for line in lines:
        s = line.lstrip()
        if s.startswith(("```", "~~~")):
            in_fence = not in_fence
            cur.append(line)
        elif line.strip() == "" and not in_fence:
            if cur:
                blocks.append("\n".join(cur))
                cur = []
            # else: swallow extra blank separators
        else:
            cur.append(line)
    remainder = "\n".join([*cur, tail]) if cur else tail
    return blocks, remainder

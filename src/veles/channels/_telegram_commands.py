"""Slash-command handlers for the Telegram channel (M116).

VISION §7.3 requires channels-parity with TUI: every TUI slash-command
should be reachable through the channel's native command surface. For
Telegram that's `setMyCommands` (registers the menu) + handler dispatch
inside `_handle_update`.

This module holds the **handlers themselves** as pure functions of
(gateway, chat_key, args) → str. The Telegram gateway calls
`dispatch(text, gateway, chat_key)` from `_handle_update` and sends
the returned text via `_send_message`. Keeping handlers here (rather
than in `telegram.py`) lets the gateway file stay focused on transport
+ buffering, and lets future channels (Slack, web) share the same
handler set.

What's wired up now (M116.1):
- `/help` — list commands
- `/start`, `/reset` — gateway already owns these (greeting / clear
  session_map). Kept handler-less so the existing flow stays
  authoritative.
- `/session` — print active session_id from session_map
- `/status` — snapshot: session, project_root, whitelist size
- `/tokens`, `/context` — placeholder until daemon exposes per-session
  usage via the client API (deferred to M116.next; the commands exist
  in the menu so the surface area matches TUI).

What's deferred (M116.next sub-tasks):
- `/model`, `/mode`, `/history`, `/save`, `/wiki` — need to mutate
  daemon state through a not-yet-existing client API.
- `/goal`, `/dream` — long-running modes; need channel-side progress
  rendering plus a daemon API.
- Inline keyboards for clarification questions (`FreeformAnswer`
  mirror of M115.4) — separate sub-task once a manager-spawned
  worker actually emits a clarification event.
"""

from __future__ import annotations

import contextlib
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from veles.channels.telegram import TelegramGateway

# Handler signature: `(gateway, chat_key, args) -> reply_text`.
# Args is the substring after the command (e.g. for `/model gpt-4o`
# args == "gpt-4o"). Empty string when bare command.
CommandHandler = Callable[["TelegramGateway", str, str], Awaitable[str]]


async def _cmd_help(gateway: TelegramGateway, chat_key: str, args: str) -> str:
    del gateway, chat_key, args
    return (
        "<b>Veles bot — commands</b>\n\n"
        "/help — this list\n"
        "/start — greeting\n"
        "/reset — clear conversation history\n"
        "/session — show current session id\n"
        "/status — model / mode / session / connection snapshot\n"
        "/mode — list available agent modes\n"
        "/insights [category] — recent insights (curated sessions, skill suggestions)\n"
        "/rules [kind] — recent behavioral rules (preferences, dont)\n"
        "/goal &lt;task&gt; — long-running goal mode (decompose + iterate)\n"
        "/dream — trigger memory consolidation pass\n"
        "/tokens — per-session token totals (work in progress)\n"
        "/context — context window vs limit (work in progress)\n\n"
        "Just send a message to chat with the agent."
    )


async def _cmd_session(gateway: TelegramGateway, chat_key: str, args: str) -> str:
    del args
    sid = gateway.session_map.get(chat_key)
    if sid:
        return f"session: <code>{sid}</code>"
    return "session: <i>none yet</i> — send a message to start one"


async def _cmd_status(gateway: TelegramGateway, chat_key: str, args: str) -> str:
    del args
    sid = gateway.session_map.get(chat_key) or "—"
    proj = str(gateway.project_root) if gateway.project_root is not None else "—"
    wl = f"{len(gateway.whitelist)} entries" if gateway.whitelist else "open (no whitelist)"
    attach = str(gateway.attachment_dir) if gateway.attachment_dir is not None else "—"
    return (
        "<b>status</b>\n"
        f"  session:        <code>{sid}</code>\n"
        f"  project_root:   <code>{proj}</code>\n"
        f"  whitelist:      {wl}\n"
        f"  attachment_dir: <code>{attach}</code>"
    )


async def _cmd_tokens_placeholder(gateway: TelegramGateway, chat_key: str, args: str) -> str:
    del gateway, chat_key, args
    return (
        "<b>tokens</b>\n"
        "Per-session token totals are not exposed via the daemon's HTTP "
        "API yet. Tracked in the TUI via <code>/tokens</code> — see "
        "MILESTONES.md M116 follow-up for the planned bot mirror."
    )


async def _cmd_context_placeholder(gateway: TelegramGateway, chat_key: str, args: str) -> str:
    del gateway, chat_key, args
    return (
        "<b>context</b>\n"
        "Per-session context window usage isn't exposed via the daemon's "
        "HTTP API yet. Tracked in the TUI via <code>/context</code> — "
        "see MILESTONES.md M116 follow-up for the planned bot mirror."
    )


# ---- M116b: agent modes via slash ----


async def _cmd_goal(gateway: TelegramGateway, chat_key: str, args: str) -> str:
    """Forward the user's goal description as an agent prompt prefixed
    with a goal-mode marker the daemon factory reads. Until M122c wires
    the full FSM through the channels API, the prompt prefix is the
    contract: the agent sees "[GOAL MODE] <task>" and proceeds with
    that framing (the daemon's mode resolver upgrades to GoalMode when
    it sees the marker)."""
    task = args.strip()
    if not task:
        return (
            "<b>/goal &lt;task&gt;</b>\n"
            "Run the agent in long-running goal-mode: it decomposes, "
            "explores, iterates until done. Pass the task description "
            "after the command, e.g. <code>/goal write a deploy script "
            "for the staging env</code>."
        )
    # We just queue the agent prompt — the actual long-loop FSM
    # behaviour lives in `core/modes/goal.py` and is reached through
    # the daemon's factory (M71+). The marker keeps this path simple
    # while M122c lands a proper channel-side progress mirror.
    try:
        await gateway.daemon_client.submit_run(  # type: ignore[attr-defined]
            f"[GOAL MODE] {task}",
            session_id=gateway.session_map.get(chat_key),
        )
    except Exception as exc:
        return f"could not start goal-mode run: {exc}"
    return (
        f"started goal-mode run for: <code>{task[:80]}</code>\n"
        "I'll send progress updates as the agent works. Reply with "
        "<code>/status</code> to check session state."
    )


# M127: the Telegram `/model` picker (`MODEL_PAGE_SIZE`, `_render_model_page`,
# `_cmd_model`) was removed — model/provider are fixed at daemon launch from
# config and can't be switched from Telegram. `/mode` keeps `chat_key_to_int`.


def chat_key_to_int(chat_key: str) -> int:
    """Telegram chat IDs are numeric; SessionMap stores them as str."""
    try:
        return int(chat_key)
    except (TypeError, ValueError):
        return 0


async def _cmd_mode(gateway: TelegramGateway, chat_key: str, args: str) -> str:
    """M126: list agent modes as inline keyboard buttons. Tapping
    PATCHes the session's mode override."""
    del args

    session_id = gateway.session_map.get(chat_key)
    if not session_id:
        return "<i>send a message first to start a session — then /mode can switch its mode.</i>"

    modes = [
        ("auto", "classifier picks per turn"),
        ("planning", "multi-step planning"),
        ("writing", "single-turn writer"),
        ("goal", "long-running goal loop"),
    ]
    buttons = [
        [{"text": f"{name} — {desc}", "callback_data": f"mo:{name}"}] for name, desc in modes
    ]
    body = (
        "<b>Pick a mode</b> — applies to this chat's session.\n"
        "Change takes effect on the next message you send."
    )
    try:
        await gateway._send_message(
            chat_key_to_int(chat_key),
            body,
            reply_markup={"inline_keyboard": buttons},
        )
    except Exception as exc:
        return f"could not send mode picker: {exc}"
    return ""


def _resolve_project(gateway: TelegramGateway):
    """Resolve the active project from the gateway's `project_root`.
    Returns None when no root is configured or the path is invalid."""
    if gateway.project_root is None:
        return None
    try:
        from veles.core.project import load_project

        return load_project(gateway.project_root)
    except Exception:
        return None


async def _cmd_insights(gateway: TelegramGateway, chat_key: str, args: str) -> str:
    """List recent rows from the M119 `insights` table — mirrors the
    TUI `/insights` slash. Optional category filter as the first arg."""
    del chat_key
    from veles.core.memory import SessionStore

    parts = args.strip().split()
    category_filter = parts[0].lower() if parts else None
    limit = 10
    if len(parts) > 1:
        with contextlib.suppress(ValueError):
            limit = max(1, min(50, int(parts[1])))

    project = _resolve_project(gateway)
    if project is None:
        return "<i>no active project — cannot query insights</i>"
    try:
        store = SessionStore(project.memory_db_path)
    except Exception as exc:
        return f"could not open memory.db: {exc}"
    try:
        if category_filter and category_filter != "all":
            rows = store._conn.execute(
                "SELECT title, category, created_at FROM insights"
                " WHERE category = ?"
                " ORDER BY created_at DESC, id DESC LIMIT ?",
                (category_filter, limit),
            ).fetchall()
        else:
            rows = store._conn.execute(
                "SELECT title, category, created_at FROM insights"
                " ORDER BY created_at DESC, id DESC LIMIT ?",
                (limit,),
            ).fetchall()
    finally:
        store._conn.close()
    if not rows:
        scope = f"category={category_filter}" if category_filter else "any category"
        return f"<i>no insights yet ({scope}).</i>"
    out = [f"<b>Insights (latest {len(rows)})</b>", ""]
    for r in rows:
        cat = r["category"] or "—"
        title = r["title"] or "(no title)"
        out.append(f"• [<code>{cat}</code>] {title}")
    return "\n".join(out)


async def _cmd_rules(gateway: TelegramGateway, chat_key: str, args: str) -> str:
    """List recent rows from the M119 `rules` table — mirrors the TUI
    `/rules` slash. Optional kind filter as the first arg."""
    del chat_key
    from veles.core.memory import SessionStore

    parts = args.strip().split()
    kind_filter = parts[0].lower() if parts else None
    limit = 10
    if len(parts) > 1:
        with contextlib.suppress(ValueError):
            limit = max(1, min(50, int(parts[1])))

    project = _resolve_project(gateway)
    if project is None:
        return "<i>no active project — cannot query rules</i>"
    try:
        store = SessionStore(project.memory_db_path)
    except Exception as exc:
        return f"could not open memory.db: {exc}"
    try:
        if kind_filter and kind_filter != "all":
            rows = store._conn.execute(
                "SELECT kind, body, source, created_at FROM rules"
                " WHERE kind = ?"
                " ORDER BY created_at DESC, id DESC LIMIT ?",
                (kind_filter, limit),
            ).fetchall()
        else:
            rows = store._conn.execute(
                "SELECT kind, body, source, created_at FROM rules"
                " ORDER BY created_at DESC, id DESC LIMIT ?",
                (limit,),
            ).fetchall()
    finally:
        store._conn.close()
    if not rows:
        scope = f"kind={kind_filter}" if kind_filter else "any kind"
        return f"<i>no rules yet ({scope}).</i>"
    out = [f"<b>Rules (latest {len(rows)})</b>", ""]
    for r in rows:
        kind = r["kind"] or "—"
        body = (r["body"] or "").strip()
        if len(body) > 100:
            body = body[:97] + "…"
        out.append(f"• [<code>{kind}</code>] {body}")
    return "\n".join(out)


async def _cmd_dream(gateway: TelegramGateway, chat_key: str, args: str) -> str:
    """Trigger one consolidation pass on the project memory. Same
    daemon-side prompt-prefix contract as /goal — the marker upgrades
    to `dream` mode in the factory."""
    del args
    try:
        await gateway.daemon_client.submit_run(  # type: ignore[attr-defined]
            "[DREAM MODE] consolidate insights, lint wiki, prune stale claims",
            session_id=gateway.session_map.get(chat_key),
        )
    except Exception as exc:
        return f"could not start dream-mode run: {exc}"
    return (
        "started dream-mode consolidation. The agent will compact "
        "sessions into wiki, lint for contradictions, surface insight "
        "candidates. Use <code>/status</code> when it finishes."
    )


# Mapping cmd-without-slash → handler. Lookup is exact (no aliases yet).
_HANDLERS: dict[str, CommandHandler] = {
    "help": _cmd_help,
    "session": _cmd_session,
    "status": _cmd_status,
    "tokens": _cmd_tokens_placeholder,
    "context": _cmd_context_placeholder,
    "goal": _cmd_goal,
    "dream": _cmd_dream,
    "mode": _cmd_mode,
    "insights": _cmd_insights,
    "rules": _cmd_rules,
}


def parse_command(text: str) -> tuple[str, str] | None:
    """Parse `/<cmd> <args…>` from a Telegram text message.

    Returns `(cmd, args)` with `cmd` already lower-cased and stripped
    of the leading `/`, or `None` when the text isn't a command.
    Telegram allows `/cmd@BotName` — the `@BotName` suffix is
    stripped so the bot responds when addressed in a group.
    """
    stripped = text.strip()
    if not stripped.startswith("/"):
        return None
    body = stripped[1:].lstrip()
    if not body:
        return None
    head, _, args = body.partition(" ")
    cmd, _, _bot_at = head.partition("@")
    return cmd.lower(), args.strip()


def is_known_command(cmd: str) -> bool:
    """True when the gateway's existing flow (`/start`, `/reset`) or
    this module's dispatcher recognises the command. Used by the
    gateway to keep buffering disabled for any slash input."""
    return cmd in {"start", "reset"} or cmd in _HANDLERS


def all_command_names() -> list[str]:
    """Sorted union of every command name the gateway dispatcher
    recognises — including the gateway-owned `start`/`reset`. Useful
    for tests and the suggestion UI ("did you mean…?")."""
    return sorted({"start", "reset"} | set(_HANDLERS.keys()))


async def dispatch(gateway: TelegramGateway, chat_key: str, cmd: str, args: str) -> str | None:
    """Run the handler for `cmd`. Returns the reply text or `None` if
    the command isn't owned by this dispatcher (`/start` and `/reset`
    are owned by the gateway itself and return `None` here)."""
    handler = _HANDLERS.get(cmd)
    if handler is None:
        return None
    return await handler(gateway, chat_key, args)


def menu_descriptors() -> list[dict[str, str]]:
    """Payload for Telegram `setMyCommands` — populates the in-app
    command menu so users can discover commands via `/`. Order matters
    (it's what the bot menu shows top-to-bottom)."""
    return [
        {"command": "help", "description": "List available commands"},
        {"command": "status", "description": "Session / project snapshot"},
        {"command": "session", "description": "Show current session id"},
        {"command": "mode", "description": "List available agent modes"},
        {
            "command": "insights",
            "description": "Recent insights (skill suggestions, manager reports)",
        },
        {"command": "rules", "description": "Recent behavioral rules (preferences, dont)"},
        {"command": "goal", "description": "Run agent in long-running goal mode"},
        {"command": "dream", "description": "Trigger memory consolidation pass"},
        {"command": "tokens", "description": "Token totals (WIP)"},
        {"command": "context", "description": "Context window usage (WIP)"},
        {"command": "reset", "description": "Clear conversation history"},
    ]


__all__ = [
    "dispatch",
    "is_known_command",
    "menu_descriptors",
    "parse_command",
]

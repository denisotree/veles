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

import asyncio
import contextlib
import html
import re
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, Any

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
        "/mode — switch this chat's agent mode (default / auto / planning / writing)\n"
        "/insights [category] — recent insights (curated sessions, skill suggestions)\n"
        "/rules [kind] — recent behavioral rules (preferences, dont)\n"
        "/goal &lt;task&gt; — run a goal in this chat (/goal · /goal cancel · /goal resume)\n"
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
    """`/goal <task>` starts a goal in this chat (M280b).

    The chat switches to goal mode and the task goes in as an ordinary turn —
    same streaming, approval buttons and delivery as any message — so GoalMode
    opens with its interview; once the plan is confirmed the goal runs to its
    end within that turn. (M276 answered "not from Telegram yet": daemon turns
    had no agent modes until M280a.)

    `/goal` shows the chat's goal, `/goal cancel` cancels it at once — even
    mid-run, since commands don't wait for the chat's turn — and `/goal resume`
    continues one that stopped. The daemon answers all of it (`get_session` /
    `cancel_goal`), so a gateway without the project's files works too."""
    arg = args.strip()
    client: Any = gateway.daemon_client
    session_id = gateway.session_map.get(chat_key)
    goal = None
    if session_id:
        with contextlib.suppress(Exception):
            goal = (await client.get_session(session_id)).get("goal")

    if arg.lower() == "cancel":
        if not session_id or goal is None:
            return "No goal is running in this chat."
        try:
            await client.cancel_goal(session_id)
        except Exception as exc:
            return f"could not cancel the goal: {html.escape(str(exc))}"
        return "Goal cancelled. If it was working, it stops after the current step."
    if arg.lower() == "resume":
        if goal is None:
            return (
                "No goal to resume in this chat. After a daemon restart a chat forgets "
                "its goal — <code>veles goal list</code> and <code>veles goal resume "
                "&lt;id&gt;</code> on the host continue it."
            )
        await gateway._run_turn_serial(chat_key_to_int(chat_key), chat_key, "continue", mode="goal")
        return ""
    if not arg:
        if goal is None:
            return (
                "<b>/goal &lt;task&gt;</b>\n"
                "Starts a goal in this chat: I ask what I need to know, confirm a plan "
                "with you, then work until it is done or a budget runs out.\n"
                "/goal — status · /goal cancel · /goal resume"
            )
        return (
            f"<b>goal</b> <code>{html.escape(goal['id'])}</code> — {html.escape(goal['phase'])}\n"
            f"{html.escape(str(goal['objective'])[:300])}\n"
            f"steps {goal['steps_done']}/{goal['max_steps']} · "
            f"${goal['cost_spent_usd']:.2f}/${goal['max_cost_usd']:.2f}\n"
            "/goal cancel · /goal resume"
        )
    if goal is not None:
        return "A goal is already running in this chat — answer its question, or /goal cancel it."
    await gateway._run_turn_serial(chat_key_to_int(chat_key), chat_key, arg, mode="goal")
    return ""


# M127: the Telegram `/model` picker (`MODEL_PAGE_SIZE`, `_render_model_page`,
# `_cmd_model`) was removed — model/provider are fixed at daemon launch from
# config and can't be switched from Telegram. `/mode` keeps `chat_key_to_int`.


def chat_key_to_int(chat_key: str) -> int:
    """Telegram chat IDs are numeric; SessionMap stores them as str."""
    try:
        return int(chat_key)
    except (TypeError, ValueError):
        return 0


# What `/mode` offers. `goal` is not here: a goal starts with `/goal <task>`,
# which also gives the goal its objective.
_MODE_CHOICES = (
    ("default", "the agent answers directly"),
    ("auto", "decides per message: plan first, or act"),
    ("planning", "plans only, changes nothing"),
    ("writing", "acts directly with its tools"),
)


async def _cmd_mode(gateway: TelegramGateway, chat_key: str, args: str) -> str:
    """List agent modes as inline buttons, the chat's current one marked.
    Tapping PATCHes the session's mode, and since M280 the next turn runs in
    it (before, the choice was stored and ignored)."""
    del args

    session_id = gateway.session_map.get(chat_key)
    if not session_id:
        return "<i>send a message first to start a session — then /mode can switch its mode.</i>"

    client: Any = gateway.daemon_client
    try:
        current = (await client.get_session(session_id)).get("mode")
    except Exception:
        current = None  # the picker still works; only the mark is missing
    buttons = [
        [
            {
                "text": f"{'✓ ' if name == current else ''}{name} — {desc}",
                "callback_data": f"mo:{name}",
            }
        ]
        for name, desc in _MODE_CHOICES
    ]
    body = (
        "<b>Pick a mode</b> for this chat.\n"
        "It applies from your next message, until the daemon restarts."
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
    from veles.core.memory.inspect import recent_insights
    from veles.core.memory.store import open_store

    parts = args.strip().split()
    category_filter = parts[0].lower() if parts else None
    limit = 10
    if len(parts) > 1:
        with contextlib.suppress(ValueError):
            limit = max(1, min(50, int(parts[1])))

    project = _resolve_project(gateway)
    if project is None:
        return "<i>no active project — cannot query insights</i>"
    category = category_filter if category_filter and category_filter != "all" else None
    try:
        store = open_store(project)
    except Exception as exc:
        return f"could not open memory.db: {exc}"
    try:
        # These handlers already run on the gateway's event loop, so they await
        # the port directly — `aio.submit` refuses to block a running loop, and
        # the read itself goes to a thread rather than stalling every other
        # chat while SQLite works.
        rows = await asyncio.to_thread(recent_insights, store.raw(), category=category, limit=limit)
    finally:
        await store.close()
    if not rows:
        scope = f"category={category_filter}" if category_filter else "any category"
        return f"<i>no insights yet ({scope}).</i>"
    out = [f"<b>Insights (latest {len(rows)})</b>", ""]
    for r in rows:
        cat = r.category or "—"
        title = r.title or "(no title)"
        hidden = f" <i>(hidden: {r.hidden_reason or 'unspecified'})</i>" if r.hidden else ""
        out.append(f"• [<code>{cat}</code>] {title}{hidden}")
    return "\n".join(out)


async def _cmd_rules(gateway: TelegramGateway, chat_key: str, args: str) -> str:
    """List recent rows from the M119 `rules` table — mirrors the TUI
    `/rules` slash. Optional kind filter as the first arg."""
    del chat_key
    from veles.core.memory.inspect import recent_rules
    from veles.core.memory.store import open_store

    parts = args.strip().split()
    kind_filter = parts[0].lower() if parts else None
    limit = 10
    if len(parts) > 1:
        with contextlib.suppress(ValueError):
            limit = max(1, min(50, int(parts[1])))

    project = _resolve_project(gateway)
    if project is None:
        return "<i>no active project — cannot query rules</i>"
    kind = kind_filter if kind_filter and kind_filter != "all" else None
    try:
        store = open_store(project)
    except Exception as exc:
        return f"could not open memory.db: {exc}"
    try:
        rows = await asyncio.to_thread(recent_rules, store.raw(), kind=kind, limit=limit)
    finally:
        await store.close()
    if not rows:
        scope = f"kind={kind_filter}" if kind_filter else "any kind"
        return f"<i>no rules yet ({scope}).</i>"
    out = [f"<b>Rules (latest {len(rows)})</b>", ""]
    for r in rows:
        kind = r.kind or "—"
        body = (r.body or "").strip()
        if len(body) > 100:
            body = body[:97] + "…"
        out.append(f"• [<code>{kind}</code>] {body}")
    return "\n".join(out)


async def _cmd_dream(gateway: TelegramGateway, chat_key: str, args: str) -> str:
    """Run one consolidation pass on the project memory and report its result.

    M276: this used to submit "[DREAM MODE] …" as an ordinary chat prompt —
    nothing read the marker, so the agent just answered the words. Now it runs
    the daemon's own dream runner (the one the schedule uses) and waits: each
    update is handled in its own task, so the wait blocks nothing else."""
    del chat_key, args
    try:
        result = await gateway.daemon_client.run_dream()  # type: ignore[attr-defined]
    except Exception as exc:
        return f"could not run dream: {html.escape(str(exc))}"
    lines = [f"<b>dream</b> — {html.escape(str(result.get('summary', 'done')))}"]
    lines += [f"• {html.escape(str(note))}" for note in result.get("notes") or []]
    return "\n".join(lines)


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


# Telegram's own command grammar (Bot API `BotCommand.command`: "1-32
# characters. Can contain only lowercase English letters, digits and
# underscores"; users may type Latin letters in either case — checked against
# core.telegram.org on 2026-09-22). Matched after lower-casing.
_COMMAND_NAME = re.compile(r"[a-z0-9_]{1,32}")


def parse_command(text: str) -> tuple[str, str] | None:
    """Parse `/<cmd> <args…>` from a Telegram text message.

    Returns `(cmd, args)` with `cmd` already lower-cased and stripped
    of the leading `/`, or `None` when the text isn't a command.
    Telegram allows `/cmd@BotName` — the `@BotName` suffix is
    stripped so the bot responds when addressed in a group.

    M274: only a name Telegram itself would treat as a command counts.
    Anything else starting with `/` was parsed as a command and answered
    "Unknown command", so a message that merely *began* with a path —
    `/var/log/app.log why does it crash?` — never reached the agent.
    """
    stripped = text.strip()
    if not stripped.startswith("/"):
        return None
    head, _, args = stripped[1:].partition(" ")
    cmd, _, _bot_at = head.partition("@")
    cmd = cmd.lower()
    if not _COMMAND_NAME.fullmatch(cmd):
        return None
    return cmd, args.strip()


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
        {"command": "mode", "description": "Switch this chat's agent mode"},
        {
            "command": "insights",
            "description": "Recent insights (skill suggestions, manager reports)",
        },
        {"command": "rules", "description": "Recent behavioral rules (preferences, dont)"},
        {"command": "goal", "description": "Run a goal in this chat"},
        {"command": "dream", "description": "Run a memory consolidation pass now"},
        {"command": "tokens", "description": "Token totals (WIP)"},
        {"command": "context", "description": "Context window usage (WIP)"},
        {"command": "reset", "description": "Clear conversation history"},
    ]


__all__ = [
    "dispatch",
    "menu_descriptors",
    "parse_command",
]

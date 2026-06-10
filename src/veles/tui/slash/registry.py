"""Slash-command framework. Keeps the App layer free of command-specific
logic and lets future phases mount additional commands (e.g. plugin
hooks) by handing a `SlashRegistry` instance rather than monkey-patching
the app.

Two-step contract:
  - registration: `registry.register(name, handler, summary=…, …)`
  - dispatch: `registry.dispatch(line, ctx)` returns `SlashResult | None`

`None` means "unknown command"; the caller decides how to surface that
(currently: a one-line error in the chat log).

Handlers never touch the UI directly. They return a `SlashResult` whose
shape carries everything the App needs to render or react: plain text,
an error flag, a quit flag, or a clear-screen flag. This keeps every
command testable as a pure function of context + args.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from veles.core.memory import SessionStore
    from veles.core.project import Project
    from veles.tui.state import AppState


@dataclass(slots=True)
class SlashContext:
    """Read-only handles a slash command may need.

    State is mutable on purpose: a few commands (e.g. `/load`, `/clear`,
    `/model <id>`, `/theme use <name>`) flip session_id or model. The
    App reads back from `ctx.state` after dispatch to refresh widgets.
    """

    state: AppState
    project: Project
    store: SessionStore


@dataclass(slots=True)
class SlashResult:
    """What the App should do after dispatch finishes.

    A result usually carries `text` (rendered as a system line in the
    chat log). The `quit`, `clear_chat`, and `open_picker` fields are
    out-of-band signals that the App handles specially. Multiple flags
    can combine — e.g. `/clear` clears the chat and prints a
    confirmation.

    `open_picker` is the name of an overlay to push: `"sessions"`,
    `"models"`, or `"themes"`. The App maps each name to a
    `PickerScreen` subclass. Strings (rather than enums) keep handlers
    free of overlay imports — they declare *what* they want, the App
    decides *which* screen builds it."""

    text: str = ""
    is_error: bool = False
    quit: bool = False
    clear_chat: bool = False
    open_picker: str | None = None
    # M83: when set, the App submits this prompt to the agent right after
    # rendering `text`. Lets slash commands (e.g. `/wiki add`, `/wiki query`)
    # trigger a normal agent turn without dragging the App into the handler.
    submit_prompt: str | None = None

    @classmethod
    def ok(cls, text: str = "") -> SlashResult:
        return cls(text=text)

    @classmethod
    def err(cls, text: str) -> SlashResult:
        return cls(text=text, is_error=True)


SlashHandler = Callable[[str, SlashContext], SlashResult]


@dataclass(slots=True)
class SlashCommand:
    name: str  # canonical name including the leading slash, e.g. "/help"
    handler: SlashHandler
    summary: str
    usage: str = ""
    aliases: tuple[str, ...] = ()


@dataclass(slots=True)
class SlashRegistry:
    _commands: dict[str, SlashCommand] = field(default_factory=dict)
    _aliases: dict[str, str] = field(default_factory=dict)

    def register(
        self,
        name: str,
        handler: SlashHandler,
        *,
        summary: str,
        usage: str = "",
        aliases: tuple[str, ...] = (),
    ) -> None:
        cmd = SlashCommand(
            name=name, handler=handler, summary=summary, usage=usage, aliases=aliases
        )
        self._commands[name] = cmd
        for alias in aliases:
            self._aliases[alias] = name

    def dispatch(self, line: str, ctx: SlashContext) -> SlashResult | None:
        """Parse `line` (which begins with `/`) and route to the handler.
        Returns `None` if the command is unknown — the App turns that
        into a rendered error."""
        stripped = line.strip()
        if not stripped.startswith("/"):
            return SlashResult.err(f"not a slash command: {line!r}")
        parts = stripped.split(maxsplit=1)
        name = parts[0]
        rest = parts[1].strip() if len(parts) > 1 else ""
        canonical = self._aliases.get(name, name)
        cmd = self._commands.get(canonical)
        if cmd is None:
            return None
        return cmd.handler(rest, ctx)

    def commands(self) -> list[SlashCommand]:
        """Sorted list of commands for help rendering and completion."""
        return sorted(self._commands.values(), key=lambda c: c.name)

    def names(self) -> list[str]:
        """Canonical + alias names, sorted. Used by the slash completer."""
        return sorted([*self._commands.keys(), *self._aliases.keys()])

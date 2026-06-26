"""Scrolling chat history. Append-only.

Textual gives us `RichLog`, but it's line-oriented: each `write()` lays
down a finished line. Streaming a partial assistant reply token-by-token
needs a different shape — we want the *last* line to keep growing.

Approach: a `VerticalScroll` of one `Static` per logical message.
- A user turn appends one user-Static.
- The assistant's reply starts as an empty Static held on the widget;
  every `ChatDelta` rewrites its content with the accumulated buffer.
- On `TurnDone`, the streaming Static is sealed: its final content is
  re-rendered through `rich.markdown.Markdown` so tables, code blocks,
  GFM-style lists, and ` ```diff` chunks (Pygments diff-lexer →
  red/green) appear properly formatted. Streaming stays plain to keep
  per-delta layout cheap and avoid mid-stream markdown breakage.
"""

from __future__ import annotations

from rich.markdown import Markdown
from textual.containers import VerticalScroll
from textual.widgets import Static


class SelectableStatic(Static):
    """Static that opts into Textual's selection API.

    M109 made every ChatLog message individually selectable so the user
    can Shift+arrow through text and copy via the in-app selection (a
    fallback when terminal-native drag-select is unavailable). Marking
    `allow_select` on the subclass is cleaner than poking the attribute
    on each instance from `ChatLog._make_static` (the previous shape)."""

    allow_select = True


class ChatLog(VerticalScroll):
    DEFAULT_CSS = """
    ChatLog {
        background: $surface;
        padding: 0 1;
        /* Reserve a left edge so highlighting it on focus doesn't shift
           layout. M179: it turns accent when the chat pane has keyboard
           focus (read mode), so the user can see which pane is active. */
        border-left: thick $surface;
    }
    ChatLog:focus {
        border-left: thick $accent;
    }
    ChatLog > Static.veles-user {
        color: $accent;
        margin-top: 1;
    }
    ChatLog > Static.veles-assistant {
        color: $text;
        margin-top: 1;
    }
    ChatLog > Static.veles-error {
        color: $error;
        margin-top: 1;
    }
    ChatLog > Static.veles-system {
        color: $text-muted;
        margin-top: 1;
    }
    """

    def __init__(self) -> None:
        super().__init__(id="veles-chat-log")
        self._current_assistant: Static | None = None
        self._buffer = ""
        # Append-only plain-text mirror of every message that was
        # mounted. Tests inspect this directly; the production code only
        # reads it during dev debugging. Each entry is `(role, text)`.
        self.transcript: list[tuple[str, str]] = []
        # M176 follow-mode flag (see below).
        self._follow = True

    # ---- follow-mode (M176) ----
    #
    # Auto-scroll new output to the bottom only while `_follow` is on. The
    # user turns it OFF by scrolling up (the app's PageUp/Home/Ctrl+Home
    # actions and the mouse-wheel handlers call `pause_follow()`), and back
    # ON via End / a new user turn (`scroll_to_bottom()`). A boolean flag is
    # deterministic — unlike inferring "am I at the bottom?" from
    # `scroll_offset` vs `max_scroll_y`, which lags behind content growth by
    # a few lines mid-stream and would both flake tests and intermittently
    # drop auto-scroll in production.

    @property
    def following(self) -> bool:
        return self._follow

    def pause_follow(self) -> None:
        """Stop auto-scrolling (the user scrolled up to read earlier output)."""
        self._follow = False

    def scroll_to_bottom(self) -> None:
        """Jump to the newest output and re-arm following (End / new turn)."""
        self._follow = True
        self.scroll_end(animate=False)

    def _follow_if_armed(self) -> None:
        if self._follow:
            self.scroll_end(animate=False)

    # ---- public API ----

    def append_user(self, text: str) -> None:
        self._seal_assistant()
        self.transcript.append(("user", text))
        self.mount(SelectableStatic(self._render_user(text), classes="veles-user"))
        # A new turn always re-arms following — the user just sent input and
        # wants to watch the reply.
        self.scroll_to_bottom()

    def start_assistant(self) -> None:
        """Begin a new streaming assistant message. Idempotent: a no-op
        if one is already in progress (shouldn't happen but cheap to
        defend against)."""
        if self._current_assistant is not None:
            return
        self._buffer = ""
        self._current_assistant = SelectableStatic("assistant>", classes="veles-assistant")
        self.transcript.append(("assistant", ""))
        self.mount(self._current_assistant)
        self._follow_if_armed()

    def append_assistant_delta(self, chunk: str) -> None:
        if self._current_assistant is None:
            self.start_assistant()
        assert self._current_assistant is not None
        self._buffer += chunk
        self._current_assistant.update(self._render_assistant(self._buffer))
        # Keep transcript tail in sync with the growing buffer so tests
        # can read the assistant's full reply by the time TurnDone fires.
        if self.transcript and self.transcript[-1][0] == "assistant":
            self.transcript[-1] = ("assistant", self._buffer)
        self._follow_if_armed()

    def seal_assistant(self) -> None:
        """End-of-turn marker. Re-renders the streaming Static through
        Rich Markdown for the final view (tables, code blocks, diff
        coloring), then drops the streaming handle so the next delta
        opens a fresh Static instead of growing the previous one."""
        if self._current_assistant is not None and self._buffer.strip():
            self._current_assistant.update(Markdown(self._buffer, code_theme="monokai"))
        self._seal_assistant()

    def append_error(self, text: str) -> None:
        self._seal_assistant()
        self.transcript.append(("error", text))
        self.mount(SelectableStatic(f"error> {text}", classes="veles-error"))
        self._follow_if_armed()

    def append_system(self, text: str) -> None:
        """Render slash-command output and other meta info. Multi-line
        text is mounted as one Static so blank-line separators inside
        the output stay intact."""
        self._seal_assistant()
        self.transcript.append(("system", text))
        safe = text.replace("[", r"\[")
        self.mount(SelectableStatic(safe, classes="veles-system"))
        self._follow_if_armed()

    def clear_messages(self) -> None:
        """Drop every mounted message Static. Used by `/clear`."""
        self._seal_assistant()
        self.transcript.clear()
        for child in list(self.children):
            child.remove()

    # ---- mouse wheel (only active when VELES_TUI_MOUSE=1) ----

    def on_mouse_scroll_up(self, event) -> None:
        """Wheel-up means the user wants to read earlier output — stop
        auto-following. The container still performs the scroll (we don't
        stop the event)."""
        self.pause_follow()

    # ---- internals ----

    def _seal_assistant(self) -> None:
        self._current_assistant = None
        self._buffer = ""

    @staticmethod
    def _render_user(text: str) -> str:
        # Textual's `Static.update` accepts rich markup. We escape `[` to
        # avoid accidental tag interpretation in user-provided text.
        safe = text.replace("[", r"\[")
        return f"[bold]you>[/bold] {safe}"

    @staticmethod
    def _render_assistant(text: str) -> str:
        safe = text.replace("[", r"\[")
        return f"assistant> {safe}"

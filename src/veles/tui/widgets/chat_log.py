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

    # ---- follow-mode (M176) ----
    #
    # Auto-scroll only when the viewport is already at the bottom. Once the
    # user scrolls up to re-read earlier output, streaming deltas leave the
    # viewport put instead of yanking it back down — the cause of the
    # "I can't scroll the chat" complaint. A new user turn (append_user) and
    # an explicit End (scroll_to_bottom) re-arm following.

    def _at_bottom(self) -> bool:
        """True when the viewport sits at (or within a line of) the bottom.

        When there's nothing to scroll yet (`max_scroll_y == 0`) the chat is
        trivially at the bottom, so the first messages still auto-scroll.
        """
        return self.scroll_offset.y >= self.max_scroll_y - 1

    def scroll_to_bottom(self) -> None:
        """Jump to the newest output and re-arm following (End / new turn)."""
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
        follow = self._at_bottom()
        self._buffer = ""
        self._current_assistant = SelectableStatic("assistant>", classes="veles-assistant")
        self.transcript.append(("assistant", ""))
        self.mount(self._current_assistant)
        if follow:
            self.scroll_end(animate=False)

    def append_assistant_delta(self, chunk: str) -> None:
        if self._current_assistant is None:
            self.start_assistant()
        assert self._current_assistant is not None
        follow = self._at_bottom()
        self._buffer += chunk
        self._current_assistant.update(self._render_assistant(self._buffer))
        # Keep transcript tail in sync with the growing buffer so tests
        # can read the assistant's full reply by the time TurnDone fires.
        if self.transcript and self.transcript[-1][0] == "assistant":
            self.transcript[-1] = ("assistant", self._buffer)
        if follow:
            self.scroll_end(animate=False)

    def seal_assistant(self) -> None:
        """End-of-turn marker. Re-renders the streaming Static through
        Rich Markdown for the final view (tables, code blocks, diff
        coloring), then drops the streaming handle so the next delta
        opens a fresh Static instead of growing the previous one."""
        if self._current_assistant is not None and self._buffer.strip():
            self._current_assistant.update(Markdown(self._buffer, code_theme="monokai"))
        self._seal_assistant()

    def append_error(self, text: str) -> None:
        follow = self._at_bottom()
        self._seal_assistant()
        self.transcript.append(("error", text))
        self.mount(SelectableStatic(f"error> {text}", classes="veles-error"))
        if follow:
            self.scroll_end(animate=False)

    def append_system(self, text: str) -> None:
        """Render slash-command output and other meta info. Multi-line
        text is mounted as one Static so blank-line separators inside
        the output stay intact."""
        follow = self._at_bottom()
        self._seal_assistant()
        self.transcript.append(("system", text))
        safe = text.replace("[", r"\[")
        self.mount(SelectableStatic(safe, classes="veles-system"))
        if follow:
            self.scroll_end(animate=False)

    def clear_messages(self) -> None:
        """Drop every mounted message Static. Used by `/clear`."""
        self._seal_assistant()
        self.transcript.clear()
        for child in list(self.children):
            child.remove()

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

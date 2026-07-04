"""Root Textual application.

Layout (top → bottom):
    ChatLog          flex 1, scrolls
    Composer         3 rows, dock implicit
    StatusBar        1 row, dock bottom

Phase 1 keeps the widget set minimal: no inspector, no overlays, no
queue panel. Slash commands aren't dispatched yet — anything starting
with `/quit` or `/q` exits, everything else is sent to the agent as-is.
Phase 2 plugs in the registry.

The app receives an `agent_factory` rather than building the Agent
itself; the production path wires this in `veles.tui.run_tui`, tests
inject a stub that returns an Agent fed by a fake provider.
"""

from __future__ import annotations

import contextlib
from typing import ClassVar

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Vertical

from veles.core.memory import SessionStore
from veles.core.project import Project
from veles.core.session_state import AppState
from veles.tui import wire
from veles.tui.bridge import AgentBridge, AgentFactory
from veles.tui.completer import SlashCompleter
from veles.tui.history import InputHistory
from veles.tui.screens import (
    ModelPickerScreen,
    SessionPickerScreen,
    ThemePickerScreen,
)
from veles.tui.slash import SlashContext, SlashRegistry, build_default_registry
from veles.tui.theme_bridge import apply_to_app as apply_theme
from veles.tui.widgets.chat_log import ChatLog
from veles.tui.widgets.composer import Composer
from veles.tui.widgets.composer_prompt import ComposerPrompt, PromptOption
from veles.tui.widgets.inspector import Inspector
from veles.tui.widgets.queue_panel import QueuePanel
from veles.tui.widgets.status_bar import StatusBar

# How far back the inspector resurrects persisted errors on boot. A recent
# failure should survive a restart (M132); a days-old, already-fixed one
# should not haunt a fresh session (M132 follow-up).
_SEED_ERROR_MAX_AGE_SECONDS = 24 * 60 * 60


class TuiApp(App[int]):
    CSS = """
    Screen {
        layout: vertical;
    }
    """

    BINDINGS: ClassVar[list[Binding]] = [
        Binding("ctrl+d", "quit", "exit", priority=True),
        # M77: single Ctrl+C copies the last assistant reply; a second press
        # within `_CTRL_C_EXIT_WINDOW_S` exits with a confirmation warning.
        Binding("ctrl+c", "copy_or_exit", "copy / 2x exit", priority=True, show=False),
        Binding("ctrl+v", "paste_clipboard", "paste", priority=True, show=False),
        # M185: copying the output selection is bound exclusively to ⌘C
        # (`super+c`, macOS) and Ctrl+Shift+C (Linux/Windows). A bare
        # drag-select never copies on its own. Both go through
        # `action_copy_selection`, which uses the native clipboard
        # (pbcopy/xclip) and confirms with "copied to clipboard". ⌘C reaches
        # the app only where the terminal forwards it (Textual requests the
        # kitty keyboard protocol); Ctrl+Shift+C is forwarded near-universally.
        Binding("super+c", "copy_selection", "copy selection", priority=True, show=False),
        Binding(
            "ctrl+shift+c",
            "copy_selection",
            "copy selection",
            priority=True,
            show=False,
        ),
        Binding("ctrl+i", "toggle_inspector", "toggle inspector"),
        Binding("ctrl+r", "pick_session", "sessions"),
        Binding("ctrl+t", "pick_theme", "themes"),
        # M182: chat scrollback is the mouse wheel / trackpad (mouse-reporting
        # is on by default — see `run_tui`). All keyboard scroll bindings
        # (Ctrl+O read-mode toggle, PageUp/PageDown, Ctrl+Home/Ctrl+End) were
        # removed. M183b: the chat pane is non-focusable (`ChatLog.can_focus =
        # False`), so keyboard focus never leaves the input — no Escape-to-input
        # escape hatch is needed.
        # No toggle binding for text-selection — VISION §7.2 forbids
        # mode-switching for select (M183b: drag-select + Ctrl+C, or
        # Option+drag + ⌘C on iTerm2).
        # `priority=True` is essential: Textual's default `Shift+Tab` is
        # reverse-focus, which would otherwise consume the keystroke
        # before our handler runs.
        Binding("shift+tab", "cycle_mode", "cycle mode", priority=True),
        # No Ctrl+M binding for models — `ctrl+m` collides with Enter on
        # most terminals (both are `\r`). Use the `/model` slash to open
        # the picker; the binding-less route keeps the keymap unambiguous.
    ]

    # Window inside which a second Ctrl+C is treated as a confirmed exit.
    _CTRL_C_EXIT_WINDOW_S: ClassVar[float] = 1.5

    def __init__(
        self,
        *,
        state: AppState,
        agent_factory: AgentFactory,
        project: Project | None = None,
        store: SessionStore | None = None,
        slash_registry: SlashRegistry | None = None,
        history: InputHistory | None = None,
    ) -> None:
        super().__init__()
        self._state = state
        self._factory = agent_factory
        self._project = project
        self._store = store
        self._slash = (
            slash_registry
            if slash_registry is not None
            else build_default_registry(project=project)
        )
        # Per-app history + completer. Default history persists at
        # `~/.veles/tui_history.jsonl`; tests inject a redirected one.
        self._history = history if history is not None else InputHistory.load()
        self._completer = SlashCompleter(self._slash)
        self._bridge: AgentBridge | None = None
        # Created in `compose`, cached here for cross-handler access.
        self._chat: ChatLog | None = None
        self._composer: Composer | None = None
        self._status: StatusBar | None = None
        self._inspector: Inspector | None = None
        self._queue_panel: QueuePanel | None = None
        # M77: track the previous Ctrl+C press timestamp for double-tap exit.
        self._last_ctrl_c_at: float = 0.0

    # ---- composition / lifecycle ----

    def compose(self) -> ComposeResult:
        with Vertical():
            self._chat = ChatLog()
            yield self._chat
            self._inspector = Inspector()
            yield self._inspector
            self._queue_panel = QueuePanel()
            yield self._queue_panel
            self._composer = Composer(
                history=self._history,
                completer=self._completer,
                project_root_provider=(
                    (lambda p=self._project: p.root) if self._project is not None else None
                ),
            )
            yield self._composer
            self._status = StatusBar()
            yield self._status

    def on_mount(self) -> None:
        # `on_mount` runs on the main thread, still inside the CLI entry's
        # `set_active_project` / `set_module_registry` scope — so capture the
        # module registry here and hand it to the bridge, which re-installs
        # both ContextVars on its worker thread (Textual doesn't propagate
        # them). See `AgentBridge.__init__`.
        from veles.core.modules import current_module_registry

        self._bridge = AgentBridge(
            self,
            self._state,
            self._factory,
            project=self._project,
            module_registry=current_module_registry(),
        )
        assert self._composer is not None and self._status is not None
        assert self._inspector is not None and self._queue_panel is not None
        # Wire the queue-pop hook into the composer now that the bridge
        # exists. Keeping this here (rather than in `__init__`) avoids a
        # chicken-and-egg between bridge and composer construction.
        self._composer.queue_provider = self._pop_queue_for_composer
        self._composer.focus()
        self._inspector.set_expanded(self._state.inspector_visible)
        self._inspector.set_busy(self._state.busy)
        # M132: seed recent errors from the persisted typed-event log so a
        # failure from a previous session stays visible after a restart.
        self._seed_inspector_errors()
        self._queue_panel.render_queue(self._state.queue)
        self._status.render_state(self._state)
        # M182: mouse reporting is ON by default (`app.run(mouse=True)` in
        # `veles.tui.run_tui`, opt-out via `VELES_TUI_MOUSE=0`). The wheel
        # scrolls the chat and drag makes an app-level Textual selection that
        # does NOT copy on its own — copying is bound to ⌘C / Ctrl+Shift+C
        # (M185, `action_copy_selection`). A modifier-drag (⌥ on iTerm2/macOS,
        # Shift elsewhere) bypasses capture for native terminal select+copy.
        # (Supersedes the old M115.3/M115.5 `mouse=False` model.)
        # Best-effort theme application — failure is silent so a missing
        # custom .toml doesn't abort the mount.
        apply_theme(self, self._state.theme_name)
        # M84: keep the wiki FTS index fresh on every TUI boot. Runs in a
        # worker so a 500-page reindex doesn't stall first paint.
        if self._project is not None:
            self.run_worker(self._reindex_wiki_if_stale, exclusive=True, group="wiki-reindex")

    def _seed_inspector_errors(self, *, limit: int = 5) -> None:
        """Load recent ErrorEvents from the project's events.jsonl and hand
        them to the inspector so a failure survives a TUI restart. Errors
        older than `_SEED_ERROR_MAX_AGE_SECONDS` are skipped so a days-old,
        already-fixed failure doesn't show up on a fresh session (M132 +
        follow-up). Best-effort: a missing/corrupt log is silently skipped."""
        if self._project is None or self._inspector is None:
            return
        try:
            from veles.core.events import (
                ErrorEvent,
                events_path_for_project,
                read_events,
                recent_error_events,
            )

            events = read_events(events_path_for_project(self._project.state_dir))
            recent = recent_error_events(
                events, within_seconds=_SEED_ERROR_MAX_AGE_SECONDS, limit=limit
            )
            seeded = [
                ErrorEvent(
                    ts=e.get("ts", ""),
                    session_id=e.get("session_id"),
                    where=e.get("where", ""),
                    error_type=e.get("error_type", "error"),
                    message=e.get("message", ""),
                )
                for e in recent
            ]
            if seeded:
                self._inspector.seed_errors(seeded)
        except Exception:
            pass

    async def _reindex_wiki_if_stale(self) -> None:
        from veles.core.layout.engines import wiki_enabled
        from veles.modules.wiki.wiki import Wiki

        assert self._project is not None
        if not wiki_enabled(self._project):
            return
        # Indexing is best-effort; never let it crash the TUI.
        with contextlib.suppress(Exception):
            Wiki(self._project.wiki_root).reindex_if_stale()

    # ---- input handling ----

    def on_composer_submitted(self, event: Composer.Submitted) -> None:
        event.stop()
        prompt = event.value.strip()
        if not prompt:
            return
        if prompt.startswith("/"):
            self._dispatch_slash(prompt)
            return
        assert self._chat is not None and self._bridge is not None
        self._chat.append_user(prompt)
        self._chat.start_assistant()
        if self._inspector is not None:
            self._inspector.reset_for_new_turn()
            self._inspector.set_busy(True)
        self._bridge.submit(prompt)
        self._refresh_status()

    # ---- slash dispatch ----

    def _dispatch_slash(self, line: str) -> None:
        """Route through `SlashRegistry`. Unknown commands surface as an
        error row; quit/clear flags are applied here so the App stays
        the single owner of UI mutation."""
        assert self._chat is not None
        if self._project is None or self._store is None:
            # Tests can opt into a no-project mode (`/quit` only).
            self._dispatch_slash_no_project(line)
            return
        ctx = SlashContext(state=self._state, project=self._project, store=self._store)
        # Snapshot the fields a handler may mutate as a side effect so
        # the App can react with the right UI work (theme swap, etc.)
        # — handlers stay pure and free of `app` references.
        prev_theme = self._state.theme_name
        result = self._slash.dispatch(line, ctx)
        if result is None:
            self._chat.append_error(f"unknown command {line.split()[0]!r}; try /help")
            return
        if self._state.theme_name != prev_theme and not result.is_error and not result.open_picker:
            apply_theme(self, self._state.theme_name)
        self._apply_slash_result(result)

    def _dispatch_slash_no_project(self, line: str) -> None:
        """Degraded mode for the Phase-1 smoke harness: only `/quit` and
        its aliases run; everything else explains why."""
        assert self._chat is not None
        name = line.strip().split(maxsplit=1)[0]
        if name in ("/quit", "/q", "/exit"):
            self.exit(0)
            return
        self._chat.append_error(
            f"{name}: slash commands require a project context; use Ctrl+D to exit."
        )

    def _apply_slash_result(self, result) -> None:
        assert self._chat is not None
        if result.clear_chat:
            self._chat.clear_messages()
        if result.text:
            if result.is_error:
                self._chat.append_error(result.text)
            else:
                self._chat.append_system(result.text)
        if result.quit:
            self.exit(0)
            return
        if result.open_picker:
            self._open_picker(result.open_picker)
            return
        if result.submit_prompt:
            self._submit_synthetic(result.submit_prompt)
            return
        # State may have changed (model/theme/session_id); refresh footer.
        self._refresh_status()

    def _submit_synthetic(self, prompt: str) -> None:
        """M83: route a slash-generated prompt through the regular agent
        flow. Mirrors `on_composer_submitted` minus the user echo (the
        slash command already printed a system line)."""
        assert self._chat is not None and self._bridge is not None
        self._chat.start_assistant()
        if self._inspector is not None:
            self._inspector.reset_for_new_turn()
            self._inspector.set_busy(True)
        self._bridge.submit(prompt)
        self._refresh_status()

    # ---- pickers ----

    def _open_picker(self, name: str) -> None:
        """Route picker names emitted by slash handlers to a `ModalScreen`.
        Session/theme pickers are reached via Ctrl+R/Ctrl+T directly."""
        if name == "models":
            self.action_pick_model()
        elif name == "models:refresh":
            self.action_pick_model(refresh=True)
        elif name == "daemon":
            self._open_daemon_picker()
        else:
            assert self._chat is not None
            self._chat.append_error(f"unknown picker {name!r}")

    def _open_daemon_picker(self) -> None:
        """Push the daemon control panel as a modal over the chat (M138).
        `standalone=False` so its quit pops back here instead of exiting."""
        from veles.tui.screens.daemon_picker import DaemonPickerScreen

        self.push_screen(DaemonPickerScreen(standalone=False, project=self._project))

    def action_pick_session(self) -> None:
        if self._store is None:
            return
        self.push_screen(
            SessionPickerScreen(self._store, current=self._state.session_id),
            self._after_session_pick,
        )

    def action_pick_model(self, *, refresh: bool = False) -> None:
        self.push_screen(
            ModelPickerScreen(
                self._state.provider_name,
                current=self._state.model,
                refresh=refresh,
            ),
            self._after_model_pick,
        )

    def action_pick_theme(self) -> None:
        self.push_screen(
            ThemePickerScreen(current=self._state.theme_name),
            self._after_theme_pick,
        )

    def _after_session_pick(self, session_id: str | None) -> None:
        if not session_id or self._store is None:
            return
        assert self._chat is not None
        info = self._store.get_session(session_id)
        if info is None:
            self._chat.append_error(f"session {session_id!r} not found")
            return
        self._state.session_id = session_id
        self._state.last_assistant_text = None
        self._chat.append_system(f"switched to session {session_id} (turns={info.turn_count})")
        self._refresh_status()

    def _after_model_pick(self, model: str | None) -> None:
        if not model:
            return
        assert self._chat is not None
        self._state.model = model
        self._chat.append_system(f"model set to {model}")
        # `_persist_state` writes mode/active_goal_id/model into
        # tui_state.json; `persist_model_choice` additionally mirrors
        # the model into project config.toml so the resolver cascade
        # picks the latest choice on next boot.
        self._persist_state()
        if self._project is not None:
            from veles.core.tui_state import persist_model_choice

            persist_model_choice(self._project, model)
        self._refresh_status()

    def _persist_state(self) -> None:
        """Snapshot AppState into `.veles/tui_state.json`. Used by every
        path that mutates a persisted field (mode, model, active_goal_id).
        Best-effort — preference file is not load-bearing."""
        if self._project is None:
            return
        from veles.core.tui_state import TuiPersistentState, save_for_project

        with contextlib.suppress(OSError):
            save_for_project(
                self._project,
                TuiPersistentState(
                    mode=self._state.mode,
                    active_goal_id=self._state.active_goal_id,
                    model=self._state.model,
                ),
            )

    def _after_theme_pick(self, theme: str | None) -> None:
        if not theme:
            return
        assert self._chat is not None
        self._state.theme_name = theme
        applied = apply_theme(self, theme)
        message = f"theme set to {theme}" if applied else f"theme {theme!r} not found"
        if applied:
            self._chat.append_system(message)
        else:
            self._chat.append_error(message)
        self._refresh_status()

    # ---- bridge → UI fan-in ----

    def on_chat_delta(self, message: wire.ChatDelta) -> None:
        assert self._chat is not None
        self._chat.append_assistant_delta(message.text)

    def on_agent_event(self, message: wire.AgentEvent) -> None:
        if self._inspector is not None:
            self._inspector.notify_event(message.event)

    def on_system_line(self, message: wire.SystemLine) -> None:
        """Mode-emitted informational lines (e.g. `[auto → planning]`).
        Routed to the chat as a system message — same visual treatment
        as slash-command output."""
        if self._chat is not None:
            self._chat.seal_assistant()
            self._chat.append_system(message.text)

    def on_turn_done(self, message: wire.TurnDone) -> None:
        assert self._chat is not None and self._bridge is not None
        self._chat.seal_assistant()
        self._state.busy = False
        if self._inspector is not None:
            self._inspector.set_busy(False)
        # Capture the last assistant text so `/save` has something to
        # write. Prefer the chat-log transcript over `message.result.text`
        # because the latter strips streaming scrubber tails.
        for role, text in reversed(self._chat.transcript):
            if role == "assistant" and text:
                self._state.last_assistant_text = text
                break
        # M79: accumulate token usage. `usage` is always present on the
        # RunResult (default-constructed UsageSnapshot), so synthetic
        # turns from goal/auto modes contribute zeros without special-cases.
        usage = getattr(message.result, "usage", None)
        if usage is not None:
            self._state.tokens_in += usage.prompt_tokens
            self._state.tokens_out += usage.completion_tokens
            self._state.last_turn_total_tokens = usage.total_tokens
            # M177: live context occupancy for the `ctx` chip = the last
            # request's prompt size (falls back to total when a provider
            # doesn't split prompt tokens).
            self._state.last_prompt_tokens = (
                usage.last_prompt_tokens or usage.prompt_tokens or usage.total_tokens
            )
            # M178: cache-read tokens for the last turn (prompt caching).
            self._state.last_turn_cache_read = getattr(usage, "cache_read_tokens", 0)
        # FIFO drain of any queued prompts (Phase 6 adds the editing UI).
        self._bridge.drain_one()
        self._refresh_status()
        del message

    def on_agent_error(self, message: wire.AgentError) -> None:
        assert self._chat is not None
        self._chat.append_error(f"{type(message.exc).__name__}: {message.exc}")
        self._state.busy = False
        if self._inspector is not None:
            self._inspector.set_busy(False)
        self._refresh_status()

    # ---- bindings ----

    def action_copy_or_exit(self) -> None:
        """Ctrl+C: M77 — copy the last assistant reply; a second press inside
        the exit window confirms the quit (transient warning between presses).

        M185: Ctrl+C no longer copies the mouse selection. Per the chosen UX,
        a bare selection never copies on its own, and copying the selection is
        bound exclusively to ⌘C (`super+c`) / Ctrl+Shift+C
        (`action_copy_selection`). Ctrl+C stays the copy-last-reply / exit key.
        """
        import time

        now = time.monotonic()
        if now - self._last_ctrl_c_at <= self._CTRL_C_EXIT_WINDOW_S:
            # Stop any in-flight turn cooperatively before tearing down the
            # event loop. Without this the worker thread stays blocked in
            # the provider stream, asyncio's shutdown waits on it, and a
            # third Ctrl+C surfaces a KeyboardInterrupt traceback (M131).
            if self._bridge is not None:
                self._bridge.cancel_turn()
            self.exit(0)
            return
        self._last_ctrl_c_at = now
        from veles.tui.clipboard import copy_text

        target = self._state.last_assistant_text or ""
        ok = copy_text(target) if target.strip() else False
        assert self._chat is not None
        if ok:
            self._chat.append_system("copied last reply · press Ctrl+C again to exit")
        else:
            self._chat.append_system("press Ctrl+C again to exit (nothing to copy)")

    def action_copy_selection(self) -> None:
        """M185: explicit copy of the current output selection — bound to ⌘C
        (`super+c`, macOS) and Ctrl+Shift+C (Linux/Windows). A bare drag-select
        never copies on its own; only these keys do. Copies via the native
        clipboard (pbcopy/xclip) so it's reliable regardless of terminal, and
        surfaces a "copied to clipboard" confirmation.

        Note: whether ⌘C reaches the app is terminal-dependent — Textual
        requests the kitty keyboard protocol, but a terminal that binds ⌘C to
        its own Copy (e.g. default iTerm2/Terminal.app) intercepts it first.
        Ctrl+Shift+C is forwarded by virtually every terminal; `VELES_TUI_MOUSE=0`
        falls back to native terminal selection + native ⌘C."""
        from veles.tui.clipboard import copy_text

        try:
            selected = self.screen.get_selected_text() or ""
        except Exception:
            selected = ""
        assert self._chat is not None
        if not selected.strip():
            self._chat.append_system("nothing selected to copy")
            return
        if copy_text(selected):
            self._chat.append_system("copied to clipboard")
        else:
            self._chat.append_system("copy failed (no clipboard tool found)")
        with contextlib.suppress(Exception):
            self.screen.clear_selection()

    def action_quit(self) -> None:  # type: ignore[override]
        """Ctrl+D / explicit quit. Stop the in-flight turn first so the
        worker thread unwinds and shutdown stays clean (M131)."""
        if self._bridge is not None:
            self._bridge.cancel_turn()
        self.exit(0)

    def action_paste_clipboard(self) -> None:
        """M77: paste — text goes into the composer; image is dropped into
        `<.veles/tmp/paste/>` and the @-reference inserted."""
        from veles.tui.clipboard import paste_image, paste_text

        assert self._composer is not None and self._chat is not None
        if self._project is not None:
            paste_dir = self._project.state_dir / "tmp" / "paste"
            target = paste_dir / self._new_paste_filename()
            if paste_image(target):
                try:
                    rel = target.relative_to(self._project.root).as_posix()
                except ValueError:
                    rel = target.as_posix()
                self._composer.insert(f"@{rel} ")
                self._chat.append_system(f"image pasted → {rel}")
                return
        text = paste_text()
        if text:
            self._composer.insert(text)

    @staticmethod
    def _new_paste_filename() -> str:
        import hashlib
        import time

        ts = time.strftime("%Y%m%d-%H%M%S", time.localtime())
        sha = hashlib.sha1(str(time.time_ns()).encode()).hexdigest()[:8]
        return f"{ts}-{sha}.png"

    def action_toggle_inspector(self) -> None:
        if self._inspector is None:
            return
        self._inspector.toggle()
        self._state.inspector_visible = self._inspector.expanded

    def action_cycle_mode(self) -> None:
        """Shift+Tab handler: cycle auto → planning → writing → goal → auto.
        Persists to `<project>/.veles/tui_state.json` so the next TUI boot
        starts in the same mode. Posts a chat system line so the user
        sees the change even before they look at the status bar.

        Special case for `goal`: per design, entering goal mode always
        starts a fresh interview. If an active goal artifact is already
        on disk from a previous goal-mode session, cancel it here (UI
        thread, before the next turn fires) so the FSM bootstraps
        cleanly into a new interview. Users who want to resume a
        paused goal can do so via `veles goal resume <id>` from the
        shell — the cancelled artifact stays on disk for reference.
        """
        from veles.core.modes import next_mode

        new_mode = next_mode(self._state.mode)
        # Auto-abandon a stale active goal when re-entering goal mode.
        if new_mode == "goal" and self._state.active_goal_id and self._project is not None:
            try:
                from veles.core.goal import cancel as cancel_goal

                stale_id = self._state.active_goal_id
                cancel_goal(
                    self._project.state_dir,
                    stale_id,
                    reason="user cycled back into goal mode",
                )
                if self._chat is not None:
                    self._chat.append_system(f"abandoned previous goal {stale_id}; starting fresh")
            except (KeyError, OSError, ValueError):
                pass  # stale id → just clear; fresh interview will bootstrap
            self._state.active_goal_id = None

        self._state.mode = new_mode
        self._persist_state()
        if self._chat is not None:
            self._chat.append_system(f"mode: {new_mode}")
        self._refresh_status()

    # ---- helpers ----

    def _refresh_status(self) -> None:
        if self._status is None:
            return
        self._status.render_state(self._state)
        if self._queue_panel is not None:
            self._queue_panel.render_queue(self._state.queue)

    def _pop_queue_for_composer(self) -> str | None:
        """Composer-side queue hook: pops the newest queued prompt for
        editing and refreshes the panel. Returns `None` when the queue
        is empty so the composer falls through to history navigation."""
        if self._bridge is None:
            return None
        text = self._bridge.pop_last_for_edit()
        if text is None:
            return None
        if self._queue_panel is not None:
            self._queue_panel.render_queue(self._state.queue)
        if self._status is not None:
            self._status.render_state(self._state)
        return text

    @property
    def state(self) -> AppState:
        """Test hook: lets pilots peek at internal state without
        reaching through private attrs."""
        return self._state

    # ---- inline composer prompt ----

    async def composer_prompt(
        self,
        *,
        question: str,
        body: str | None,
        options: list[PromptOption],
        default_key: object,
    ) -> object:
        """Show an inline approval/trust prompt above the Composer and
        await the user's pick.

        The Composer is hidden (its draft is preserved) while the prompt
        is active so the user's keystrokes land on the prompt's ListView
        instead of the text buffer. Called from the worker thread via
        `app.call_from_thread`, which awaits this coroutine on the UI
        loop and returns the result back to the worker.
        """
        import asyncio

        assert self._composer is not None
        loop = asyncio.get_running_loop()
        future: asyncio.Future[object] = loop.create_future()
        prompt = ComposerPrompt(
            question=question,
            body=body,
            options=options,
            default_key=default_key,
            future=future,
        )
        parent = self._composer.parent
        assert parent is not None
        await parent.mount(prompt, before=self._composer)
        self._composer.display = False
        try:
            result = await future
        finally:
            await prompt.remove()
            self._composer.display = True
            self._composer.focus()
        return result

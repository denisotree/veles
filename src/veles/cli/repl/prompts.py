"""Mid-turn prompters for the inline `_ReplApp`.

The agent's `ask_user`, the M39 critical-op confirmer, and the unified
permission prompt (trust ladder + approval) are all answered INSIDE the
running Application (a nested prompt_toolkit app can't run under the live
event loop). Each publishes a question, wakes the UI, and blocks the
executor thread on an Event until a key handler on the loop thread supplies
the answer. All state lives on `_ReplApp`.
"""

from __future__ import annotations

import sys

from veles.core.i18n import t


class PromptsMixin:
    # --- mid-turn pickers (ask_user + permission), answered inside this app ---

    def _ask(self, question: str, options):
        """Question prompter installed for the agent's `ask_user`. Runs in the
        executor thread: it publishes the question, wakes the UI, then blocks on
        an Event until a key handler (loop thread) supplies the answer. Returns
        None with no TTY so headless runs never block."""
        import threading

        if not sys.stdin.isatty():
            return None
        self.q_question = question
        self.q_options = list(options) if options else []
        self.q_values = None  # answer IS the chosen option string
        self.q_allow_free = bool(options)  # options → offer a free-text row too
        self.q_sel = 0
        self.q_free = not self.q_options  # no options → straight to free text
        self.q_answer = None
        self.q_event = threading.Event()
        self.q_active = True
        self._invalidate_threadsafe()
        self.q_event.wait()  # blocks the executor thread, not the loop
        return self.q_answer

    def _confirm_critical(self, op: str, summary: str) -> bool:
        """M39 hard-confirm for DESTRUCTIVE ops (delete_file, user-global
        writes), answered inside THIS app as a yes/no picker — the default
        confirmer reads `input()` from stdin, which hangs the executor thread
        under the running Application. Runs in the executor thread; blocks on the
        picker Event. Refuses (False) with no TTY, and defaults the highlight to
        Cancel so a stray Enter never deletes."""
        import threading

        if not sys.stdin.isatty():
            return False
        self.console.print()
        self.console.print(f"⚠ {op}", style=self.theme.error, markup=False)
        if summary:
            self.console.print(f"  {summary}", style=self.theme.muted, markup=False)
        self.q_question = t("repl.confirm_critical", op=op)
        self.q_options = [t("repl.confirm_yes"), t("repl.confirm_cancel")]
        self.q_values = ["yes", "no"]
        self.q_allow_free = False
        self.q_free = False
        self.q_sel = 1  # default highlight = Cancel (safe)
        self.q_answer = None
        self.q_event = threading.Event()
        self.q_active = True
        self._invalidate_threadsafe()
        self.q_event.wait()
        return self.q_answer == "yes"  # Esc/cancel → None → False (deny)

    def _permission_prompt(self, req):
        """Unified permission prompter (trust ladder + approval), installed so a
        sensitive tool's decision is answered inside THIS app instead of the
        default nested-Application menu (which corrupts the terminal). Runs in
        the executor thread and blocks on the same picker Event as `_ask`. Denies
        with no TTY so headless runs never block."""
        import threading

        from veles.core.permission.prompt import PromptAnswer, format_prompt_body

        if not sys.stdin.isatty():
            return PromptAnswer(decision="deny")
        # The tool / reason / arguments go to scrollback; the picker shows only
        # the ladder options (mirrors the default menu's layout).
        self.console.print()
        self.console.print(format_prompt_body(req), style=self.theme.muted, markup=False)
        if req.kind == "trust":
            labels = [
                "Once (this call only)",
                "Always for this project",
                "Always everywhere",
                "Refuse",
            ]
            values = ["allow_once", "allow_project", "allow_global", "deny"]
        else:  # approval — turn-scoped: only allow-once / deny
            labels = ["Allow once", "Refuse"]
            values = ["allow_once", "deny"]
        self.q_question = t("repl.permission_allow", tool=req.tool_name)
        self.q_options = labels
        self.q_values = values
        self.q_allow_free = False
        self.q_free = False
        self.q_sel = 0
        self.q_answer = None
        self.q_event = threading.Event()
        self.q_active = True
        self._invalidate_threadsafe()
        self.q_event.wait()
        return PromptAnswer(decision=self.q_answer or "deny")  # Esc/None → deny

    def _picker_rows(self) -> int:
        """Total selectable rows: options plus the free-text sentinel if shown."""
        return len(self.q_options) + (1 if self.q_allow_free else 0)

    def _answer(self, ans) -> None:
        ev = self.q_event
        question = self.q_question
        self.q_answer = ans
        self.q_active = False
        self.q_free = False
        self.q_event = None
        if ans is not None:
            self.console.print(f"  ⋅ {question} → {ans}", style=self.theme.muted, markup=False)
        self.app.invalidate()
        if ev is not None:
            ev.set()

    def _picker_enter(self) -> None:
        if self.q_allow_free and self.q_sel >= len(self.q_options):  # free-text row
            self.q_free = True
            self.input.text = ""
            self.app.invalidate()
            return
        idx = min(self.q_sel, len(self.q_options) - 1) if self.q_options else 0
        # Answer the mapped decision value (permission) or the option (ask_user).
        self._answer(self.q_values[idx] if self.q_values is not None else self.q_options[idx])

    def _free_submit(self) -> None:
        txt = self.input.text.strip()
        self.input.text = ""
        self._answer(txt or None)

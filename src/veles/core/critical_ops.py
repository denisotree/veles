"""Always-confirm gate for critical operations (M39).

Some operations are too consequential to be bypassed by the M38 trust
ladder's persistent grants, by `VELES_TRUST_AUTO_ALLOW=1`, or by the
CLI `--yes` flag. M39 routes them through `confirm_critical(op, summary)`
which demands a literal lowercase `yes` typed at TTY every time. Non-TTY
contexts refuse outright. There is no env-var bypass — VISION §8 calls
this out explicitly.

Current call sites:

- `cli.py` install commands (`veles skill add`, `veles module add`):
  third-party code that will execute on the user's machine. `--yes` is
  parsed but ignored for these paths.
- `tools/builtin/fs_write_guard.py::guard_write` (every file-tool write):
  writes resolved outside the active project root (i.e. into user-global
  `~/.veles/`) — the agent could install code there otherwise — and writes
  to auto-executed / agent CLI config paths (`writable.needs_confirmation`:
  `.git/`, `.claude/`, `.envrc`, …).

In M39 scope now:
- `tools/builtin/file_ops.py::delete_file` (DESTRUCTIVE) — routes here per
  call. Interactive surfaces MUST install their own confirmer via
  `set_critical_confirmer` (the REPL/TUI render an in-app yes/no picker); the
  default `input()` confirmer would hang a running prompt_toolkit app.

Out of M39 scope:
- Network beyond the LLM endpoint (`fetch_url`) — gated by M38 trust
  ladder. Re-prompting on every fetch would defeat any agent loop that
  uses public docs.

  **But M198 later added a second, narrower path to this gate that this
  paragraph does not cover**, and reading it as "fetch_url never reaches
  confirm_critical" is wrong. `permission/engine.py::_untrusted_args_rule`
  routes an *egress* tool here when its destination host also appears in
  untrusted content read earlier in the same run. It runs before the policy
  gate, so neither the `allow` override in `BUILTIN_TOOL_POLICY_OVERRIDES` nor
  `VELES_TRUST_AUTO_ALLOW=1` can reach it — by design, that is the
  prompt-injection exfiltration signal.

  Consequence, observed live 2026-09-01: `web_search` records its results as
  untrusted, so fetching any URL those results contain escalates. "Search, then
  open what you found" is the whole of research, which means research is
  effectively TTY-only — in a daemon, a channel, or a non-TTY `veles run` the
  model retries against a fail-closed deny until its iterations run out.
  Interactive surfaces install a picker via `set_critical_confirmer`; headless
  callers currently have no equivalent.

Tests inject a fake confirmer via `set_critical_confirmer`.
"""

from __future__ import annotations

import os
import sys
from collections.abc import Callable
from contextvars import ContextVar, Token

Confirmer = Callable[[str, str], bool]

_LITERAL_YES = "yes"

# Set on every command the agent's `run_shell` runs. An approval asked for from there
# is the agent approving its own code. A shell can strip it: this stops the agent
# that "fixes" a skipped-module warning, not a determined one (an OS sandbox does).
AGENT_SHELL_ENV = "VELES_AGENT_SHELL"


def refuse_in_agent_shell(what: str) -> None:
    """Raise PermissionError when called from a command the agent's shell started."""
    if os.environ.get(AGENT_SHELL_ENV):
        raise PermissionError(f"{what} can't come from the agent's shell — run it yourself")


_critical_confirmer: ContextVar[Confirmer | None] = ContextVar(
    "veles_critical_confirmer", default=None
)


def set_critical_confirmer(c: Confirmer | None) -> Token:
    return _critical_confirmer.set(c)


def reset_critical_confirmer(token: Token) -> None:
    _critical_confirmer.reset(token)


def confirm_critical(op: str, summary: str) -> bool:
    """Hard-confirmation prompt. Returns True iff the user types literal `yes`.

    Non-TTY contexts refuse without prompting. Tests override the
    interactive prompt by registering a fake `Confirmer` via
    `set_critical_confirmer`.
    """
    confirmer = _critical_confirmer.get()
    if confirmer is not None:
        return confirmer(op, summary)
    return _default_confirmer(op, summary)


def _default_confirmer(op: str, summary: str) -> bool:
    # `op`/`summary` are built by call sites from tool-controlled strings
    # (paths, names, recipes) — escape once here so no caller has to
    # remember to, and a control character can't forge this prompt. `op` is
    # always one line (an action description), so full `shown()` is right.
    # `summary` is sometimes a legitimate multi-line review body (e.g.
    # `mcp/approvals.py::describe_recipe`, install summaries with `Source:
    # .../Target: ...` lines) — `shown_multiline()` keeps those newlines
    # literal while still escaping any other injected control character.
    from veles.core.text import gutter, shown, shown_multiline

    op = shown(op)
    summary = gutter(shown_multiline(summary)) if summary else ""
    if not sys.stdin.isatty():
        print(
            f"\nCRITICAL: {op} requires interactive confirmation; non-TTY context refuses.",
            file=sys.stderr,
        )
        return False
    print(f"\nCRITICAL: {op}", file=sys.stderr)
    if summary:
        print(summary, file=sys.stderr)
    print(
        f"Type {_LITERAL_YES!r} (literal lowercase) to proceed. "
        "Trust grants and --yes do NOT bypass this.",
        file=sys.stderr,
    )
    try:
        raw = input("Confirm: ").strip()
    except EOFError:
        return False
    return raw == _LITERAL_YES

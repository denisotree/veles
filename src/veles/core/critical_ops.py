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
- `tools/builtin/write_file.py`: writes resolved outside the active
  project root (i.e. into user-global `~/.veles/`) — the agent could
  install code there otherwise.

In M39 scope now:
- `tools/builtin/file_ops.py::delete_file` (DESTRUCTIVE) — routes here per
  call. Interactive surfaces MUST install their own confirmer via
  `set_critical_confirmer` (the REPL/TUI render an in-app yes/no picker); the
  default `input()` confirmer would hang a running prompt_toolkit app.

Out of M39 scope:
- Network beyond the LLM endpoint (`fetch_url`) — gated by M38 trust
  ladder. Re-prompting on every fetch would defeat any agent loop that
  uses public docs.

Tests inject a fake confirmer via `set_critical_confirmer`.
"""

from __future__ import annotations

import sys
from collections.abc import Callable
from contextvars import ContextVar, Token

Confirmer = Callable[[str, str], bool]

_LITERAL_YES = "yes"

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

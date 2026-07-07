"""Map `cli/tui_theme.py:TuiTheme` to Textual's `Theme` + applier.

The legacy themes are rich-flavoured (error/success/warning/accent/muted
plus prompt_toolkit-specific style strings). Textual themes use a
different vocabulary — primary/secondary/accent/warning/error/success
plus an explicit foreground/background pair. The mapping is lossy on
purpose: we keep only the colour tokens that move the needle in a
Textual UI, and drop the prompt_toolkit-only fields.

Why a separate bridge rather than rewriting `TuiTheme`: the legacy
TOML format under `~/.veles/themes/*.toml` is what users already have
on disk. Touching the schema would break those files. Going through a
bridge keeps user data stable while letting the new TUI render in the
theme they expect.
"""

from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING

from textual.theme import Theme

from veles.cli.tui_theme import TuiTheme, load_theme

if TYPE_CHECKING:
    from textual.app import App


# All five built-ins are dark; user-supplied themes inherit the same
# until we add a `dark: bool` field to `TuiTheme` (out of scope here —
# would require migrating every existing .toml on disk).
_DEFAULT_DARK = True


def to_textual_theme(t: TuiTheme) -> Theme:
    """Project a `TuiTheme` onto Textual's colour-token vocabulary.

    The TuiTheme accent doubles as Textual's `primary` (used for borders
    and the focused widget edge) and `accent` (highlights). Muted maps
    to `secondary` so dim subtitles pick up the theme's quiet tone.
    """
    return Theme(
        name=f"veles_{t.name}",
        primary=t.accent,
        secondary=t.muted,
        accent=t.accent,
        warning=t.warning,
        error=t.error,
        success=t.success,
        dark=_DEFAULT_DARK,
    )


def apply_to_app(app: App, theme_name: str) -> bool:
    """Resolve `theme_name` (built-in or user TOML), register it with
    the App if needed, and switch. Returns `False` when the name doesn't
    resolve to a known theme — caller decides whether to surface the
    failure to the user."""
    tt = load_theme(theme_name)
    if tt is None:
        return False
    textual_theme = to_textual_theme(tt)
    # `register_theme` raises if a same-named theme is already
    # installed — fine, we just switch in the next step.
    with contextlib.suppress(Exception):
        app.register_theme(textual_theme)
    try:
        app.theme = textual_theme.name
    except Exception:
        return False
    return True

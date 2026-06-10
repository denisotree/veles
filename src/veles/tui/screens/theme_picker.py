"""Pick a colour theme.

Includes the five built-in themes from `cli/tui_theme.py`. Custom TOML
themes from `~/.veles/themes/*.toml` aren't listed here yet — the
Phase 7 theme bridge will plug them in when CSS variables actually
swap. For now the picker is a state mutator: it sets
`state.theme_name`, the rest is bookkeeping.
"""

from __future__ import annotations

from veles.tui.screens.base_picker import PickerItem, PickerScreen


def builtin_theme_names() -> list[str]:
    from veles.cli.tui_theme import THEMES

    return sorted(THEMES.keys())


class ThemePickerScreen(PickerScreen[str]):
    def __init__(self, current: str | None = None) -> None:
        items: list[PickerItem[str]] = []
        for name in builtin_theme_names():
            marker = "* " if name == current else "  "
            items.append(
                PickerItem(label=f"{marker}{name}", haystack=name, value=name)
            )
        super().__init__(
            title="Pick a theme (Esc to cancel)",
            items=items,
            empty_message="no themes installed",
            placeholder="filter by theme name…",
        )

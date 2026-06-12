"""TUI colour themes (M48c).

Each TuiTheme maps semantic roles (error, success, warning, …) to Rich
markup colour strings and prompt_toolkit style strings so the entire TUI
palette can be swapped by changing one object.

Built-in themes: everforest (default), dracula, gruvbox, tokyo-night,
catppuccin.

Custom themes live at `~/.veles/themes/<name>.toml` and are discovered
automatically by `list_themes()` / `load_theme()`.
"""

from __future__ import annotations

import os
import tempfile
import tomllib
from dataclasses import asdict, dataclass, field
from pathlib import Path

_THEME_FIELDS = (
    "name",
    "error",
    "success",
    "warning",
    "accent",
    "muted",
    "border",
    "pt_selected",
    "pt_hint",
)


@dataclass(frozen=True, slots=True)
class TuiTheme:
    name: str
    # Rich markup colour names used as f"[{theme.error}]text[/]"
    error: str
    success: str
    warning: str
    accent: str  # banner, panel borders, info highlights
    muted: str  # secondary / dimmed text
    # Rich Panel border style string
    border: str
    # prompt_toolkit FormattedText style strings
    pt_selected: str  # highlighted menu item
    pt_hint: str  # navigation hint line
    pt_header: str = field(default="bold")


# ---- built-in themes ----

THEMES: dict[str, TuiTheme] = {
    "everforest": TuiTheme(
        name="everforest",
        error="#e67e80",
        success="#a7c080",
        warning="#dbbc7f",
        accent="#7fbbb3",
        muted="#859289",
        border="#7fbbb3",
        pt_selected="bold fg:#a7c080",
        pt_hint="fg:#859289",
    ),
    "dracula": TuiTheme(
        name="dracula",
        error="#ff5555",
        success="#50fa7b",
        warning="#f1fa8c",
        accent="#8be9fd",
        muted="#6272a4",
        border="#8be9fd",
        pt_selected="bold fg:#ff79c6",
        pt_hint="fg:#6272a4",
    ),
    "gruvbox": TuiTheme(
        name="gruvbox",
        error="#fb4934",
        success="#b8bb26",
        warning="#fabd2f",
        accent="#83a598",
        muted="#928374",
        border="#83a598",
        pt_selected="bold fg:#fabd2f",
        pt_hint="fg:#928374",
    ),
    "tokyo-night": TuiTheme(
        name="tokyo-night",
        error="#f7768e",
        success="#9ece6a",
        warning="#e0af68",
        accent="#7aa2f7",
        muted="#565f89",
        border="#7aa2f7",
        pt_selected="bold fg:#7aa2f7",
        pt_hint="fg:#565f89",
    ),
    "catppuccin": TuiTheme(
        name="catppuccin",
        error="#f38ba8",
        success="#a6e3a1",
        warning="#f9e2af",
        accent="#89dceb",
        muted="#6c7086",
        border="#89dceb",
        pt_selected="bold fg:#cba6f7",
        pt_hint="fg:#6c7086",
    ),
}


# ---- path helpers ----


def themes_dir() -> Path:
    """Return ~/.veles/themes/ (VELES_USER_HOME-aware)."""
    from veles.core.user_paths import user_themes_dir

    return user_themes_dir()


# ---- load / save ----


def load_theme(name: str) -> TuiTheme | None:
    """Return TuiTheme by name: built-in first, then custom TOML, else None."""
    if name in THEMES:
        return THEMES[name]
    candidate = themes_dir() / f"{name}.toml"
    if candidate.is_file():
        try:
            return import_theme_from_file(candidate)
        except (ValueError, OSError):
            return None
    return None


def save_custom_theme(theme: TuiTheme) -> None:
    """Atomically write theme to ~/.veles/themes/<name>.toml."""
    td = themes_dir()
    td.mkdir(parents=True, exist_ok=True)
    target = td / f"{theme.name}.toml"
    text = _render_theme_toml(theme)
    fd, tmp = tempfile.mkstemp(prefix=target.name + ".", suffix=".tmp", dir=td)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
        os.replace(tmp, target)
    except Exception:
        Path(tmp).unlink(missing_ok=True)
        raise


def import_theme_from_file(path: Path) -> TuiTheme:
    """Parse a TOML theme file and return TuiTheme.

    Raises ValueError if required fields are missing or the file is unreadable.
    """
    try:
        with path.open("rb") as fh:
            data = tomllib.load(fh)
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise ValueError(f"cannot read theme file {path}: {exc}") from exc

    missing = [f for f in _THEME_FIELDS if f not in data or not isinstance(data[f], str)]
    if missing:
        raise ValueError(f"theme file {path} missing fields: {', '.join(missing)}")

    return TuiTheme(
        name=data["name"],
        error=data["error"],
        success=data["success"],
        warning=data["warning"],
        accent=data["accent"],
        muted=data["muted"],
        border=data["border"],
        pt_selected=data["pt_selected"],
        pt_hint=data["pt_hint"],
        pt_header=data.get("pt_header", "bold"),
    )


def list_themes() -> list[str]:
    """Return sorted list of all available theme names (built-in + custom)."""
    names: set[str] = set(THEMES.keys())
    td = themes_dir()
    if td.is_dir():
        for p in td.glob("*.toml"):
            names.add(p.stem)
    return sorted(names)


# ---- TOML rendering ----


def _escape(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"')


def _render_theme_toml(theme: TuiTheme) -> str:
    d = asdict(theme)
    lines = []
    for key in (*_THEME_FIELDS, "pt_header"):
        if key in d:
            lines.append(f'{key} = "{_escape(d[key])}"')
    return "\n".join(lines) + "\n"

"""Tests for veles.cli.tui_theme — TuiTheme dataclass, THEMES dict, load/save."""

from __future__ import annotations

from pathlib import Path

import pytest

from veles.cli.tui_theme import (
    THEMES,
    TuiTheme,
    import_theme_from_file,
    list_themes,
    load_theme,
    save_custom_theme,
    themes_dir,
)

# ---- fixtures ----


@pytest.fixture(autouse=True)
def _isolate_user_home(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    isolated = tmp_path / "_user_home"
    isolated.mkdir()
    monkeypatch.setenv("VELES_USER_HOME", str(isolated))
    yield


def _make_theme_toml(path: Path, **overrides) -> None:
    defaults = {
        "name": "testtheme",
        "error": "#ff0000",
        "success": "#00ff00",
        "warning": "#ffff00",
        "accent": "#00ffff",
        "muted": "#888888",
        "border": "#00ffff",
        "pt_selected": "bold fg:#00ff00",
        "pt_hint": "fg:#888888",
    }
    defaults.update(overrides)
    lines = [f'{k} = "{v}"' for k, v in defaults.items()]
    path.write_text("\n".join(lines) + "\n")


# ---- built-in theme tests ----


def test_builtin_themes_all_present() -> None:
    assert set(THEMES.keys()) == {"everforest", "dracula", "gruvbox", "tokyo-night", "catppuccin"}


def test_each_theme_has_required_fields() -> None:
    for name, theme in THEMES.items():
        assert theme.name == name
        assert theme.error
        assert theme.success
        assert theme.warning
        assert theme.accent
        assert theme.muted
        assert theme.border
        assert theme.pt_selected
        assert theme.pt_hint


def test_everforest_is_default() -> None:
    assert "everforest" in THEMES
    t = THEMES["everforest"]
    assert "#" in t.error  # hex colour


# ---- load_theme ----


def test_load_theme_builtin() -> None:
    t = load_theme("dracula")
    assert t is not None
    assert t.name == "dracula"
    assert t is THEMES["dracula"]


def test_load_theme_unknown_returns_none() -> None:
    assert load_theme("nonexistent-xyz") is None


def test_load_theme_custom_after_save(tmp_path: Path) -> None:
    custom = TuiTheme(
        name="mytest",
        error="#111111",
        success="#222222",
        warning="#333333",
        accent="#444444",
        muted="#555555",
        border="#444444",
        pt_selected="bold fg:#222222",
        pt_hint="fg:#555555",
    )
    save_custom_theme(custom)
    loaded = load_theme("mytest")
    assert loaded is not None
    assert loaded.name == "mytest"
    assert loaded.error == "#111111"


# ---- save_custom_theme ----


def test_save_custom_theme_creates_file() -> None:
    custom = TuiTheme(
        name="saveme",
        error="#aaa",
        success="#bbb",
        warning="#ccc",
        accent="#ddd",
        muted="#eee",
        border="#ddd",
        pt_selected="bold fg:#bbb",
        pt_hint="fg:#eee",
    )
    save_custom_theme(custom)
    td = themes_dir()
    assert (td / "saveme.toml").is_file()


def test_save_and_load_round_trip() -> None:
    original = THEMES["dracula"]
    custom = TuiTheme(
        name="dracula-copy",
        error=original.error,
        success=original.success,
        warning=original.warning,
        accent=original.accent,
        muted=original.muted,
        border=original.border,
        pt_selected=original.pt_selected,
        pt_hint=original.pt_hint,
    )
    save_custom_theme(custom)
    loaded = load_theme("dracula-copy")
    assert loaded is not None
    assert loaded.error == original.error
    assert loaded.pt_selected == original.pt_selected


# ---- import_theme_from_file ----


def test_import_theme_from_file_ok(tmp_path: Path) -> None:
    p = tmp_path / "mytheme.toml"
    _make_theme_toml(p, name="mytheme", error="#cafe00")
    t = import_theme_from_file(p)
    assert t.name == "mytheme"
    assert t.error == "#cafe00"
    assert t.pt_header == "bold"  # default


def test_import_theme_with_custom_pt_header(tmp_path: Path) -> None:
    p = tmp_path / "t.toml"
    _make_theme_toml(p)
    p.write_text(p.read_text() + 'pt_header = "bold italic"\n')
    t = import_theme_from_file(p)
    assert t.pt_header == "bold italic"


def test_import_theme_missing_field_raises(tmp_path: Path) -> None:
    p = tmp_path / "bad.toml"
    p.write_text('name = "bad"\nerror = "#ff0000"\n')  # missing several fields
    with pytest.raises(ValueError, match="missing fields"):
        import_theme_from_file(p)


def test_import_theme_bad_toml_raises(tmp_path: Path) -> None:
    p = tmp_path / "nottoml.toml"
    p.write_text("this is not [ valid toml =\n")
    with pytest.raises(ValueError, match="cannot read"):
        import_theme_from_file(p)


def test_import_theme_missing_file_raises(tmp_path: Path) -> None:
    p = tmp_path / "ghost.toml"
    with pytest.raises(ValueError, match="cannot read"):
        import_theme_from_file(p)


# ---- list_themes ----


def test_list_themes_includes_builtin() -> None:
    names = list_themes()
    assert "everforest" in names
    assert "dracula" in names
    assert "gruvbox" in names
    assert "tokyo-night" in names
    assert "catppuccin" in names


def test_list_themes_sorted() -> None:
    names = list_themes()
    assert names == sorted(names)


def test_list_themes_includes_custom_after_save() -> None:
    custom = TuiTheme(
        name="zzcustom",
        error="#111",
        success="#222",
        warning="#333",
        accent="#444",
        muted="#555",
        border="#444",
        pt_selected="bold fg:#222",
        pt_hint="fg:#555",
    )
    save_custom_theme(custom)
    assert "zzcustom" in list_themes()


def test_list_themes_no_duplicate_builtins() -> None:
    names = list_themes()
    assert len(names) == len(set(names))


# ---- themes_dir ----


def test_themes_dir_respects_veles_user_home(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    custom_home = tmp_path / "custom_home"
    monkeypatch.setenv("VELES_USER_HOME", str(custom_home))
    td = themes_dir()
    assert str(custom_home) in str(td)
    assert td.name == "themes"

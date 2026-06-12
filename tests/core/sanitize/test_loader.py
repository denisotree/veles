"""TOML loader + LRU cache + hierarchy (builtin → global → project)."""

from __future__ import annotations

from pathlib import Path

from veles.core.project import init_project
from veles.core.sanitize import loader as loader_mod


def _isolate_home(monkeypatch, tmp_path: Path) -> Path:
    """Point `~` at a tmp dir + clear the rule cache so a freshly
    populated `~/.veles/sanitize.toml` is observed."""
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    monkeypatch.setattr(
        "veles.core.sanitize.loader.Path.home",
        classmethod(lambda cls: fake_home),
    )
    monkeypatch.setattr(
        "veles.core.sanitize.builtin.Path.home",
        classmethod(lambda cls: fake_home),
    )
    loader_mod.clear_cache()
    return fake_home


def test_loader_returns_builtin_only_when_no_toml(monkeypatch, tmp_path: Path) -> None:
    _isolate_home(monkeypatch, tmp_path)
    rs = loader_mod.load_rules(None)
    names = [r.name for r in rs]
    assert "project_root" not in names  # no project
    assert "home_dir" in names


def test_loader_picks_up_global_toml(monkeypatch, tmp_path: Path) -> None:
    fake_home = _isolate_home(monkeypatch, tmp_path)
    (fake_home / ".veles").mkdir()
    (fake_home / ".veles" / "sanitize.toml").write_text(
        '[[rule]]\ntype = "literal"\npattern = "OPS-123"\nreplacement = "<ticket>"\n',
        encoding="utf-8",
    )
    loader_mod.clear_cache()
    rs = loader_mod.load_rules(None)
    assert rs.apply("see OPS-123") == "see <ticket>"


def test_loader_project_toml_extends_global(monkeypatch, tmp_path: Path) -> None:
    fake_home = _isolate_home(monkeypatch, tmp_path)
    (fake_home / ".veles").mkdir()
    (fake_home / ".veles" / "sanitize.toml").write_text(
        '[[rule]]\ntype = "literal"\npattern = "GLOBAL"\nreplacement = "<g>"\n',
        encoding="utf-8",
    )
    project = init_project(tmp_path / "p", name="p")
    (project.state_dir / "sanitize.toml").write_text(
        '[[rule]]\ntype = "regex"\npattern = "PROJ-[0-9]+"\nreplacement = "<proj>"\n',
        encoding="utf-8",
    )
    loader_mod.clear_cache()
    rs = loader_mod.load_rules(project)
    out = rs.apply("GLOBAL and PROJ-42")
    assert out == "<g> and <proj>"


def test_loader_invalid_regex_logged_and_skipped(monkeypatch, tmp_path: Path, caplog) -> None:
    """A broken local rule must not silently take the agent down."""
    fake_home = _isolate_home(monkeypatch, tmp_path)
    (fake_home / ".veles").mkdir()
    (fake_home / ".veles" / "sanitize.toml").write_text(
        '[[rule]]\ntype = "regex"\npattern = "(unclosed"\nreplacement = "x"\n'
        '[[rule]]\ntype = "literal"\npattern = "ok"\nreplacement = "OK"\n',
        encoding="utf-8",
    )
    loader_mod.clear_cache()
    import logging

    with caplog.at_level(logging.WARNING, logger="veles.core.sanitize.rule"):
        rs = loader_mod.load_rules(None)
    # The bad rule is dropped; the good one still works.
    assert rs.apply("this is ok") == "this is OK"
    assert any("invalid regex" in m for m in caplog.messages)


def test_loader_broken_toml_logged_and_skipped(monkeypatch, tmp_path: Path, caplog) -> None:
    fake_home = _isolate_home(monkeypatch, tmp_path)
    (fake_home / ".veles").mkdir()
    (fake_home / ".veles" / "sanitize.toml").write_text(
        "this = not valid TOML[\n", encoding="utf-8"
    )
    loader_mod.clear_cache()
    import logging

    with caplog.at_level(logging.WARNING, logger="veles.core.sanitize.loader"):
        rs = loader_mod.load_rules(None)
    # No crash — just builtins survive.
    assert "home_dir" in [r.name for r in rs]
    assert any("cannot read" in m for m in caplog.messages)


def test_loader_cache_keyed_by_project(monkeypatch, tmp_path: Path) -> None:
    """Two different projects must not share a cached RuleSet —
    otherwise `<project_a>` substitutions leak into project_b."""
    _isolate_home(monkeypatch, tmp_path)
    p1 = init_project(tmp_path / "p1", name="alpha")
    p2 = init_project(tmp_path / "p2", name="beta")
    loader_mod.clear_cache()
    rs1 = loader_mod.load_rules(p1)
    rs2 = loader_mod.load_rules(p2)
    assert rs1.apply(str(p1.root.resolve())) == "<alpha>"
    assert rs2.apply(str(p2.root.resolve())) == "<beta>"

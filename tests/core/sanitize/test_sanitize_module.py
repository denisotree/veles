"""End-to-end of the public `sanitize()` entry point."""

from __future__ import annotations

from pathlib import Path

from veles.core.context import reset_active_project, set_active_project
from veles.core.project import init_project
from veles.core.sanitize import sanitize
from veles.core.sanitize import loader as loader_mod


def _isolate_home(monkeypatch, tmp_path: Path) -> Path:
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


def test_sanitize_noop_on_empty() -> None:
    assert sanitize("") == ""


def test_sanitize_uses_current_project_when_unspecified(
    monkeypatch, tmp_path: Path
) -> None:
    _isolate_home(monkeypatch, tmp_path)
    project = init_project(tmp_path / "p", name="mind-palace")
    token = set_active_project(project)
    try:
        out = sanitize(f"open {project.root.resolve()}/wiki/index.md")
    finally:
        reset_active_project(token)
    assert out == "open <mind-palace>/wiki/index.md"


def test_sanitize_with_explicit_project_overrides_context(
    monkeypatch, tmp_path: Path
) -> None:
    _isolate_home(monkeypatch, tmp_path)
    ctx_project = init_project(tmp_path / "ctx", name="ctx-proj")
    explicit_project = init_project(tmp_path / "exp", name="exp-proj")
    token = set_active_project(ctx_project)
    try:
        out = sanitize(
            f"see {explicit_project.root.resolve()}", project=explicit_project
        )
    finally:
        reset_active_project(token)
    assert out == "see <exp-proj>"


def test_sanitize_runs_builtin_chain_in_one_call(monkeypatch, tmp_path: Path) -> None:
    """One pass over the full builtin chain — path, home, user, secret."""
    fake_home = _isolate_home(monkeypatch, tmp_path)
    monkeypatch.setattr(
        "veles.core.sanitize.builtin.getpass.getuser", lambda: "alicebob"
    )
    project = init_project(tmp_path / "p", name="proj")
    msg = (
        f"path={project.root.resolve()} "
        f"home={fake_home} "
        f"user=alicebob "
        f"key=sk-{'a' * 40}"
    )
    out = sanitize(msg, project=project)
    assert "<proj>" in out
    assert "~ " in out
    assert "<user>" in out
    assert "sk-<redacted>" in out
    assert "/Users/" not in out
    assert "alicebob" not in out


def test_sanitize_idempotent(monkeypatch, tmp_path: Path) -> None:
    _isolate_home(monkeypatch, tmp_path)
    project = init_project(tmp_path / "p", name="p")
    msg = f"{project.root.resolve()}/x and Bearer {'z' * 30}"
    once = sanitize(msg, project=project)
    twice = sanitize(once, project=project)
    assert once == twice

"""Built-in rules — project_root, home_dir, os_user, secrets."""

from __future__ import annotations

from pathlib import Path

from veles.core.project import init_project
from veles.core.sanitize.builtin import builtin_rules
from veles.core.sanitize.rule import RuleSet


def _rs_for(project_name: str | None, project_root: Path | None) -> RuleSet:
    return RuleSet(builtin_rules(project_name, project_root))


def test_project_root_rule_collapses_abs_path(tmp_path: Path) -> None:
    p = init_project(tmp_path / "mp", name="mind-palace")
    rs = _rs_for(p.name, p.root)
    assert rs.apply(f"see {p.root.resolve()}/wiki/foo.md") == "see <mind-palace>/wiki/foo.md"


def test_project_root_rule_skipped_without_project() -> None:
    """Context-free callers (e.g. background workers) still get $HOME /
    secrets coverage but no project rule is emitted."""
    rs = _rs_for(None, None)
    names = [r.name for r in rs]
    assert "project_root" not in names


def test_home_dir_rule_present_and_applies(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        "veles.core.sanitize.builtin.Path.home",
        classmethod(lambda cls: tmp_path / "fakehome"),
    )
    (tmp_path / "fakehome").mkdir()
    rs = _rs_for(None, None)
    out = rs.apply(f"file at {tmp_path / 'fakehome'}/notes.md")
    assert out == "file at ~/notes.md"


def test_os_user_rule_redacts_username(monkeypatch) -> None:
    monkeypatch.setattr("veles.core.sanitize.builtin.getpass.getuser", lambda: "alicebob")
    rs = _rs_for(None, None)
    assert rs.apply("from alicebob to root") == "from <user> to root"


def test_os_user_rule_skipped_when_username_short(monkeypatch) -> None:
    """Single-letter / two-letter usernames would over-match — `os_user`
    is omitted when the value is <3 chars."""
    monkeypatch.setattr("veles.core.sanitize.builtin.getpass.getuser", lambda: "al")
    rs = _rs_for(None, None)
    assert "alpha" in rs.apply("alpha")  # not touched
    names = [r.name for r in rs]
    assert "os_user" not in names


def test_secret_openai_redacted(monkeypatch) -> None:
    monkeypatch.setattr("veles.core.sanitize.builtin.getpass.getuser", lambda: "")
    rs = _rs_for(None, None)
    s = "OPENAI=sk-" + "a" * 48
    assert rs.apply(s) == "OPENAI=sk-<redacted>"


def test_secret_anthropic_redacted_before_openai(monkeypatch) -> None:
    """`sk-ant-...` starts with `sk-`. If the OpenAI rule fires first
    it eats the `sk-` prefix and leaves `ant-...` exposed. The order in
    `builtin_rules` puts Anthropic first to avoid that."""
    monkeypatch.setattr("veles.core.sanitize.builtin.getpass.getuser", lambda: "")
    rs = _rs_for(None, None)
    s = "ANTHROPIC=sk-ant-" + "b" * 40
    assert rs.apply(s) == "ANTHROPIC=sk-ant-<redacted>"


def test_secret_aws_redacted(monkeypatch) -> None:
    monkeypatch.setattr("veles.core.sanitize.builtin.getpass.getuser", lambda: "")
    rs = _rs_for(None, None)
    assert rs.apply("AWS key AKIAABCDEFGHIJKLMNOP is hot") == "AWS key AKIA<redacted> is hot"


def test_secret_bearer_redacted(monkeypatch) -> None:
    monkeypatch.setattr("veles.core.sanitize.builtin.getpass.getuser", lambda: "")
    rs = _rs_for(None, None)
    s = "Authorization: Bearer " + "x" * 30
    assert rs.apply(s) == "Authorization: Bearer <token>"


def test_idempotent_under_repeated_application(tmp_path: Path) -> None:
    p = init_project(tmp_path / "p", name="proj")
    rs = _rs_for(p.name, p.root)
    msg = f"path: {p.root.resolve()}, key sk-{'z' * 40}, bearer Bearer {'y' * 30}"
    once = rs.apply(msg)
    twice = rs.apply(once)
    assert once == twice

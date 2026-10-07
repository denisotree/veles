"""`bare` is the default layout; projects from before layouts existed stay
`llm-wiki`; `veles init` with a layout that isn't installed offers it and creates
nothing when it can't be had."""

from __future__ import annotations

from pathlib import Path

import pytest

from veles.core.project import LAYOUT_DEFAULT, LEGACY_LAYOUT, init_project, load_project


@pytest.fixture()
def home(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("VELES_USER_HOME", str(tmp_path / "home"))
    monkeypatch.setenv("VELES_NO_WIZARD", "1")
    return tmp_path


def test_constants() -> None:
    assert LAYOUT_DEFAULT == "bare"
    assert LEGACY_LAYOUT == "llm-wiki"


def test_init_project_defaults_to_bare(home) -> None:
    project = init_project(home / "p", name="p")
    assert project.layout_name == "bare"
    assert load_project(project.root).layout_name == "bare"
    assert not (project.root / "wiki").exists()


def test_project_without_layout_key_is_legacy_llm_wiki(home) -> None:
    project = init_project(home / "p", name="p")
    toml = project.state_dir / "project.toml"
    text = toml.read_text(encoding="utf-8")
    toml.write_text(
        "\n".join(line for line in text.splitlines() if not line.startswith("layout")),
        encoding="utf-8",
    )
    assert load_project(project.root).layout_name == "llm-wiki"


def test_cli_init_without_layout_and_tty_is_bare(home, monkeypatch) -> None:
    from veles.cli import main

    monkeypatch.chdir(home)
    (home / "p").mkdir()
    monkeypatch.chdir(home / "p")
    assert main(["init"]) == 0
    assert load_project(home / "p").layout_name == "bare"


def test_cli_init_with_a_missing_layout_creates_nothing(home, monkeypatch, capsys) -> None:
    from veles.cli import main
    from veles.core.registry import ensure

    asked: list[object] = []

    def refuse(need, project, *, interactive):
        asked.append(need)
        return False

    monkeypatch.setattr(ensure, "ensure_extension", refuse)
    (home / "p").mkdir()
    monkeypatch.chdir(home / "p")
    assert main(["init", "--layout", "ghost-pack"]) == 1
    assert asked == [ensure.LayoutNeed("ghost-pack")]
    assert not (home / "p" / ".veles").exists()
    assert "ghost-pack" in capsys.readouterr().err


def test_cli_init_asks_for_a_layout_at_a_tty(home, monkeypatch) -> None:
    from veles.cli import main
    from veles.cli.commands import init as init_cmd

    pack = home / "home" / ".veles" / "layouts" / "journal"
    pack.mkdir(parents=True)
    (pack / "layout.toml").write_text('[layout]\nname = "journal"\n', encoding="utf-8")
    seen: list[str] = []
    answers = iter(["no-such-layout", "journal"])  # a wrong answer is asked again

    def prompter(prompt: str, default: str | None) -> str:
        seen.append(prompt)
        return next(answers)

    monkeypatch.setattr(init_cmd, "_is_tty", lambda: True)
    monkeypatch.setattr(init_cmd, "_prompter", prompter)
    (home / "p").mkdir()
    monkeypatch.chdir(home / "p")
    assert main(["init"]) == 0
    assert "bare" in seen[0] and "journal" in seen[0]
    assert len(seen) == 2
    assert load_project(home / "p").layout_name == "journal"

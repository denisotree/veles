"""M117e: LayoutPickerStep — wizard step that lets the user choose a
layout-pack at init time.

We don't exercise the Textual UI directly here (other wizard tests
do that via run_test); these unit-test the step's branching against
a stub WizardContext + stub `push_screen_wait`. That keeps the test
fast and lets us assert the project.toml rewrite without spinning up
Textual.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest

from veles.core.project import init_project, load_project
from veles.tui.wizard.project_steps import LayoutPickerStep
from veles.tui.wizard.step import WizardOutcome


@dataclass
class _StubApp:
    """Mimics the bits of Textual's App that the step touches."""

    responses: list[Any] = field(default_factory=list)
    pushed: list[Any] = field(default_factory=list)

    async def push_screen_wait(self, screen: Any) -> Any:
        self.pushed.append(screen)
        if not self.responses:
            raise AssertionError("test queued no response for push_screen_wait")
        return self.responses.pop(0)


@dataclass
class _StubCtx:
    app: _StubApp
    answers: dict[str, Any] = field(default_factory=dict)


@pytest.fixture()
def isolated_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("VELES_USER_HOME", str(tmp_path / "home"))
    return tmp_path / "home"


def _write_user_pack(
    isolated_home: Path, name: str, description: str = ""
) -> Path:
    pack_dir = isolated_home / ".veles" / "layouts" / name
    pack_dir.mkdir(parents=True, exist_ok=True)
    (pack_dir / "layout.toml").write_text(
        f'[layout]\nname = "{name}"\ndescription = "{description}"\n',
        encoding="utf-8",
    )
    return pack_dir


# ---- single-pack: auto-confirm ----


async def test_single_pack_auto_confirms_without_screen(
    isolated_home: Path, tmp_path: Path
) -> None:
    """Only the builtin pack is available → step doesn't show UI;
    just records the default and proceeds."""
    project = init_project(tmp_path / "proj", name="proj")
    app = _StubApp()  # no responses queued — none should be needed
    ctx = _StubCtx(app=app, answers={"project": project})
    step = LayoutPickerStep()
    outcome = await step.run(ctx)
    assert outcome == WizardOutcome.NEXT
    assert ctx.answers["layout"] == "llm-wiki"
    assert app.pushed == []


# ---- multi-pack: picker offered ----


async def test_picker_shown_when_multiple_packs(
    isolated_home: Path, tmp_path: Path
) -> None:
    _write_user_pack(isolated_home, "obsidian-import", "Mind Palace mapper")
    project = init_project(tmp_path / "proj", name="proj")
    app = _StubApp(responses=["obsidian-import"])
    ctx = _StubCtx(app=app, answers={"project": project})
    outcome = await LayoutPickerStep().run(ctx)
    assert outcome == WizardOutcome.NEXT
    assert ctx.answers["layout"] == "obsidian-import"
    # Picker screen was shown exactly once
    assert len(app.pushed) == 1


async def test_picker_rewrites_project_toml(
    isolated_home: Path, tmp_path: Path
) -> None:
    """After picking a non-default pack, project.toml's `layout` field
    is rewritten so the next `veles run` sees the choice."""
    _write_user_pack(isolated_home, "obsidian-import")
    project = init_project(tmp_path / "proj", name="proj")
    assert project.layout_name == "llm-wiki"

    app = _StubApp(responses=["obsidian-import"])
    ctx = _StubCtx(app=app, answers={"project": project})
    await LayoutPickerStep().run(ctx)

    # In-memory project reflects the change
    assert project.layout_name == "obsidian-import"
    # Reloading from disk also sees it
    reloaded = load_project(project.root)
    assert reloaded.layout_name == "obsidian-import"


async def test_picker_keeps_existing_when_same_chosen(
    isolated_home: Path, tmp_path: Path
) -> None:
    """If the user picks the layout already in use, we don't rewrite
    project.toml needlessly."""
    _write_user_pack(isolated_home, "obsidian-import")
    project = init_project(tmp_path / "proj", name="proj")
    mtime_before = project.project_toml_path.stat().st_mtime

    app = _StubApp(responses=["llm-wiki"])  # picked same as current
    ctx = _StubCtx(app=app, answers={"project": project})
    outcome = await LayoutPickerStep().run(ctx)
    assert outcome == WizardOutcome.NEXT
    mtime_after = project.project_toml_path.stat().st_mtime
    # mtime unchanged → no rewrite
    assert mtime_after == mtime_before


async def test_picker_esc_returns_back_signal(
    isolated_home: Path, tmp_path: Path
) -> None:
    """Esc on the picker (push_screen_wait returns None) → `_nav`
    helper translates that to BACK so the wizard runner can step
    backwards. project.toml stays untouched."""
    _write_user_pack(isolated_home, "obsidian-import")
    project = init_project(tmp_path / "proj", name="proj")
    app = _StubApp(responses=[None])
    ctx = _StubCtx(app=app, answers={"project": project})
    outcome = await LayoutPickerStep().run(ctx)
    assert outcome == WizardOutcome.BACK
    # No rewrite happened — current layout preserved
    assert project.layout_name == "llm-wiki"


# ---- safety: project missing ----


async def test_picker_without_project_in_ctx_skips(tmp_path: Path) -> None:
    """If BootstrapStep didn't land a project (shouldn't happen, but
    defensive), the picker no-ops rather than crashing."""
    app = _StubApp()
    ctx = _StubCtx(app=app)  # no `project` key
    outcome = await LayoutPickerStep().run(ctx)
    assert outcome == WizardOutcome.NEXT
    assert app.pushed == []

"""M117e/M162: LayoutPickerStep — wizard step that lets the user choose
a layout-pack at init time. M162 moved it BEFORE BootstrapStep: the
picker only records `ctx.answers["layout"]`; BootstrapStep passes it to
`init_project(layout=...)`, which scaffolds the chosen pack directly.

We don't exercise the Textual UI directly here (other wizard tests
do that via run_test); these unit-test the step's branching against
a stub WizardContext + stub `push_screen_wait`.
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


# ---- builtin packs: picker offered, default llm-wiki ----


async def test_builtin_packs_offer_picker_with_llm_wiki_default(
    isolated_home: Path, tmp_path: Path
) -> None:
    """M164 ships three builtin packs (llm-wiki / bare / notes), so the
    picker always shows; accepting the default records llm-wiki."""
    app = _StubApp(responses=["llm-wiki"])
    ctx = _StubCtx(app=app)
    step = LayoutPickerStep()
    outcome = await step.run(ctx)
    assert outcome == WizardOutcome.NEXT
    assert ctx.answers["layout"] == "llm-wiki"
    assert len(app.pushed) == 1


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


async def test_picked_layout_flows_into_init(
    isolated_home: Path, tmp_path: Path
) -> None:
    """M162: the picker records the answer; init_project(layout=picked)
    persists it in project.toml so the next `veles run` sees it."""
    _write_user_pack(isolated_home, "obsidian-import")
    app = _StubApp(responses=["obsidian-import"])
    ctx = _StubCtx(app=app)
    await LayoutPickerStep().run(ctx)
    assert ctx.answers["layout"] == "obsidian-import"

    project = init_project(
        tmp_path / "proj", name="proj", layout=ctx.answers["layout"]
    )
    assert project.layout_name == "obsidian-import"
    reloaded = load_project(project.root)
    assert reloaded.layout_name == "obsidian-import"


async def test_picker_esc_returns_back_signal(
    isolated_home: Path, tmp_path: Path
) -> None:
    """Esc on the picker (push_screen_wait returns None) → `_nav`
    helper translates that to BACK so the wizard runner can step
    backwards."""
    _write_user_pack(isolated_home, "obsidian-import")
    app = _StubApp(responses=[None])
    ctx = _StubCtx(app=app)
    outcome = await LayoutPickerStep().run(ctx)
    assert outcome == WizardOutcome.BACK
    assert "layout" not in ctx.answers


# ---- safety: pre-bootstrap (no project in ctx) ----


async def test_picker_runs_without_project_in_ctx(tmp_path: Path) -> None:
    """M162: the picker runs BEFORE bootstrap, so there is never a
    project in ctx — picking a builtin pack just records the answer."""
    app = _StubApp(responses=["bare"])
    ctx = _StubCtx(app=app)  # no `project` key
    outcome = await LayoutPickerStep().run(ctx)
    assert outcome == WizardOutcome.NEXT
    assert ctx.answers["layout"] == "bare"

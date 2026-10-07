"""`prompt` contributions: module blocks in the stable system prompt.

The snapshot under `tests/fixtures/prompt/` was taken from 1.2.1's builder
before the wiki blocks moved into the wiki module — the cache prefix must not
change by a byte. (The llm-wiki snapshot is checked with the wiki module.)
"""

from __future__ import annotations

from pathlib import Path

import pytest

import veles.runtime.prompt as prompt_mod
from veles.core.modules import ModuleAPI, ModuleRegistry, reset_module_registry, set_module_registry
from veles.core.project import init_project

_FIXTURES = Path(__file__).parent / "fixtures" / "prompt"


@pytest.fixture()
def build(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("VELES_USER_HOME", str(tmp_path / "home"))
    monkeypatch.setattr(prompt_mod, "_runtime_clock_block", lambda: "<clock>")

    def _build(layout: str):
        p = init_project(tmp_path / layout, name="snap", layout=layout)
        (p.root / "notes.md").write_text("x")
        return p, prompt_mod.build_run_system_prompt(p, prompt="")

    return _build


def test_prompt_is_byte_identical_to_1_2_1(build) -> None:
    project, out = build("bare")
    expected = (_FIXTURES / "bare.txt").read_text(encoding="utf-8")
    assert out is not None
    assert out.replace(str(project.root), "<ROOT>") == expected


def test_contributed_block_lands_in_the_stable_prompt(build) -> None:
    def block(project, *, include_index: bool) -> list[str]:
        return [f"<fake-module-block index={include_index}>"]

    scratch, reg = ModuleRegistry(), ModuleRegistry()
    ModuleAPI(scratch, "m").contribute("prompt", "fake", block)
    reg.merge_from(scratch, "m")
    token = set_module_registry(reg)
    try:
        _p, out = build("bare")
    finally:
        reset_module_registry(token)
    assert out is not None and "<fake-module-block index=True>" in out
    assert out.index("<fake-module-block") < out.index("<clock>")  # stable, before volatile

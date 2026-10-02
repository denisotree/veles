"""`self_doc` and `scaffold` contributions."""

from __future__ import annotations

from pathlib import Path

import pytest

from veles.core.modules import ModuleAPI, ModuleRegistry, reset_module_registry, set_module_registry
from veles.core.project import init_project


@pytest.fixture()
def home(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("VELES_USER_HOME", str(tmp_path / "home"))
    return tmp_path


def _with(point: str, name: str, obj: object):
    scratch, reg = ModuleRegistry(), ModuleRegistry()
    ModuleAPI(scratch, "m").contribute(point, name, obj)
    reg.merge_from(scratch, "m")
    return set_module_registry(reg)


def test_contributed_self_doc_writer_takes_the_document(home) -> None:
    from veles.core.self_doc import refresh_self_doc

    project = init_project(home / "b", name="b", layout="bare")
    got: list[str] = []

    def writer(proj, content: str) -> str | None:
        got.append(content)
        return "fake/self-doc.md"

    token = _with("self_doc", "fake", writer)
    try:
        rel = refresh_self_doc(project)
    finally:
        reset_module_registry(token)
    assert rel == "fake/self-doc.md" and got


def test_self_doc_falls_back_to_memory_when_no_writer_takes_it(home) -> None:
    from veles.core.self_doc import refresh_self_doc

    project = init_project(home / "b", name="b", layout="bare")
    token = _with("self_doc", "fake", lambda proj, content: None)
    try:
        rel = refresh_self_doc(project)
    finally:
        reset_module_registry(token)
    assert rel == ".veles/memory/self-doc.md"


def test_contributed_scaffold_runs_for_every_pack(home) -> None:
    from veles.core.layout.discovery import find_layout
    from veles.core.layout.scaffold import apply_scaffold

    seen: list[str] = []
    (home / "proj").mkdir()
    token = _with("scaffold", "fake", lambda root, manifest: seen.append(manifest.name))
    try:
        apply_scaffold(find_layout("bare", None), home / "proj", "proj")
    finally:
        reset_module_registry(token)
    assert seen == ["bare"]

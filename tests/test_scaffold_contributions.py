"""`scaffold` contributions."""

from __future__ import annotations

from pathlib import Path

import pytest

from veles.core.modules import ModuleAPI, ModuleRegistry, reset_module_registry, set_module_registry


@pytest.fixture()
def home(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("VELES_USER_HOME", str(tmp_path / "home"))
    return tmp_path


def _with(point: str, name: str, obj: object):
    scratch, reg = ModuleRegistry(), ModuleRegistry()
    ModuleAPI(scratch, "m").contribute(point, name, obj)
    reg.merge_from(scratch, "m")
    return set_module_registry(reg)


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

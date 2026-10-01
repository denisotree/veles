"""`tool` contributions: module tool sets, gated by the engine they belong to."""

from __future__ import annotations

from pathlib import Path

import pytest

from veles.core.contributions import Engine, ToolSet, load_tool_sets
from veles.core.layout import clear_engine_cache
from veles.core.modules import ModuleAPI, ModuleRegistry, reset_module_registry, set_module_registry
from veles.core.project import init_project


@pytest.fixture(autouse=True)
def _fresh_engine_cache():
    clear_engine_cache()
    yield
    clear_engine_cache()


def _project(tmp_path: Path, monkeypatch, *, engines: str):
    home = tmp_path / "home"
    monkeypatch.setenv("VELES_USER_HOME", str(home))
    pack = home / ".veles" / "layouts" / "fakepack"
    pack.mkdir(parents=True)
    (pack / "layout.toml").write_text(f'[layout]\nname = "fakepack"\n{engines}', encoding="utf-8")
    return init_project(tmp_path / "p", name="p", layout="fakepack")


def _contribute_fake(loads: list[int]):
    scratch, reg = ModuleRegistry(), ModuleRegistry()
    api = ModuleAPI(scratch, "fake-mod")
    api.contribute("engine", "fake", Engine("fake"))
    api.contribute(
        "tool",
        "fake",
        ToolSet(load=lambda: loads.append(1), tools=("fake_do",), engine="fake"),
    )
    reg.merge_from(scratch, "fake-mod")
    return set_module_registry(reg)


def test_tool_set_of_an_engine_the_layout_does_not_enable_is_gated(tmp_path, monkeypatch) -> None:
    project = _project(tmp_path, monkeypatch, engines="")
    loads: list[int] = []
    token = _contribute_fake(loads)
    try:
        gated = load_tool_sets(project)
    finally:
        reset_module_registry(token)
    assert "fake_do" in gated
    assert loads == []  # never imported


def test_tool_set_of_an_enabled_engine_is_loaded(tmp_path, monkeypatch) -> None:
    project = _project(tmp_path, monkeypatch, engines="[layout.engines]\nfake = true\n")
    loads: list[int] = []
    token = _contribute_fake(loads)
    try:
        gated = load_tool_sets(project)
    finally:
        reset_module_registry(token)
    assert "fake_do" not in gated
    assert loads == [1]


def test_mcp_server_hides_wiki_tools_on_a_bare_project(tmp_path, monkeypatch) -> None:
    import io
    import json

    from veles.adapters.cli.mcp_server import main

    monkeypatch.setenv("VELES_USER_HOME", str(tmp_path / "home"))
    project = init_project(tmp_path / "b", name="b", layout="bare")
    request = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/list"}) + "\n"
    monkeypatch.setattr("sys.stdin", io.StringIO(request))
    out = io.StringIO()
    monkeypatch.setattr("sys.stdout", out)
    main(["--project-root", str(project.root)])
    names = {t["name"] for t in json.loads(out.getvalue().splitlines()[0])["result"]["tools"]}
    assert "read_file" in names
    assert not any(n.startswith("wiki_") for n in names)

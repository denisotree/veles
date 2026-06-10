"""Unit tests for module discovery, loading, and hook dispatch."""

from __future__ import annotations

from pathlib import Path

import pytest

from veles.core.modules import (
    ModuleAPI,
    ModuleLoadError,
    ModuleRegistry,
    VetoResult,
    current_module_registry,
    discover_modules,
    fire_hook,
    load_module,
    reset_module_registry,
    set_module_registry,
)
from veles.core.project import init_project


def _write_module(
    modules_dir: Path,
    name: str,
    *,
    body: str,
    entrypoint: str = "main.py:register",
    description: str = "Test module",
    version: str | None = "0.1.0",
) -> Path:
    mod_dir = modules_dir / name
    mod_dir.mkdir(parents=True, exist_ok=True)
    version_line = f'version = "{version}"\n' if version else ""
    (mod_dir / "module.toml").write_text(
        f"[module]\n"
        f'name = "{name}"\n'
        f'description = "{description}"\n'
        f'entrypoint = "{entrypoint}"\n'
        f"{version_line}",
        encoding="utf-8",
    )
    (mod_dir / "main.py").write_text(body, encoding="utf-8")
    return mod_dir


# ---- discover_modules ----


def test_discover_modules_finds_valid_directories(tmp_path: Path) -> None:
    project = init_project(tmp_path / "p", name="p")
    project.modules_dir.mkdir(parents=True, exist_ok=True)
    _write_module(project.modules_dir, "alpha", body="def register(api): pass")
    _write_module(project.modules_dir, "beta", body="def register(api): pass")
    handles = discover_modules(project)
    assert [h.name for h in handles] == ["alpha", "beta"]


def test_discover_modules_skips_missing_manifest(tmp_path: Path) -> None:
    project = init_project(tmp_path / "p", name="p")
    project.modules_dir.mkdir(parents=True, exist_ok=True)
    (project.modules_dir / "stub").mkdir()
    (project.modules_dir / "stub" / "main.py").write_text("# no manifest")
    assert discover_modules(project) == []


def test_discover_modules_skips_invalid_toml(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    project = init_project(tmp_path / "p", name="p")
    project.modules_dir.mkdir(parents=True, exist_ok=True)
    bad = project.modules_dir / "bad"
    bad.mkdir()
    (bad / "module.toml").write_text("[module\nbroken", encoding="utf-8")
    assert discover_modules(project) == []
    err = capsys.readouterr().err
    assert "skipping module" in err


def test_discover_modules_returns_empty_when_modules_dir_missing(tmp_path: Path) -> None:
    project = init_project(tmp_path / "p", name="p")
    assert discover_modules(project) == []


# ---- load_module ----


def test_load_module_calls_register_with_api(tmp_path: Path) -> None:
    project = init_project(tmp_path / "p", name="p")
    project.modules_dir.mkdir(parents=True, exist_ok=True)
    _write_module(
        project.modules_dir,
        "logger",
        body=("def register(api):\n    api.add_hook('pre_tool_call', lambda ctx: None)\n"),
    )
    handles = discover_modules(project)
    registry = ModuleRegistry()
    load_module(handles[0], registry)
    assert registry.modules == ["logger"]
    assert next(iter(registry.iter_hooks("pre_tool_call")))[0] == "logger"


def test_load_module_raises_on_missing_entrypoint_file(tmp_path: Path) -> None:
    project = init_project(tmp_path / "p", name="p")
    project.modules_dir.mkdir(parents=True, exist_ok=True)
    mod_dir = project.modules_dir / "broken"
    mod_dir.mkdir()
    (mod_dir / "module.toml").write_text(
        '[module]\nname = "broken"\ndescription = "x"\nentrypoint = "missing.py:register"\n',
        encoding="utf-8",
    )
    handles = discover_modules(project)
    with pytest.raises(ModuleLoadError, match="not found"):
        load_module(handles[0], ModuleRegistry())


def test_load_module_raises_on_register_exception(tmp_path: Path) -> None:
    project = init_project(tmp_path / "p", name="p")
    project.modules_dir.mkdir(parents=True, exist_ok=True)
    _write_module(
        project.modules_dir,
        "boom",
        body="def register(api):\n    raise RuntimeError('nope')\n",
    )
    handles = discover_modules(project)
    with pytest.raises(ModuleLoadError, match=r"register\(\) raised"):
        load_module(handles[0], ModuleRegistry())


def test_load_module_raises_when_register_not_callable(tmp_path: Path) -> None:
    project = init_project(tmp_path / "p", name="p")
    project.modules_dir.mkdir(parents=True, exist_ok=True)
    _write_module(
        project.modules_dir,
        "notcallable",
        body="register = 42\n",
    )
    handles = discover_modules(project)
    with pytest.raises(ModuleLoadError, match="not callable"):
        load_module(handles[0], ModuleRegistry())


# ---- ModuleRegistry / ModuleAPI ----


def test_module_api_validates_hook_name() -> None:
    api = ModuleAPI(ModuleRegistry(), "x")
    with pytest.raises(ValueError, match="unknown hook"):
        api.add_hook("not_a_hook", lambda ctx: None)


def test_module_api_add_hook_stores_in_registry() -> None:
    reg = ModuleRegistry()
    api = ModuleAPI(reg, "alpha")
    seen = []
    api.add_hook("pre_turn", lambda ctx: seen.append(ctx))
    [(_name, fn)] = list(reg.iter_hooks("pre_turn"))
    fn({"foo": 1})
    assert seen == [{"foo": 1}]


def test_registry_iter_hooks_preserves_order() -> None:
    reg = ModuleRegistry()
    reg.add_hook("pre_turn", "a", lambda ctx: None)
    reg.add_hook("pre_turn", "b", lambda ctx: None)
    reg.add_hook("pre_turn", "c", lambda ctx: None)
    assert [n for n, _ in reg.iter_hooks("pre_turn")] == ["a", "b", "c"]


# ---- fire_hook ----


def test_fire_hook_no_op_when_registry_is_none() -> None:
    # No registry set; should not raise.
    fire_hook("pre_turn", turn=1)


def test_fire_hook_calls_all_hooks(tmp_path: Path) -> None:
    reg = ModuleRegistry()
    seen = []
    reg.add_hook("pre_turn", "a", lambda ctx: seen.append(("a", ctx["turn"])))
    reg.add_hook("pre_turn", "b", lambda ctx: seen.append(("b", ctx["turn"])))
    token = set_module_registry(reg)
    try:
        fire_hook("pre_turn", turn=7)
    finally:
        reset_module_registry(token)
    assert seen == [("a", 7), ("b", 7)]


def test_fire_hook_isolates_failing_hook(
    capsys: pytest.CaptureFixture[str],
) -> None:
    reg = ModuleRegistry()
    seen = []

    def boom(ctx):
        raise RuntimeError("kaboom")

    reg.add_hook("pre_turn", "bad", boom)
    reg.add_hook("pre_turn", "good", lambda ctx: seen.append(ctx["turn"]))
    token = set_module_registry(reg)
    try:
        fire_hook("pre_turn", turn=3)
    finally:
        reset_module_registry(token)
    assert seen == [3]
    err = capsys.readouterr().err
    assert "bad" in err
    assert "kaboom" in err


def test_set_reset_module_registry_isolates_state() -> None:
    assert current_module_registry() is None
    reg = ModuleRegistry()
    token = set_module_registry(reg)
    try:
        assert current_module_registry() is reg
    finally:
        reset_module_registry(token)
    assert current_module_registry() is None


# ---- VetoResult / fire_hook return ----


def test_fire_hook_returns_none_when_callbacks_return_none() -> None:
    reg = ModuleRegistry()
    reg.add_hook("pre_tool_call", "a", lambda ctx: None)
    reg.add_hook("pre_tool_call", "b", lambda ctx: None)
    token = set_module_registry(reg)
    try:
        assert fire_hook("pre_tool_call", name="x", arguments={}) is None
    finally:
        reset_module_registry(token)


def test_fire_hook_returns_first_veto_with_module_name_populated() -> None:
    reg = ModuleRegistry()
    reg.add_hook("pre_tool_call", "guard", lambda ctx: VetoResult(reason="blocked"))
    reg.add_hook("pre_tool_call", "later", lambda ctx: VetoResult(reason="also blocked"))
    token = set_module_registry(reg)
    try:
        veto = fire_hook("pre_tool_call", name="rm", arguments={"path": "/etc"})
    finally:
        reset_module_registry(token)
    assert veto is not None
    assert veto.reason == "blocked"
    assert veto.module_name == "guard"


def test_fire_hook_runs_all_callbacks_even_when_one_vetoes() -> None:
    reg = ModuleRegistry()
    seen: list[str] = []
    reg.add_hook("pre_tool_call", "guard", lambda ctx: VetoResult(reason="no"))
    reg.add_hook("pre_tool_call", "logger", lambda ctx: seen.append(ctx["name"]))
    token = set_module_registry(reg)
    try:
        veto = fire_hook("pre_tool_call", name="rm", arguments={})
    finally:
        reset_module_registry(token)
    assert veto is not None
    assert veto.module_name == "guard"
    assert seen == ["rm"]


def test_fire_hook_continues_after_failing_callback_for_veto() -> None:
    reg = ModuleRegistry()

    def boom(ctx):
        raise RuntimeError("bad")

    reg.add_hook("pre_tool_call", "broken", boom)
    reg.add_hook("pre_tool_call", "guard", lambda ctx: VetoResult(reason="no"))
    token = set_module_registry(reg)
    try:
        veto = fire_hook("pre_tool_call", name="rm", arguments={})
    finally:
        reset_module_registry(token)
    assert veto is not None
    assert veto.module_name == "guard"


def test_on_session_hooks_registered() -> None:
    reg = ModuleRegistry()
    reg.add_hook("on_session_start", "x", lambda ctx: None)
    reg.add_hook("on_session_end", "x", lambda ctx: None)
    assert [n for n, _ in reg.iter_hooks("on_session_start")] == ["x"]
    assert [n for n, _ in reg.iter_hooks("on_session_end")] == ["x"]

from pathlib import Path

import pytest

from veles.cli._project import _load_project_modules
from veles.core.path_guard import SandboxViolation, resolve_safe
from veles.core.project import init_project
from veles.core.registry.gate import approve_module
from veles.core.registry.records import record_for_path
from veles.core.user_paths import user_modules_dir


def _module(root: Path, name: str, hook: str = "pre_turn") -> Path:
    d = root / name
    d.mkdir(parents=True)
    (d / "module.toml").write_text(
        f'[module]\nname = "{name}"\ndescription = "d"\nentrypoint = "m.py:register"\n',
        encoding="utf-8",
    )
    (d / "m.py").write_text(
        f"def register(api):\n    api.add_hook({hook!r}, lambda **kw: None)\n", encoding="utf-8"
    )
    return d


def test_user_module_loads_in_any_project(tmp_path: Path) -> None:
    d = _module(user_modules_dir(), "u1")
    approve_module(d, name="u1", project_root=None)
    assert record_for_path(str(d.resolve())).project is None
    for proj in ("a", "b"):
        project = init_project(tmp_path / proj, name=proj)
        assert _load_project_modules(project).modules == ["u1"]


def test_user_modules_load_before_project_modules(tmp_path: Path) -> None:
    project = init_project(tmp_path / "p", name="p")
    approve_module(_module(user_modules_dir(), "u1"), name="u1", project_root=None)
    approve_module(_module(project.modules_dir, "p1"), name="p1", project_root=project.root)
    assert _load_project_modules(project).modules == ["u1", "p1"]


def test_project_module_overrides_user_module(tmp_path: Path, capsys) -> None:
    project = init_project(tmp_path / "p", name="p")
    approve_module(_module(user_modules_dir(), "same"), name="same", project_root=None)
    approve_module(
        _module(project.modules_dir, "same", hook="post_turn"),
        name="same",
        project_root=project.root,
    )
    registry = _load_project_modules(project)
    assert registry.modules == ["same"]
    assert [m for m, _ in registry.iter_hooks("post_turn")] == ["same"]
    assert [m for m, _ in registry.iter_hooks("pre_turn")] == []
    assert "overrides the user-level one" in capsys.readouterr().err


def test_changed_user_module_is_refused(tmp_path: Path, capsys) -> None:
    project = init_project(tmp_path / "p", name="p")
    d = _module(user_modules_dir(), "u1")
    approve_module(d, name="u1", project_root=None)
    (d / "m.py").write_text("raise SystemExit('tampered')\n", encoding="utf-8")
    assert _load_project_modules(project).modules == []
    assert "u1" in capsys.readouterr().err


def test_duplicate_module_name_in_same_scope_is_ignored(tmp_path: Path, capsys) -> None:
    project = init_project(tmp_path / "p", name="p")
    d1 = _module(user_modules_dir(), "aaa-dup")
    d2 = user_modules_dir() / "zzz-dup"
    d2.mkdir(parents=True)
    (d2 / "module.toml").write_text(
        '[module]\nname = "aaa-dup"\ndescription = "d2"\nentrypoint = "m.py:register"\n',
        encoding="utf-8",
    )
    (d2 / "m.py").write_text(
        "def register(api):\n    api.add_hook('post_turn', lambda **kw: None)\n",
        encoding="utf-8",
    )
    approve_module(d1, name="aaa-dup", project_root=None)
    approve_module(d2, name="aaa-dup", project_root=None)
    registry = _load_project_modules(project)
    assert registry.modules == ["aaa-dup"]
    assert [m for m, _ in registry.iter_hooks("pre_turn")] == ["aaa-dup"]
    assert [m for m, _ in registry.iter_hooks("post_turn")] == []
    assert "duplicate" in capsys.readouterr().err


def test_user_modules_dir_is_outside_the_agent_sandbox(tmp_path: Path) -> None:
    from veles.core.context import reset_active_project, set_active_project

    project = init_project(tmp_path / "p", name="p")
    token = set_active_project(project)
    try:
        with pytest.raises(SandboxViolation):
            resolve_safe(user_modules_dir() / "evil" / "m.py")
    finally:
        reset_active_project(token)


def test_user_module_memory_provider_is_built_under_its_registry(tmp_path: Path) -> None:
    """A user-level module that registers a memory provider is loaded by
    `_load_project_modules`, and `build_extra_providers` builds it under that
    project's registry — the module wiring reaches all the way to the recall path."""
    from veles.core.memory.providers import build_extra_providers
    from veles.core.modules import reset_module_registry, set_module_registry

    d = user_modules_dir() / "mem-provider"
    d.mkdir(parents=True)
    (d / "module.toml").write_text(
        '[module]\nname = "mem-provider"\ndescription = "d"\nentrypoint = "m.py:register"\n',
        encoding="utf-8",
    )
    (d / "m.py").write_text(
        "def register(api):\n    api.add_memory_provider('fake', lambda cfg: {'cfg': cfg})\n",
        encoding="utf-8",
    )
    approve_module(d, name="mem-provider", project_root=None)

    project = init_project(tmp_path / "p", name="p")
    registry = _load_project_modules(project)
    assert registry.modules == ["mem-provider"]

    config = tmp_path / "config.toml"
    config.write_text('[memory.external.fake]\napi_key = "k"\n', encoding="utf-8")

    token = set_module_registry(registry)
    try:
        [provider] = build_extra_providers(config)
    finally:
        reset_module_registry(token)
    assert provider == {"cfg": {"api_key": "k"}}

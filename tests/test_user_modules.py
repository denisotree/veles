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


def test_unapproved_project_module_does_not_shadow_approved_user_module(
    tmp_path: Path, capsys
) -> None:
    """A planted, unapproved project module named like an approved user module must
    not disable it: the gate runs before override, and the warning names the planted dir."""
    project = init_project(tmp_path / "p", name="p")
    approve_module(_module(user_modules_dir(), "same"), name="same", project_root=None)
    planted = _module(project.modules_dir, "same", hook="post_turn")
    registry = _load_project_modules(project)
    assert registry.modules == ["same"]
    assert [m for m, _ in registry.iter_hooks("pre_turn")] == ["same"]
    assert [m for m, _ in registry.iter_hooks("post_turn")] == []
    err = capsys.readouterr().err
    assert str(planted) in err
    assert "overrides" not in err


def test_symlinked_module_dir_borrowing_another_projects_approval_is_refused(
    tmp_path: Path, capsys
) -> None:
    """Project A symlinks `.veles/modules/guard` to project B's approved `guard`: the
    record (keyed by resolved path) must not admit it in A, so the approved user-level
    `guard` still loads there."""
    a = init_project(tmp_path / "a", name="a")
    b = init_project(tmp_path / "b", name="b")
    approve_module(_module(user_modules_dir(), "guard"), name="guard", project_root=None)
    b_guard = _module(b.modules_dir, "guard", hook="post_turn")
    approve_module(b_guard, name="guard", project_root=b.root)
    a.modules_dir.mkdir(parents=True, exist_ok=True)
    (a.modules_dir / "guard").symlink_to(b_guard, target_is_directory=True)
    registry = _load_project_modules(a)
    assert registry.modules == ["guard"]
    assert [m for m, _ in registry.iter_hooks("pre_turn")] == ["guard"]
    assert [m for m, _ in registry.iter_hooks("post_turn")] == []
    assert "symlink" in capsys.readouterr().err
    assert _load_project_modules(b).modules == ["guard"]  # B itself is unaffected


def test_approval_for_another_project_does_not_admit_via_symlinked_modules_dir(
    tmp_path: Path, capsys
) -> None:
    """A's whole `.veles/modules` is a link to B's: same resolved dirs, but B's record is
    scoped to B — loaded as project A it is refused."""
    a = init_project(tmp_path / "a", name="a")
    b = init_project(tmp_path / "b", name="b")
    approve_module(_module(b.modules_dir, "guard"), name="guard", project_root=b.root)
    if a.modules_dir.exists():
        a.modules_dir.rmdir()
    a.modules_dir.symlink_to(b.modules_dir, target_is_directory=True)
    assert _load_project_modules(a).modules == []
    assert "another" in capsys.readouterr().err
    assert _load_project_modules(b).modules == ["guard"]


def test_user_scope_record_does_not_admit_a_project_load(tmp_path: Path) -> None:
    from veles.core.registry.gate import admit_module

    project = init_project(tmp_path / "p", name="p")
    d = _module(project.modules_dir, "m1")
    approve_module(d, name="m1", project_root=None)  # recorded as user scope
    assert admit_module(d, project_root=project.root) is not None
    assert admit_module(d, project_root=None) is None
    approve_module(d, name="m1", project_root=project.root)
    assert admit_module(d, project_root=None) is not None
    assert admit_module(d, project_root=project.root) is None


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


def test_module_that_fails_to_register_leaves_nothing_behind(tmp_path: Path, capsys) -> None:
    """A module whose `register()` raises must not leave partial state behind: not the
    hook, not the memory provider it registered before raising."""
    project = init_project(tmp_path / "p", name="p")
    d = user_modules_dir() / "boom"
    d.mkdir(parents=True)
    (d / "module.toml").write_text(
        '[module]\nname = "boom"\ndescription = "d"\nentrypoint = "m.py:register"\n',
        encoding="utf-8",
    )
    (d / "m.py").write_text(
        "def register(api):\n"
        "    api.add_hook('pre_turn', lambda **kw: None)\n"
        "    api.add_memory_provider('fake', lambda cfg: object())\n"
        "    raise RuntimeError('boom')\n",
        encoding="utf-8",
    )
    approve_module(d, name="boom", project_root=None)

    registry = _load_project_modules(project)

    assert registry.modules == []
    assert [m for m, _ in registry.iter_hooks("pre_turn")] == []
    assert list(registry.iter_memory_providers()) == []
    assert "boom" in capsys.readouterr().err


def test_module_with_colliding_provider_name_is_skipped_entirely(tmp_path: Path, capsys) -> None:
    """A module whose `register()` returns cleanly but whose memory-provider name
    collides with one an earlier module already registered is skipped as a whole — its
    hook must not land either, only the earlier module's provider stays registered."""
    project = init_project(tmp_path / "p", name="p")

    first = user_modules_dir() / "first"
    first.mkdir(parents=True)
    (first / "module.toml").write_text(
        '[module]\nname = "first"\ndescription = "d"\nentrypoint = "m.py:register"\n',
        encoding="utf-8",
    )
    (first / "m.py").write_text(
        "def register(api):\n    api.add_memory_provider('fake', lambda cfg: object())\n",
        encoding="utf-8",
    )
    approve_module(first, name="first", project_root=None)

    second = user_modules_dir() / "second"
    second.mkdir(parents=True)
    (second / "module.toml").write_text(
        '[module]\nname = "second"\ndescription = "d"\nentrypoint = "m.py:register"\n',
        encoding="utf-8",
    )
    (second / "m.py").write_text(
        "def register(api):\n"
        "    api.add_hook('post_turn', lambda **kw: None)\n"
        "    api.add_memory_provider('fake', lambda cfg: object())\n",
        encoding="utf-8",
    )
    approve_module(second, name="second", project_root=None)

    registry = _load_project_modules(project)

    assert registry.modules == ["first"]
    assert [m for m, _ in registry.iter_hooks("post_turn")] == []
    assert [name for name, _module, _factory in registry.iter_memory_providers()] == ["fake"]
    assert "second" in capsys.readouterr().err

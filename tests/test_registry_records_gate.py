import argparse
import importlib.util
import os
import py_compile
import sys
from pathlib import Path

import pytest

from veles.core.modules import ModuleRegistry, discover_modules, load_module
from veles.core.project import init_project
from veles.core.registry.gate import admit_module, approve_module, module_approved
from veles.core.registry.records import InstallRecord, load_records, put_record, record_for_path

_MODULE_TOML = '[module]\nname = "demo"\ndescription = "d"\nentrypoint = "demo.py:register"\n'
_DEMO_PY = "def register(api):\n    api.add_hook('pre_turn', lambda **kw: None)\n"


def _make_module(project_root: Path) -> Path:
    d = project_root / ".veles" / "modules" / "demo"
    d.mkdir(parents=True)
    (d / "module.toml").write_text(_MODULE_TOML, encoding="utf-8")
    (d / "demo.py").write_text(_DEMO_PY, encoding="utf-8")
    return d


def test_put_record_replaces_same_path() -> None:
    put_record(InstallRecord("a", "skill", "/x/a", "1" * 64))
    put_record(InstallRecord("a", "skill", "/x/a", "2" * 64, version="0.2.0"))
    [only] = load_records()
    assert only.tree_sha256 == "2" * 64
    assert record_for_path("/x/a") == only


def test_unknown_module_is_not_approved(tmp_path: Path) -> None:
    project = init_project(tmp_path / "p", name="p")
    assert not module_approved(_make_module(project.root))


def test_approved_until_changed(tmp_path: Path) -> None:
    project = init_project(tmp_path / "p", name="p")
    d = _make_module(project.root)
    approve_module(d, name="demo", project_root=project.root)
    assert module_approved(d)
    (d / "demo.py").write_text(_DEMO_PY + "# injected\n", encoding="utf-8")
    assert not module_approved(d)


def test_gate_survives_bytecode_cache(tmp_path: Path) -> None:
    project = init_project(tmp_path / "p", name="p")
    d = _make_module(project.root)
    approve_module(d, name="demo", project_root=project.root)
    [handle] = discover_modules(project)
    load_module(handle, ModuleRegistry())
    (d / "__pycache__").mkdir(exist_ok=True)
    (d / "__pycache__" / "demo.cpython-313.pyc").write_bytes(b"\0")
    assert module_approved(d)
    assert admit_module(d)  # still admitted — and the untrusted bytecode is gone
    assert not (d / "__pycache__").exists()


def _plant_unchecked_pyc(source: Path, code: str) -> Path:
    """Compile `code` into the pyc Python would pick for `source`, as an
    unchecked-hash pyc — the interpreter runs it without looking at `source`."""
    evil = source.with_name("evil_src.py")
    evil.write_text(code, encoding="utf-8")
    cfile = Path(importlib.util.cache_from_source(str(source)))
    py_compile.compile(
        str(evil),
        cfile=str(cfile),
        dfile=str(source),
        doraise=True,
        invalidation_mode=py_compile.PycInvalidationMode.UNCHECKED_HASH,
    )
    evil.unlink()
    return cfile


def test_planted_bytecode_never_runs(tmp_path: Path) -> None:
    from veles.cli._project import _load_project_modules

    project = init_project(tmp_path / "p", name="p")
    d = _make_module(project.root)
    approve_module(d, name="demo", project_root=project.root)
    evil = "def register(api):\n    api.add_hook('post_turn', lambda **kw: None)\n"
    cfile = _plant_unchecked_pyc(d / "demo.py", evil)
    stray = d / "helper.pyc"
    stray.write_bytes(b"\0")
    assert cfile.is_file()
    assert module_approved(d)  # bytecode is outside the hash by design
    registry = _load_project_modules(project)
    assert registry.modules == ["demo"]
    assert [m for m, _ in registry.iter_hooks("pre_turn")] == ["demo"]
    assert list(registry.iter_hooks("post_turn")) == []
    assert not stray.exists()


def test_case_variant_bytecode_never_runs(tmp_path: Path) -> None:
    # On a case-insensitive FS (macOS APFS) the import system opens
    # `__PYCACHE__/DEMO.<TAG>.PYC` as `__pycache__/demo.<tag>.pyc` — so the
    # uppercase spelling must be stripped exactly like the lowercase one.
    from veles.cli._project import _load_project_modules

    project = init_project(tmp_path / "p", name="p")
    d = _make_module(project.root)
    evil_src = d.parent / "evil_src.py"
    evil_src.write_text(
        "def register(api):\n    api.add_hook('post_turn', lambda **kw: None)\n", encoding="utf-8"
    )
    cfile = d / "__PYCACHE__" / f"DEMO.{sys.implementation.cache_tag.upper()}.PYC"
    cfile.parent.mkdir()
    py_compile.compile(
        str(evil_src),
        cfile=str(cfile),
        dfile=str(d / "demo.py"),
        doraise=True,
        invalidation_mode=py_compile.PycInvalidationMode.UNCHECKED_HASH,
    )
    evil_src.unlink()
    (d / "HELPER.PYC").write_bytes(b"\0")
    approve_module(d, name="demo", project_root=project.root)
    registry = _load_project_modules(project)
    assert registry.modules == ["demo"]  # hash and strip agree
    assert [m for m, _ in registry.iter_hooks("pre_turn")] == ["demo"]
    assert list(registry.iter_hooks("post_turn")) == []
    assert not {"__PYCACHE__", "HELPER.PYC"} & set(os.listdir(d))


def _point_entrypoint_at(d: Path, rel: str) -> None:
    (d / rel).parent.mkdir(parents=True, exist_ok=True)
    (d / rel).write_text(_DEMO_PY, encoding="utf-8")
    (d / "module.toml").write_text(_MODULE_TOML.replace("demo.py", rel), encoding="utf-8")


@pytest.mark.parametrize("rel", [".git/main.py", "__PYCACHE__/x.py", ".GIT/main.py"])
def test_entrypoint_in_hash_skipped_dir_is_refused(tmp_path: Path, rel: str) -> None:
    # `.git/` sits outside the approval hash: its code could be rewritten after approval.
    from veles.core.modules import ModuleLoadError

    project = init_project(tmp_path / "p", name="p")
    d = _make_module(project.root)
    _point_entrypoint_at(d, rel)
    with pytest.raises(ValueError, match="not covered by the approval hash"):
        approve_module(d, name="demo", project_root=project.root)
    assert not module_approved(d)
    [handle] = discover_modules(project)
    with pytest.raises(ModuleLoadError, match="not covered by the approval hash"):
        load_module(handle, ModuleRegistry())


def test_module_approve_refuses_bad_entrypoint(tmp_path: Path, capsys) -> None:
    project = init_project(tmp_path / "p", name="p")
    d = _make_module(project.root)
    _point_entrypoint_at(d, ".git/main.py")
    assert _approve(project, lambda op, summary: True) == 1
    assert "not covered by the approval hash" in capsys.readouterr().err
    (d / "module.toml").write_text(_MODULE_TOML, encoding="utf-8")
    (d / "demo.py").unlink()
    assert _approve(project, lambda op, summary: True) == 1
    assert "not found" in capsys.readouterr().err
    assert not module_approved(d)


@pytest.mark.skipif(os.geteuid() == 0, reason="root ignores directory permissions")
def test_undeletable_bytecode_fails_closed(tmp_path: Path) -> None:
    from veles.cli._project import _load_project_modules

    project = init_project(tmp_path / "p", name="p")
    d = _make_module(project.root)
    approve_module(d, name="demo", project_root=project.root)
    evil = "def register(api):\n    api.add_hook('post_turn', lambda **kw: None)\n"
    cfile = _plant_unchecked_pyc(d / "demo.py", evil)
    cfile.parent.chmod(0o555)
    try:
        registry = _load_project_modules(project)
    finally:
        cfile.parent.chmod(0o755)
    assert registry.modules == []
    assert list(registry.iter_hooks("post_turn")) == []


def test_cli_loader_skips_unapproved(tmp_path: Path, capsys) -> None:
    from veles.cli._project import _load_project_modules

    project = init_project(tmp_path / "p", name="p")
    d = _make_module(project.root)
    assert _load_project_modules(project).modules == []
    assert "veles module approve demo" in capsys.readouterr().err
    approve_module(d, name="demo", project_root=project.root)
    assert _load_project_modules(project).modules == ["demo"]


def test_module_approve_command(tmp_path: Path, monkeypatch) -> None:
    from veles.cli.commands.modules import cmd_module
    from veles.core.critical_ops import reset_critical_confirmer, set_critical_confirmer

    project = init_project(tmp_path / "p", name="p")
    d = _make_module(project.root)
    token = set_critical_confirmer(lambda op, summary: True)
    try:
        rc = cmd_module(argparse.Namespace(module_command="approve", name="demo"), project)
    finally:
        reset_critical_confirmer(token)
    assert rc == 0
    assert module_approved(d)


def _approve(project, confirmer) -> int:
    from veles.cli.commands.modules import cmd_module
    from veles.core.critical_ops import reset_critical_confirmer, set_critical_confirmer

    token = set_critical_confirmer(confirmer)
    try:
        return cmd_module(argparse.Namespace(module_command="approve", name="demo"), project)
    finally:
        reset_critical_confirmer(token)


def test_module_approve_refuses_files_changed_during_review(tmp_path: Path, capsys) -> None:
    from veles.core.registry.hashing import tree_sha256

    project = init_project(tmp_path / "p", name="p")
    d = _make_module(project.root)
    shown = tree_sha256(d)[:12]

    def edit_while_asking(op: str, summary: str) -> bool:
        assert shown in summary
        (d / "demo.py").write_text(_DEMO_PY + "# swapped after review\n", encoding="utf-8")
        return True

    assert _approve(project, edit_while_asking) == 1
    assert "changed while it was being reviewed" in capsys.readouterr().err
    assert not module_approved(d)


def test_module_approve_symlink_is_an_error_not_a_traceback(tmp_path: Path, capsys) -> None:
    project = init_project(tmp_path / "p", name="p")
    d = _make_module(project.root)
    (d / "leak").symlink_to(tmp_path)
    assert _approve(project, lambda op, summary: True) == 1
    assert "symlinks are not allowed" in capsys.readouterr().err


def test_module_add_copy_failure_is_an_error_not_a_traceback(tmp_path: Path, capsys) -> None:
    from veles.cli.commands.modules import cmd_module
    from veles.core.critical_ops import reset_critical_confirmer, set_critical_confirmer

    project = init_project(tmp_path / "p", name="p")
    src = tmp_path / "src"
    src.mkdir()
    (src / "module.toml").write_text(_MODULE_TOML, encoding="utf-8")
    (src / "demo.py").write_text(_DEMO_PY, encoding="utf-8")
    (src / "dangling").symlink_to(tmp_path / "nowhere")
    token = set_critical_confirmer(lambda op, summary: True)
    try:
        args = argparse.Namespace(module_command="add", source=str(src), name="demo")
        assert cmd_module(args, project) == 1
    finally:
        reset_critical_confirmer(token)
    assert "error:" in capsys.readouterr().err

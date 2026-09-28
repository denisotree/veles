import argparse
import importlib.util
import py_compile
from pathlib import Path

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

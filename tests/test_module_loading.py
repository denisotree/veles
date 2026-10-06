"""Module loading outside the CLI: the delegated-CLI MCP child loads the same
approved user modules (else a registry-installed wiki would vanish there), and the
lazy builtin registry loads once even when two threads ask first."""

from __future__ import annotations

import contextvars
import threading
import time
from pathlib import Path

import pytest

from veles.core import contributions as contrib
from veles.core.modules import current_module_registry
from veles.core.project import init_project
from veles.core.registry.gate import approve_module
from veles.core.user_paths import user_modules_dir


def _user_module(name: str) -> Path:
    d = user_modules_dir() / name
    d.mkdir(parents=True)
    (d / "module.toml").write_text(
        f'[module]\nname = "{name}"\ndescription = "d"\nentrypoint = "m.py:register"\n',
        encoding="utf-8",
    )
    (d / "m.py").write_text(
        "def register(api):\n    api.add_hook('pre_turn', lambda **kw: None)\n", encoding="utf-8"
    )
    return d


def test_mcp_child_loads_approved_user_modules(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from veles.adapters.cli import mcp_server

    project = init_project(tmp_path / "p", name="p")
    approve_module(_user_module("u1"), name="u1", project_root=None)
    _user_module("unapproved")
    seen: dict = {}

    class _StubServer:
        def __init__(self, *_a, **_kw) -> None:
            reg = current_module_registry()
            seen["modules"] = reg.modules if reg is not None else None

        def serve(self, **_kw) -> int:
            return 0

    monkeypatch.setattr(mcp_server, "MCPServer", _StubServer)
    contextvars.copy_context().run(mcp_server.main, ["--project-root", str(project.root)])
    assert seen["modules"] == ["u1"]


def test_doctor_reports_a_module_that_never_loads(tmp_path: Path) -> None:
    """A never-approved module has no install record, so the extensions check missed it
    and doctor said "0 error" while the module was skipped (integrator report V-2)."""
    from veles.core.doctor import _check_modules

    project = init_project(tmp_path / "p", name="p")
    assert _check_modules(project).status == "ok"
    approve_module(_user_module("u1"), name="u1", project_root=None)
    _user_module("never")
    own = project.modules_dir / "guard"
    own.mkdir(parents=True)
    (own / "module.toml").write_text(
        '[module]\nname = "guard"\ndescription = "d"\nentrypoint = "m.py:register"\n',
        encoding="utf-8",
    )
    (own / "m.py").write_text("def register(api):\n    pass\n", encoding="utf-8")
    res = _check_modules(project)
    assert res.status == "error"
    assert "never" in res.message and "guard" in res.message and "u1" not in res.message
    assert "veles module approve --user never" in (res.fix_hint or "")
    assert "veles module approve guard" in (res.fix_hint or "")


def test_builtin_modules_load_once_across_threads(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []
    barrier = threading.Barrier(4)

    def counting(name: str):
        calls.append(name)
        time.sleep(0.05)  # widen the race window: a second thread arrives mid-load

        class _M:
            @staticmethod
            def register(api) -> None:
                pass

        return _M

    contrib.reset_builtin_contributions()
    monkeypatch.setattr(contrib, "BUILTIN_MODULES", ("fake.one",))
    monkeypatch.setattr(contrib.importlib, "import_module", counting)

    def first_call() -> None:
        barrier.wait()
        contrib.contributions("engine")

    threads = [threading.Thread(target=first_call) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    contrib.reset_builtin_contributions()
    assert calls == ["fake.one"]


def test_reload_into_an_existing_registry_runs_only_new_entrypoints(tmp_path: Path) -> None:
    """After an install mid-session the CLI loads the new modules into the live
    registry — an already-loaded module's entrypoint must not run a second time."""
    from veles.core.module_loading import load_project_modules

    project = init_project(tmp_path / "p", name="p")
    runs = tmp_path / "runs"
    one = _user_module("one")
    (one / "m.py").write_text(
        f"from pathlib import Path\n"
        f"with Path({str(runs)!r}).open('a') as f:\n"
        f"    f.write('one\\n')\n"
        f"def register(api):\n"
        f"    api.add_hook('pre_turn', lambda **kw: None)\n",
        encoding="utf-8",
    )
    approve_module(one, name="one", project_root=None)
    reg = load_project_modules(project)
    approve_module(_user_module("two"), name="two", project_root=None)
    assert load_project_modules(project, into=reg) is reg
    assert set(reg.modules) == {"one", "two"}
    assert runs.read_text(encoding="utf-8") == "one\n"


def test_cli_session_sees_a_module_installed_at_its_start(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """`_run_in_project`: an install offered at session start lands in the registry
    the command runs with — the module installed before it is not loaded again."""
    import argparse

    from veles.cli import _run_in_project
    from veles.core.registry import ensure

    project = init_project(tmp_path / "p", name="p")
    monkeypatch.chdir(project.root)
    runs = tmp_path / "runs"
    first = _user_module("first")
    (first / "m.py").write_text(
        f"from pathlib import Path\n"
        f"with Path({str(runs)!r}).open('a') as f:\n"
        f"    f.write('first\\n')\n"
        f"def register(api):\n"
        f"    api.add_hook('pre_turn', lambda **kw: None)\n",
        encoding="utf-8",
    )
    approve_module(first, name="first", project_root=None)

    def install_second(_project, *, interactive: bool) -> bool:
        approve_module(_user_module("second"), name="second", project_root=None)
        return True

    monkeypatch.setattr(ensure, "ensure_project_extensions", install_second)
    seen: dict = {}

    def command(_args, _project) -> int:
        reg = current_module_registry()
        seen["modules"] = list(reg.modules) if reg is not None else None
        return 0

    args = argparse.Namespace(command="run", project_root=None, no_wizard=True)
    assert _run_in_project(args, command) == 0
    assert seen["modules"] == ["first", "second"]
    assert runs.read_text(encoding="utf-8") == "first\n"

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

"""Release A: one typed contribution point for modules (`api.contribute`)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from veles.core import contributions as contrib
from veles.core.module_manifest import parse_manifest
from veles.core.modules import (
    ModuleAPI,
    ModuleHandle,
    ModuleLoadError,
    ModuleRegistry,
    load_module,
    reset_module_registry,
    set_module_registry,
)


@pytest.fixture()
def point():
    """A throwaway keyed point accepting `str` objects."""
    p = contrib.Point(name="test-point", kind=str)
    contrib.register_point(p)
    yield p
    contrib.CONTRIBUTION_POINTS.pop(p.name, None)


@pytest.fixture()
def no_builtins(monkeypatch):
    monkeypatch.setattr(contrib, "BUILTIN_MODULES", ())
    contrib.reset_builtin_contributions()
    yield
    contrib.reset_builtin_contributions()


def _write_module(root: Path, name: str, body: str) -> ModuleHandle:
    d = root / name
    d.mkdir(parents=True)
    (d / "module.toml").write_text(
        f'[module]\nname = "{name}"\ndescription = "d"\nentrypoint = "m.py:register"\n',
        encoding="utf-8",
    )
    (d / "m.py").write_text(body, encoding="utf-8")
    manifest = parse_manifest((d / "module.toml").read_text(encoding="utf-8"))
    return ModuleHandle(name=name, manifest=manifest, dir=d)


def test_contribute_is_visible_after_load(tmp_path, point, no_builtins) -> None:
    h = _write_module(
        tmp_path, "a", "def register(api):\n    api.contribute('test-point', 'x', 'hello')\n"
    )
    reg = ModuleRegistry()
    load_module(h, reg)
    token = set_module_registry(reg)
    try:
        got = contrib.contributions("test-point")
    finally:
        reset_module_registry(token)
    assert [(c.name, c.obj, c.module) for c in got] == [("x", "hello", "a")]


@pytest.mark.parametrize(
    "body, why",
    [
        ("api.contribute('no-such-point', 'x', 'v')", "unknown point"),
        ("api.contribute('test-point', 'x', 42)", "wrong kind"),
        (
            "api.contribute('test-point', 'x', 'a')\n    api.contribute('test-point', 'x', 'b')",
            "dup",
        ),
    ],
)
def test_bad_contribution_refuses_the_module(tmp_path, point, no_builtins, body, why) -> None:
    h = _write_module(tmp_path, "bad", f"def register(api):\n    {body}\n")
    reg = ModuleRegistry()
    with pytest.raises(ModuleLoadError):
        load_module(h, reg)
    assert reg.contributions("test-point") == [] and reg.modules == [], why


def test_duplicate_name_across_modules_refuses_the_second(tmp_path, point, no_builtins) -> None:
    reg = ModuleRegistry()
    body = "def register(api):\n    api.contribute('test-point', 'x', 'v')\n"
    load_module(_write_module(tmp_path, "one", body), reg)
    with pytest.raises(ModuleLoadError):
        load_module(_write_module(tmp_path, "two", body), reg)
    assert [c.module for c in reg.contributions("test-point")] == ["one"]


def test_builtin_modules_load_lazily_once(tmp_path, point, monkeypatch) -> None:
    pkg = tmp_path / "pkgs" / "fake_builtin"
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text(
        "LOADS = []\n"
        "def register(api):\n"
        "    LOADS.append(1)\n"
        "    api.contribute('test-point', 'b', 'from-builtin')\n",
        encoding="utf-8",
    )
    monkeypatch.syspath_prepend(str(tmp_path / "pkgs"))
    monkeypatch.setattr(contrib, "BUILTIN_MODULES", ("fake_builtin",))
    contrib.reset_builtin_contributions()
    try:
        # No set_module_registry: a bare process (MCP child, a test) still sees builtins.
        assert [c.obj for c in contrib.contributions("test-point")] == ["from-builtin"]
        assert [c.obj for c in contrib.contributions("test-point")] == ["from-builtin"]
        assert sys.modules["fake_builtin"].LOADS == [1]
    finally:
        contrib.reset_builtin_contributions()
        sys.modules.pop("fake_builtin", None)


def test_broken_builtin_warns_and_the_rest_load(tmp_path, point, monkeypatch, capsys) -> None:
    pkgs = tmp_path / "pkgs"
    (pkgs / "good_b").mkdir(parents=True)
    (pkgs / "good_b" / "__init__.py").write_text(
        "def register(api):\n    api.contribute('test-point', 'g', 'ok')\n", encoding="utf-8"
    )
    (pkgs / "bad_b").mkdir()
    (pkgs / "bad_b" / "__init__.py").write_text("raise ImportError('boom')\n", encoding="utf-8")
    monkeypatch.syspath_prepend(str(pkgs))
    monkeypatch.setattr(contrib, "BUILTIN_MODULES", ("bad_b", "good_b"))
    contrib.reset_builtin_contributions()
    try:
        assert [c.obj for c in contrib.contributions("test-point")] == ["ok"]
        assert "bad_b" in capsys.readouterr().err
    finally:
        contrib.reset_builtin_contributions()
        for m in ("good_b", "bad_b"):
            sys.modules.pop(m, None)


def test_call_each_survives_a_raising_contribution(point, no_builtins, capsys) -> None:
    reg = ModuleRegistry()
    scratch = ModuleRegistry()
    ModuleAPI(scratch, "m").contribute("test-point", "ok", "fine")
    ModuleAPI(scratch, "m").contribute("test-point", "boom", "explode")
    reg.merge_from(scratch, "m")

    def run(c: contrib.Contribution) -> str:
        if c.obj == "explode":
            raise RuntimeError("nope")
        return str(c.obj)

    token = set_module_registry(reg)
    try:
        assert contrib.call_each("test-point", run) == ["fine"]
        assert contrib.call_each("test-point", run) == ["fine"]
    finally:
        reset_module_registry(token)
    assert capsys.readouterr().err.count("warning:") == 1


def test_memory_provider_is_a_contribution(tmp_path, no_builtins) -> None:
    h = _write_module(
        tmp_path,
        "mp",
        "def register(api):\n    api.add_memory_provider('mp', lambda cfg: None)\n",
    )
    reg = ModuleRegistry()
    load_module(h, reg)
    assert [c.name for c in reg.contributions("memory")] == ["mp"]
    assert [name for name, _m, _f in reg.iter_memory_providers()] == ["mp"]

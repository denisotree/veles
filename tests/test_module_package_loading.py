"""A module may span several files: its entrypoint is loaded as a package rooted
at the module directory, so `from .helpers import x` works — and a module that
fails to load leaves none of its submodules behind."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from veles.core.module_manifest import parse_manifest
from veles.core.modules import ModuleHandle, ModuleLoadError, ModuleRegistry, load_module


def _module(root: Path, name: str, files: dict[str, str], entrypoint: str) -> ModuleHandle:
    d = root / name
    for rel, body in files.items():
        (d / rel).parent.mkdir(parents=True, exist_ok=True)
        (d / rel).write_text(body, encoding="utf-8")
    text = f'[module]\nname = "{name}"\ndescription = "d"\nentrypoint = "{entrypoint}"\n'
    (d / "module.toml").write_text(text, encoding="utf-8")
    return ModuleHandle(name, parse_manifest(text), d)


def test_entrypoint_imports_its_siblings_relatively(tmp_path: Path) -> None:
    handle = _module(
        tmp_path,
        "multi",
        {
            "__init__.py": (
                "from .helpers import HOOK\n"
                "def register(api):\n"
                "    from .sub.deep import VALUE\n"
                "    assert VALUE == 42\n"
                "    api.add_hook(HOOK, lambda **kw: None)\n"
            ),
            "helpers.py": "HOOK = 'pre_turn'\n",
            "sub/__init__.py": "",
            "sub/deep.py": "from ..helpers import HOOK\nVALUE = 42\n",
        },
        "__init__.py:register",
    )
    registry = ModuleRegistry()
    load_module(handle, registry)
    assert registry.modules == ["multi"]
    assert "_veles_module_multi.helpers" in sys.modules


def test_single_file_module_with_a_sibling(tmp_path: Path) -> None:
    handle = _module(
        tmp_path,
        "flat",
        {
            "main.py": "from .util import f\ndef register(api):\n    f(api)\n",
            "util.py": "def f(api):\n    api.add_hook('pre_turn', lambda **kw: None)\n",
        },
        "main.py:register",
    )
    load_module(handle, ModuleRegistry())


def test_failed_load_leaves_no_submodules(tmp_path: Path) -> None:
    handle = _module(
        tmp_path,
        "broken",
        {
            "__init__.py": (
                "from .helpers import X\ndef register(api):\n    raise RuntimeError('no')\n"
            ),
            "helpers.py": "X = 1\n",
        },
        "__init__.py:register",
    )
    with pytest.raises(ModuleLoadError):
        load_module(handle, ModuleRegistry())
    assert not [m for m in sys.modules if m.startswith("_veles_module_broken")]

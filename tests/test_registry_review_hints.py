"""Reviewer hints and staleness: native binaries are named for the reviewer, an old
registry clone says so, and the CI template passes the base ref through env."""

from __future__ import annotations

import os
import time
from pathlib import Path

from tests.registry_helpers import make_git_registry, write_extension, write_registry
from veles.core.registry.catalog import available
from veles.core.registry.config import add_source, remove_source
from veles.core.registry.validate import validate_registry


def test_native_binaries_are_reported_to_the_reviewer(tmp_path: Path) -> None:
    root = write_registry(tmp_path / "r")
    write_extension(
        root,
        "official",
        "demo",
        kind="module",
        files={
            "module.toml": (
                '[module]\nname = "demo"\ndescription = "d"\nentrypoint = "d.py:register"\n'
            ),
            "d.py": "def register(api):\n    pass\n",
            "lib/fast.so": "\x7fELF",
            "fast.pyd": "MZ",
            "x.dylib": "",
        },
    )
    review = "\n".join(validate_registry(root).review)
    for name in ("lib/fast.so", "fast.pyd", "x.dylib"):
        assert f"{name}: native binary" in review


def test_old_registry_clone_warns(tmp_path: Path) -> None:
    root = tmp_path / "remote"
    make_git_registry(root, skills=("alpha",))
    remove_source("public")
    source = add_source(str(root))
    found, warnings = available()  # clones it
    assert found and not any("days ago" in w for w in warnings)
    from veles.core.registry.config import cache_dir

    git_dir = cache_dir(source.name) / ".git"
    old = time.time() - 10 * 86400
    for marker in (git_dir / "FETCH_HEAD", git_dir):
        if marker.exists():
            os.utime(marker, (old, old))
    _, warnings = available(sync_missing=False)
    assert any("10 days ago" in w and "veles registry update" in w for w in warnings)


def test_ci_template_reads_the_base_ref_from_env() -> None:
    import importlib.resources

    workflow = (
        importlib.resources.files("veles")
        .joinpath("registry_template/github/workflows/validate.yml")
        .read_text(encoding="utf-8")
    )
    assert "BASE_REF: ${{ github.base_ref }}" in workflow
    assert '--base "origin/$BASE_REF"' in workflow
    assert "--base origin/${{" not in workflow  # no expression inside the shell line

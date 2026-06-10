"""Tests for the builtin stat_file tool (M124-perm-unify)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from veles.core.context import reset_active_project, set_active_project
from veles.core.path_guard import SandboxViolation
from veles.core.project import init_project


@pytest.fixture
def project(tmp_path: Path):
    root = tmp_path / "proj"
    root.mkdir()
    p = init_project(root, name="t")
    token = set_active_project(p)
    yield p
    reset_active_project(token)


def test_stat_regular_file(project) -> None:
    from veles.core.tools.builtin.stat_file import stat_file

    target = project.root / "hello.txt"
    target.write_text("hi there")
    payload = json.loads(stat_file(str(target)))
    assert payload["type"] == "file"
    assert payload["size_bytes"] == 8
    assert payload["mtime_iso"].endswith("+00:00")
    assert len(payload["sha256_short"]) == 16


def test_stat_directory(project) -> None:
    from veles.core.tools.builtin.stat_file import stat_file

    payload = json.loads(stat_file(str(project.root)))
    assert payload["type"] == "directory"
    assert "sha256_short" not in payload


def test_stat_missing_file(project) -> None:
    from veles.core.tools.builtin.stat_file import stat_file

    payload = json.loads(stat_file(str(project.root / "absent")))
    assert payload["type"] == "missing"


def test_stat_symlink_resolves_to_target_kind(project) -> None:
    """Sandbox `resolve_safe` follows symlinks before classification (this
    is the existing M37 sandbox contract — a link inside the sandbox
    pointing outside would have been rejected). Symlinks to in-sandbox
    files therefore stat as their target kind, not as `symlink`."""
    from veles.core.tools.builtin.stat_file import stat_file

    target = project.root / "target.txt"
    target.write_text("x")
    link = project.root / "alias"
    link.symlink_to(target)
    payload = json.loads(stat_file(str(link)))
    assert payload["type"] == "file"


def test_sandbox_violation(project) -> None:
    from veles.core.tools.builtin.stat_file import stat_file

    with pytest.raises(SandboxViolation):
        stat_file("/etc/passwd")


def test_sha_short_is_stable(project) -> None:
    """Same content → same prefix; small change → different prefix."""
    from veles.core.tools.builtin.stat_file import stat_file

    f = project.root / "a.bin"
    f.write_bytes(b"hello")
    a = json.loads(stat_file(str(f)))["sha256_short"]
    f.write_bytes(b"hello")
    b = json.loads(stat_file(str(f)))["sha256_short"]
    f.write_bytes(b"hella")
    c = json.loads(stat_file(str(f)))["sha256_short"]
    assert a == b
    assert a != c

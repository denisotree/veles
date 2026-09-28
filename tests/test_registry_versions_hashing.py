from pathlib import Path

import pytest

from veles.core.registry.hashing import tree_sha256
from veles.core.registry.versions import is_newer, parse_version, satisfies


def test_parse_version_strips_local_and_prerelease() -> None:
    assert parse_version("1.2.3") == (1, 2, 3)
    assert parse_version("0.0.0+unknown") == (0, 0, 0)
    assert parse_version("1.0.0-rc1") == (1, 0, 0)
    with pytest.raises(ValueError):
        parse_version("one")


@pytest.mark.parametrize(
    ("version", "spec", "ok"),
    [
        ("1.0.0", ">=1.0,<2", True),
        ("2.0.0", ">=1.0,<2", False),
        ("1.4.2", "==1.4.2", True),
        ("1.4.2", "!=1.4.2", False),
        ("1.10.0", ">1.9", True),
        ("1.0", "<=1.0.0", True),
    ],
)
def test_satisfies(version: str, spec: str, ok: bool) -> None:
    assert satisfies(version, spec) is ok


def test_satisfies_rejects_garbage() -> None:
    with pytest.raises(ValueError):
        satisfies("1.0.0", "~=1.0")


def test_is_newer() -> None:
    assert is_newer("1.10.0", "1.9.9")
    assert not is_newer("1.0.0", "1.0.0")


def _tree(root: Path) -> None:
    (root / "pkg").mkdir(parents=True)
    (root / "pkg" / "a.py").write_text("x = 1\n", encoding="utf-8")
    (root / "module.toml").write_text("[module]\n", encoding="utf-8")


def test_tree_sha256_is_stable_and_content_sensitive(tmp_path: Path) -> None:
    _tree(tmp_path / "one")
    _tree(tmp_path / "two")
    assert tree_sha256(tmp_path / "one") == tree_sha256(tmp_path / "two")
    (tmp_path / "two" / "pkg" / "a.py").write_text("x = 2\n", encoding="utf-8")
    assert tree_sha256(tmp_path / "one") != tree_sha256(tmp_path / "two")


def test_tree_sha256_ignores_caches_and_manifest(tmp_path: Path) -> None:
    root = tmp_path / "t"
    _tree(root)
    before = tree_sha256(root)
    (root / "pkg" / "__pycache__").mkdir()
    (root / "pkg" / "__pycache__" / "a.cpython-313.pyc").write_bytes(b"\0")
    (root / ".DS_Store").write_bytes(b"\0")
    (root / "extension.toml").write_text("[extension]\n", encoding="utf-8")
    assert tree_sha256(root) == before


def test_tree_sha256_rejects_symlink(tmp_path: Path) -> None:
    root = tmp_path / "t"
    _tree(root)
    (root / "leak").symlink_to(tmp_path)
    with pytest.raises(ValueError, match="symlink"):
        tree_sha256(root)

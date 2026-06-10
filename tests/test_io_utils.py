"""M-R1.5: shared JSON load + atomic write helpers."""

from __future__ import annotations

from pathlib import Path

from veles.core.io_utils import atomic_write_json, load_optional_json


def test_load_missing_returns_default(tmp_path: Path) -> None:
    assert load_optional_json(tmp_path / "nope.json") is None
    assert load_optional_json(tmp_path / "nope.json", default={}) == {}


def test_load_bad_json_returns_default(tmp_path: Path) -> None:
    p = tmp_path / "bad.json"
    p.write_text("not { valid json", encoding="utf-8")
    assert load_optional_json(p) is None
    assert load_optional_json(p, default={"x": 1}) == {"x": 1}


def test_load_success(tmp_path: Path) -> None:
    p = tmp_path / "ok.json"
    p.write_text('{"a": 1, "b": "two"}', encoding="utf-8")
    assert load_optional_json(p) == {"a": 1, "b": "two"}


def test_atomic_write_creates_file(tmp_path: Path) -> None:
    p = tmp_path / "out.json"
    atomic_write_json(p, {"k": "v"})
    assert p.is_file()
    assert load_optional_json(p) == {"k": "v"}


def test_atomic_write_creates_parent_dir(tmp_path: Path) -> None:
    p = tmp_path / "nested" / "deeper" / "out.json"
    atomic_write_json(p, {"ok": True})
    assert p.is_file()


def test_atomic_write_replaces_existing(tmp_path: Path) -> None:
    p = tmp_path / "out.json"
    atomic_write_json(p, {"v": 1})
    atomic_write_json(p, {"v": 2})
    assert load_optional_json(p) == {"v": 2}


def test_atomic_write_with_mode(tmp_path: Path) -> None:
    """Mode is applied via os.chmod after the rename — useful for
    token files that need 0600."""
    import os
    import stat

    p = tmp_path / "secret.json"
    atomic_write_json(p, {"token": "x"}, mode=0o600)
    perms = stat.S_IMODE(os.stat(p).st_mode)
    assert perms == 0o600

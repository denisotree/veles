"""Unit tests for the file-backed CuratorState (cursor for veles curate)."""

from __future__ import annotations

from pathlib import Path

import pytest

from veles.core.curator_state import CuratorState, load, save_atomic


def test_load_missing_file_returns_default(tmp_path: Path) -> None:
    state = load(tmp_path / "does-not-exist.json")
    assert state == CuratorState(last_curated_at=0.0, sessions_curated_total=0)


def test_save_and_load_roundtrip(tmp_path: Path) -> None:
    path = tmp_path / "curator.state.json"
    save_atomic(path, CuratorState(last_curated_at=1700000000.5, sessions_curated_total=7))
    assert load(path) == CuratorState(last_curated_at=1700000000.5, sessions_curated_total=7)


def test_load_corrupted_json_returns_default(tmp_path: Path) -> None:
    path = tmp_path / "broken.json"
    path.write_text("{not valid json", encoding="utf-8")
    assert load(path) == CuratorState()


def test_load_partial_json_uses_defaults(tmp_path: Path) -> None:
    path = tmp_path / "partial.json"
    path.write_text('{"last_curated_at": 12.0}', encoding="utf-8")
    assert load(path) == CuratorState(last_curated_at=12.0, sessions_curated_total=0)


def test_save_overwrites_existing(tmp_path: Path) -> None:
    path = tmp_path / "curator.state.json"
    save_atomic(path, CuratorState(last_curated_at=1.0, sessions_curated_total=1))
    save_atomic(path, CuratorState(last_curated_at=99.0, sessions_curated_total=42))
    assert load(path) == CuratorState(last_curated_at=99.0, sessions_curated_total=42)


def test_save_atomic_does_not_leak_tempfile_on_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "curator.state.json"

    def boom(*_args, **_kwargs):
        raise RuntimeError("simulated rename failure")

    # M-R1.5: atomic write moved into core/io_utils.py; patch os.replace there.
    monkeypatch.setattr("veles.core.io_utils.os.replace", boom)
    with pytest.raises(RuntimeError, match="simulated"):
        save_atomic(path, CuratorState(last_curated_at=1.0, sessions_curated_total=1))
    assert not path.exists()
    assert list(tmp_path.glob("*.tmp")) == []

"""Unit tests for the file-backed BudgetSnapshot used to propagate the
cumulative token budget across parent/child process boundaries.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from veles.core.budget_state import BudgetSnapshot, load, save_atomic


def test_save_and_load_roundtrip(tmp_path: Path) -> None:
    path = tmp_path / "budget.state.json"
    save_atomic(path, BudgetSnapshot(limit=50_000, consumed=1_234))
    loaded = load(path)
    assert loaded == BudgetSnapshot(limit=50_000, consumed=1_234)


def test_load_missing_file_returns_none(tmp_path: Path) -> None:
    assert load(tmp_path / "does-not-exist.json") is None


def test_load_corrupted_json_returns_none(tmp_path: Path) -> None:
    path = tmp_path / "broken.json"
    path.write_text("{not valid json", encoding="utf-8")
    assert load(path) is None


def test_load_missing_keys_returns_none(tmp_path: Path) -> None:
    path = tmp_path / "incomplete.json"
    path.write_text('{"limit": 100}', encoding="utf-8")
    assert load(path) is None


def test_save_overwrites_existing_file(tmp_path: Path) -> None:
    path = tmp_path / "budget.state.json"
    save_atomic(path, BudgetSnapshot(limit=100, consumed=10))
    save_atomic(path, BudgetSnapshot(limit=100, consumed=42))
    assert load(path) == BudgetSnapshot(limit=100, consumed=42)


def test_save_zero_consumed_boundary(tmp_path: Path) -> None:
    path = tmp_path / "budget.state.json"
    save_atomic(path, BudgetSnapshot(limit=50_000, consumed=0))
    loaded = load(path)
    assert loaded is not None
    assert loaded.consumed == 0


def test_save_creates_parent_directory(tmp_path: Path) -> None:
    path = tmp_path / "nested" / "deep" / "budget.state.json"
    save_atomic(path, BudgetSnapshot(limit=10, consumed=1))
    assert load(path) == BudgetSnapshot(limit=10, consumed=1)


def test_save_atomic_does_not_leak_tempfile_on_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "budget.state.json"

    def boom(*args, **kwargs):
        raise RuntimeError("simulated rename failure")

    # M-R1.5: atomic write moved into core/io_utils.py; patch os.replace there.
    monkeypatch.setattr("veles.core.io_utils.os.replace", boom)
    with pytest.raises(RuntimeError, match="simulated"):
        save_atomic(path, BudgetSnapshot(limit=10, consumed=1))
    assert not path.exists()
    # Tempfile prefix is now derived from path.name; just check no .tmp leak.
    leftover = list(tmp_path.glob("*.tmp"))
    assert leftover == []

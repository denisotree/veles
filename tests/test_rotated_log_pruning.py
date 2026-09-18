"""M257: rotated `traces.jsonl.*` / `events.jsonl.*` are pruned, not kept forever.

`trace.py` used to say outright that keeping every rotated sibling was fine
because "cleanup is a curator concern" — and the curator never implemented it, so
nothing pruned them at all. Measured volume says this is a slow leak, not a fire:
~530 B per trace record and ~1.1 KB of events per agent turn puts the first 50 MB
rotation years out at ordinary usage. It is cheap to close once and impossible to
notice until it matters, which is exactly the kind of thing that never gets done
later.

The prune runs on rotation, so a project that never rotates never pays for it.
"""

from __future__ import annotations

import os
import time
from pathlib import Path

import pytest

from veles.core.events import EventWriter, UserMessage
from veles.core.io_utils import prune_rotated
from veles.core.trace import TraceRecord, TraceWriter, hash_text, hash_tools, now_iso


def _record(request_id: str = "r1") -> TraceRecord:
    return TraceRecord(
        request_id=request_id,
        session_id="s1",
        ts=now_iso(),
        provider="openrouter",
        model="m",
        system_prompt_hash=hash_text("p"),
        tool_bundle_hash=hash_tools(None),
    )


def _rotated(path: Path) -> list[str]:
    return sorted(p.name for p in path.parent.glob(f"{path.name}.*"))


# ---- the helper ----


def test_keeps_the_newest_and_drops_the_rest(tmp_path: Path) -> None:
    live = tmp_path / "traces.jsonl"
    live.write_text("live\n", encoding="utf-8")
    for i in range(5):
        sibling = tmp_path / f"traces.jsonl.{1000 + i}"
        sibling.write_text("old\n", encoding="utf-8")
        os.utime(sibling, (time.time() + i, time.time() + i))

    removed = prune_rotated(live, keep=2)

    assert len(removed) == 3
    assert _rotated(live) == ["traces.jsonl.1003", "traces.jsonl.1004"]
    assert live.exists(), "the live file must never be pruned"


def test_ordering_is_by_mtime_not_by_name(tmp_path: Path) -> None:
    """Same-second rotations produce `.<ts>` and `.<ts>.<n>`, whose lexical order
    does not match age. Sorting by name would delete the wrong file."""
    live = tmp_path / "traces.jsonl"
    live.write_text("live\n", encoding="utf-8")
    older = tmp_path / "traces.jsonl.1000.1"
    newer = tmp_path / "traces.jsonl.1000"
    for path, when in ((older, 100.0), (newer, 200.0)):
        path.write_text("x\n", encoding="utf-8")
        os.utime(path, (when, when))

    prune_rotated(live, keep=1)

    assert _rotated(live) == ["traces.jsonl.1000"]


def test_unrelated_neighbours_are_untouched(tmp_path: Path) -> None:
    """Only `<name>.<digits>` is a rotation of ours. `traces.jsonl.bak` is
    somebody's backup, and `events.jsonl` is a different log entirely."""
    live = tmp_path / "traces.jsonl"
    live.write_text("live\n", encoding="utf-8")
    (tmp_path / "traces.jsonl.bak").write_text("mine\n", encoding="utf-8")
    (tmp_path / "events.jsonl").write_text("other\n", encoding="utf-8")
    (tmp_path / "traces.jsonl.1").write_text("rotated\n", encoding="utf-8")

    prune_rotated(live, keep=0)

    assert (tmp_path / "traces.jsonl.bak").exists()
    assert (tmp_path / "events.jsonl").exists()
    assert not (tmp_path / "traces.jsonl.1").exists()


def test_keep_zero_removes_every_rotation(tmp_path: Path) -> None:
    live = tmp_path / "t.jsonl"
    live.write_text("x\n", encoding="utf-8")
    (tmp_path / "t.jsonl.1").write_text("a\n", encoding="utf-8")
    assert prune_rotated(live, keep=0)
    assert _rotated(live) == []


def test_negative_keep_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        prune_rotated(tmp_path / "t.jsonl", keep=-1)


def test_nothing_to_prune_is_not_an_error(tmp_path: Path) -> None:
    assert prune_rotated(tmp_path / "missing.jsonl", keep=3) == []


# ---- wired into both writers ----


def test_trace_writer_prunes_on_rotation(tmp_path: Path) -> None:
    path = tmp_path / "traces.jsonl"
    writer = TraceWriter(path, max_bytes=1, keep_rotated=2)
    for i in range(5):
        writer.write(_record(f"r{i}"))
        time.sleep(0.01)  # distinct mtimes

    assert len(_rotated(path)) == 2
    assert path.exists()


def test_event_writer_prunes_on_rotation(tmp_path: Path) -> None:
    path = tmp_path / "events.jsonl"
    writer = EventWriter(path, max_bytes=1, keep_rotated=2)
    for i in range(5):
        writer.write(UserMessage(ts=now_iso(), session_id="s", text=f"m{i}"))
        time.sleep(0.01)

    assert len(_rotated(path)) == 2
    assert path.exists()


def test_writers_keep_history_when_pruning_is_off(tmp_path: Path) -> None:
    """`keep_rotated=0` means "no prune" for the *live* file but wipes rotations;
    an operator who wants the full history passes a large keep instead. This
    guards the escape hatch rather than the default."""
    path = tmp_path / "traces.jsonl"
    writer = TraceWriter(path, max_bytes=1, keep_rotated=1000)
    for i in range(4):
        writer.write(_record(f"r{i}"))
        time.sleep(0.01)

    assert len(_rotated(path)) == 3

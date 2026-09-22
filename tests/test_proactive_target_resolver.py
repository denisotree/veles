"""M214 — proactive delivery target resolution (last active channel / override)."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from veles.channels.session_map import SessionMap, channel_session_path
from veles.core.proactive.target_resolver import (
    last_active_target,
    resolve_last_active_target,
)


def _write_map(base: Path, channel: str, entries: dict[str, float]) -> None:
    path = channel_session_path(channel, base_dir=base)
    m = SessionMap(
        path=path,
        entries={
            key: {"session_id": f"s-{key}", "last_used_at": ts} for key, ts in entries.items()
        },
    )
    m.save()


def test_none_on_cold_start(tmp_path: Path):
    assert last_active_target(["telegram"], base_dir=tmp_path) is None


# Maps are keyed as a gateway keys a chat — `str(chat_id)` — so the resolver
# builds the target `<channel>:<key>`. Pre-M278 it returned the bare key, and
# these tests wrote target-shaped keys that no gateway ever writes.


def test_picks_most_recent_within_a_channel(tmp_path: Path):
    _write_map(tmp_path, "telegram", {"1": 100.0, "2": 300.0, "3": 50.0})
    assert last_active_target(["telegram"], base_dir=tmp_path) == "telegram:2"


def test_picks_globally_most_recent_across_channels(tmp_path: Path):
    _write_map(tmp_path, "telegram", {"1": 100.0})
    _write_map(tmp_path, "slack", {"C9": 500.0})
    got = last_active_target(["telegram", "slack"], base_dir=tmp_path)
    assert got == "slack:C9"


def test_skips_keys_the_pre_m278_binder_wrote(tmp_path: Path):
    _write_map(tmp_path, "telegram", {"42": 100.0, "telegram:42": 900.0})
    assert last_active_target(["telegram"], base_dir=tmp_path) == "telegram:42"


def test_a_named_daemon_reads_its_own_map(tmp_path: Path):
    """`_channel_session_map` keeps a named daemon's chats in
    `<name>-<channel>-sessions.json`; the resolver read only `<channel>`."""
    _write_map(tmp_path, "work-telegram", {"7": 100.0})
    assert last_active_target(["telegram"], base_dir=tmp_path, session_name="work") == "telegram:7"
    assert last_active_target(["telegram"], base_dir=tmp_path) is None


def test_resolve_uses_config_override_first(tmp_path: Path, monkeypatch):
    _write_map(tmp_path, "telegram", {"1": 100.0})

    import veles.core.proactive.target_resolver as tr

    monkeypatch.setattr(tr, "_config_target", lambda _project: "telegram:override")
    state = SimpleNamespace(project=object(), active_channels=["telegram"])
    # base_dir isn't threaded through resolve_*, but the override short-circuits
    # before any map read, so the pinned target wins regardless.
    assert resolve_last_active_target(state) == "telegram:override"


def test_resolve_falls_back_to_last_active(monkeypatch, tmp_path: Path):
    _write_map(tmp_path, "telegram", {"7": 900.0})

    import veles.core.proactive.target_resolver as tr

    monkeypatch.setattr(tr, "_config_target", lambda _project: None)
    monkeypatch.setattr(
        tr,
        "last_active_target",
        lambda channels, **kw: last_active_target(channels, base_dir=tmp_path, **kw),
    )
    state = SimpleNamespace(project=object(), active_channels=["telegram"])
    assert resolve_last_active_target(state) == "telegram:7"

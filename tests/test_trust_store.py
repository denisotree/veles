"""M38 — TrustStore JSON persistence."""

from __future__ import annotations

from pathlib import Path

import pytest

from veles.core.trust_store import TrustStore, user_trust_path


def test_fresh_load_returns_empty_store(tmp_path: Path) -> None:
    store = TrustStore.load(tmp_path / "trust.json")
    assert store.tools == {}
    assert not store.is_granted("run_shell")


def test_grant_persists_round_trip(tmp_path: Path) -> None:
    target = tmp_path / "trust.json"
    store = TrustStore.load(target)
    store.grant("run_shell")
    assert target.is_file()
    reloaded = TrustStore.load(target)
    assert reloaded.is_granted("run_shell")
    assert "run_shell" in reloaded.tools
    assert reloaded.tools["run_shell"].endswith("Z")


def test_revoke_removes_entry(tmp_path: Path) -> None:
    target = tmp_path / "trust.json"
    store = TrustStore.load(target)
    store.grant("run_shell")
    assert store.revoke("run_shell") is True
    reloaded = TrustStore.load(target)
    assert not reloaded.is_granted("run_shell")


def test_revoke_unknown_returns_false(tmp_path: Path) -> None:
    store = TrustStore.load(tmp_path / "trust.json")
    assert store.revoke("never_granted") is False


def test_corrupt_json_loads_empty(tmp_path: Path) -> None:
    target = tmp_path / "trust.json"
    target.write_text("{not json", encoding="utf-8")
    store = TrustStore.load(target)
    assert store.tools == {}


def test_non_dict_root_loads_empty(tmp_path: Path) -> None:
    target = tmp_path / "trust.json"
    target.write_text("[]", encoding="utf-8")
    store = TrustStore.load(target)
    assert store.tools == {}


def test_missing_tools_key_loads_empty(tmp_path: Path) -> None:
    target = tmp_path / "trust.json"
    target.write_text('{"version": 1}', encoding="utf-8")
    store = TrustStore.load(target)
    assert store.tools == {}


def test_malformed_entry_silently_skipped(tmp_path: Path) -> None:
    target = tmp_path / "trust.json"
    target.write_text(
        '{"tools": {"good": {"granted_at": "2026-05-10T00:00:00Z"}, '
        '"bad_no_dict": "string", "bad_no_iso": {"granted_at": 42}}}',
        encoding="utf-8",
    )
    store = TrustStore.load(target)
    assert store.is_granted("good")
    assert not store.is_granted("bad_no_dict")
    assert not store.is_granted("bad_no_iso")


def test_multiple_grants_kept_alphabetical(tmp_path: Path) -> None:
    target = tmp_path / "trust.json"
    store = TrustStore.load(target)
    store.grant("write_file")
    store.grant("fetch_url")
    store.grant("run_shell")
    saved = target.read_text(encoding="utf-8")
    # grants written sorted by tool name
    assert saved.index("fetch_url") < saved.index("run_shell") < saved.index("write_file")


def test_user_trust_path_uses_user_home_env(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("VELES_USER_HOME", str(tmp_path))
    assert user_trust_path() == tmp_path / ".veles" / "trust.json"


def test_user_trust_path_falls_back_to_home(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv("VELES_USER_HOME", raising=False)
    monkeypatch.setattr(
        "veles.core.trust_store.Path.home",
        classmethod(lambda cls: tmp_path),
    )
    assert user_trust_path() == tmp_path / ".veles" / "trust.json"


def test_save_creates_parent_directory(tmp_path: Path) -> None:
    nested = tmp_path / "a" / "b" / "trust.json"
    store = TrustStore.load(nested)
    store.grant("run_shell")
    assert nested.is_file()

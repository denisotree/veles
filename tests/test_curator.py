"""Unit tests for the `veles curate` command logic.

Avoids real LLM calls by monkey-patching `_run_agent_streaming_aware` at
the cli.py module level. The curator's contract — cursor advancement,
quiet-window filter, failure-stops-batch — is asserted on observable
state files and store cursors, not internal call counts.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import pytest

from veles.cli import (
    _CURATE_QUIET_WINDOW_SEC,
    _CURATOR_IDLE_THRESHOLD_SEC,
    _cmd_curate,
    _continuous_curator_eligible,
    _curate_one_session,
    _maybe_run_idle_curator,
    _maybe_run_post_turn_curator,
    _render_message,
    _truncate_session_messages,
)
from veles.core.agent import RunResult
from veles.core.context import TokenBudget
from veles.core.curator_state import CuratorState
from veles.core.curator_state import load as load_curator_state
from veles.core.curator_state import save_atomic as save_curator_state
from veles.core.memory import SessionStore
from veles.core.project import init_project
from veles.core.provider import Message, ToolCall


def _make_args(provider: str = "openrouter", **overrides: Any) -> Any:
    class Ns:
        pass

    ns = Ns()
    ns.provider = provider
    ns.model = "anthropic/claude-sonnet-4.6"
    ns.max_iterations = 5
    ns.max_tokens_total = 0
    ns.verbose = False
    ns.stream = False
    ns.limit = 20
    for k, v in overrides.items():
        setattr(ns, k, v)
    return ns


def _make_completed(text: str = "ok") -> tuple[RunResult, TokenBudget]:
    return RunResult(text=text, iterations=1, stopped_reason="completed"), TokenBudget(limit=0)


def _make_failed() -> tuple[RunResult, TokenBudget]:
    return RunResult(text="", iterations=5, stopped_reason="max_iterations"), TokenBudget(limit=0)


def _seed_session(store: SessionStore, *, n_turns: int = 2, age_sec: float = 120.0) -> str:
    sid = store.create_session()
    for i in range(n_turns):
        store.append_turn(sid, Message(role="user", content=f"turn {i}"))
    # age the session by rewriting last_activity_at
    target = time.time() - age_sec
    store._conn.execute("UPDATE sessions SET last_activity_at=? WHERE id=?", (target, sid))
    store._conn.execute("UPDATE turns SET created_at=? WHERE session_id=?", (target, sid))
    return sid


def test_render_message_includes_role_and_content() -> None:
    out = _render_message(Message(role="user", content="hello"))
    assert out == "[user] hello"


def test_render_message_includes_tool_calls() -> None:
    msg = Message(
        role="assistant",
        content=None,
        tool_calls=[ToolCall(id="c1", name="run_shell", arguments={"command": "ls"})],
    )
    out = _render_message(msg)
    assert "[assistant]" in out
    assert "run_shell" in out
    assert "command" in out


def test_truncate_keeps_short_input_intact() -> None:
    msgs = [Message(role="user", content=f"m{i}") for i in range(5)]
    out = _truncate_session_messages(msgs, max_turns=10, max_chars=10_000)
    assert "truncated" not in out
    assert all(f"m{i}" in out for i in range(5))


def test_truncate_drops_middle_turns_when_over_limit() -> None:
    msgs = [Message(role="user", content=f"m{i}") for i in range(20)]
    out = _truncate_session_messages(msgs, max_turns=8, max_chars=10_000)
    assert "<...truncated 12 turns to fit budget...>" in out
    # First 4 + last 4 retained
    for i in range(4):
        assert f"m{i}" in out
    for i in range(16, 20):
        assert f"m{i}" in out
    # Some middle turn should be missing
    assert "m10" not in out


def test_truncate_caps_chars() -> None:
    msgs = [Message(role="user", content="x" * 1000) for _ in range(20)]
    out = _truncate_session_messages(msgs, max_turns=80, max_chars=2_000)
    assert "<...truncated mid-content to fit 2000 chars...>" in out
    assert len(out) < 4_000  # ~ 2k + marker overhead


def test_curate_one_session_advances_on_completed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = init_project(tmp_path, name="t")
    store = SessionStore(project.memory_db_path)
    sid = _seed_session(store, n_turns=3, age_sec=120)
    session = store.get_session(sid)
    assert session is not None

    monkeypatch.setattr("veles.cli._run_agent_streaming_aware", lambda *a, **kw: _make_completed())
    monkeypatch.setattr("veles.cli._make_tool_aware_provider", lambda *a, **kw: _stub_provider())
    monkeypatch.setattr(
        "veles.cli._load_skills",
        lambda project, base, *, provider, model: _empty_registry(),
    )
    monkeypatch.setattr("veles.cli._qualify_for_provider", lambda p, *a, **kw: p)

    ok = _curate_one_session(store, session, _make_args(), project)
    assert ok is True
    store.close()


def test_curate_one_session_returns_false_on_max_iterations(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = init_project(tmp_path, name="t")
    store = SessionStore(project.memory_db_path)
    sid = _seed_session(store, n_turns=2, age_sec=120)
    session = store.get_session(sid)
    assert session is not None

    monkeypatch.setattr("veles.cli._run_agent_streaming_aware", lambda *a, **kw: _make_failed())
    monkeypatch.setattr("veles.cli._make_tool_aware_provider", lambda *a, **kw: _stub_provider())
    monkeypatch.setattr(
        "veles.cli._load_skills",
        lambda project, base, *, provider, model: _empty_registry(),
    )
    monkeypatch.setattr("veles.cli._qualify_for_provider", lambda p, *a, **kw: p)

    ok = _curate_one_session(store, session, _make_args(), project)
    assert ok is False
    store.close()


def test_cmd_curate_no_new_sessions_returns_zero(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    project = init_project(tmp_path, name="t")
    monkeypatch.setenv("OPENROUTER_API_KEY", "fake")
    rc = _cmd_curate(_make_args(), project)
    assert rc == 0
    err = capsys.readouterr().err
    assert "no new sessions" in err


def test_cmd_curate_skips_quiet_window(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    project = init_project(tmp_path, name="t")
    monkeypatch.setenv("OPENROUTER_API_KEY", "fake")
    store = SessionStore(project.memory_db_path)
    # session whose last_activity_at is INSIDE quiet window (10 sec ago)
    _seed_session(store, n_turns=2, age_sec=_CURATE_QUIET_WINDOW_SEC - 10)
    store.close()

    monkeypatch.setattr("veles.cli._run_agent_streaming_aware", lambda *a, **kw: _make_completed())
    monkeypatch.setattr("veles.cli._make_tool_aware_provider", lambda *a, **kw: _stub_provider())
    monkeypatch.setattr(
        "veles.cli._load_skills",
        lambda project, base, *, provider, model: _empty_registry(),
    )
    monkeypatch.setattr("veles.cli._qualify_for_provider", lambda p, *a, **kw: p)

    rc = _cmd_curate(_make_args(), project)
    assert rc == 0
    err = capsys.readouterr().err
    assert "no new sessions" in err
    assert not (project.state_dir / "curator.state.json").exists()


def test_cmd_curate_advances_state_on_success(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = init_project(tmp_path, name="t")
    monkeypatch.setenv("OPENROUTER_API_KEY", "fake")
    store = SessionStore(project.memory_db_path)
    _seed_session(store, n_turns=3, age_sec=120)
    _seed_session(store, n_turns=2, age_sec=90)
    store.close()

    monkeypatch.setattr("veles.cli._run_agent_streaming_aware", lambda *a, **kw: _make_completed())
    monkeypatch.setattr("veles.cli._make_tool_aware_provider", lambda *a, **kw: _stub_provider())
    monkeypatch.setattr(
        "veles.cli._load_skills",
        lambda project, base, *, provider, model: _empty_registry(),
    )
    monkeypatch.setattr("veles.cli._qualify_for_provider", lambda p, *a, **kw: p)

    rc = _cmd_curate(_make_args(), project)
    assert rc == 0
    state_path = project.state_dir / "curator.state.json"
    assert state_path.exists()
    state = load_curator_state(state_path)
    assert state.sessions_curated_total == 2
    assert state.last_curated_at > 0

    # System-ops journal entry written
    log = (project.memory_dir / "LOG.md").read_text(encoding="utf-8")
    assert "curate-batch" in log

    # Second invocation: nothing new (cursor at the latest), exit 0 with no-new message
    rc2 = _cmd_curate(_make_args(), project)
    assert rc2 == 0


def test_cmd_curate_failure_stops_batch_and_does_not_advance(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = init_project(tmp_path, name="t")
    monkeypatch.setenv("OPENROUTER_API_KEY", "fake")
    store = SessionStore(project.memory_db_path)
    _seed_session(store, n_turns=2, age_sec=200)
    _seed_session(store, n_turns=2, age_sec=150)
    store.close()

    # First call succeeds, second fails
    calls = {"n": 0}

    def fake(*_a: Any, **_kw: Any) -> tuple[RunResult, TokenBudget]:
        calls["n"] += 1
        if calls["n"] == 1:
            return _make_completed()
        return _make_failed()

    monkeypatch.setattr("veles.cli._run_agent_streaming_aware", fake)
    monkeypatch.setattr("veles.cli._make_tool_aware_provider", lambda *a, **kw: _stub_provider())
    monkeypatch.setattr(
        "veles.cli._load_skills",
        lambda project, base, *, provider, model: _empty_registry(),
    )
    monkeypatch.setattr("veles.cli._qualify_for_provider", lambda p, *a, **kw: p)

    rc = _cmd_curate(_make_args(), project)
    assert rc == 0
    state = load_curator_state(project.state_dir / "curator.state.json")
    # Only the first session counted; cursor advanced to its last_activity_at
    assert state.sessions_curated_total == 1


def test_persistently_failing_session_is_skipped_after_three_attempts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Poison-pill guard (live 2026-07-08): one session failing curation forever
    blocked the whole curator queue — every post-turn pass retried it, failed,
    and stopped ("<curate (post-turn) failed …; stopping>" on every turn). After
    3 failed attempts the cursor must advance past it so curation continues."""
    project = init_project(tmp_path, name="t")
    monkeypatch.setenv("OPENROUTER_API_KEY", "fake")
    store = SessionStore(project.memory_db_path)
    _seed_session(store, n_turns=2, age_sec=200)
    store.close()

    calls = {"n": 0}

    def always_fail(*_a: Any, **_kw: Any) -> tuple[RunResult, TokenBudget]:
        calls["n"] += 1
        return _make_failed()

    monkeypatch.setattr("veles.cli._run_agent_streaming_aware", always_fail)
    monkeypatch.setattr("veles.cli._make_tool_aware_provider", lambda *a, **kw: _stub_provider())
    monkeypatch.setattr(
        "veles.cli._load_skills",
        lambda project, base, *, provider, model: _empty_registry(),
    )
    monkeypatch.setattr("veles.cli._qualify_for_provider", lambda p, *a, **kw: p)

    for _ in range(3):
        _cmd_curate(_make_args(), project)
    assert calls["n"] == 3

    state = load_curator_state(project.state_dir / "curator.state.json")
    assert state.last_curated_at > 0  # cursor advanced PAST the poison session
    assert state.sessions_curated_total == 0  # skipped, never counted as curated

    # A 4th pass must NOT retry the abandoned session.
    _cmd_curate(_make_args(), project)
    assert calls["n"] == 3


# ---- helpers ----


def _stub_provider():
    # Provider is never actually called in these tests (the agent run is
    # stubbed); only `name`/`supports_tools` are inspected.
    from tests.conftest import StubProvider

    return StubProvider(name="openrouter")


def _empty_registry():
    from veles.core.tools.registry import Registry

    return Registry()


def test_cmd_curate_state_json_format(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project = init_project(tmp_path, name="t")
    monkeypatch.setenv("OPENROUTER_API_KEY", "fake")
    store = SessionStore(project.memory_db_path)
    _seed_session(store, n_turns=1, age_sec=120)
    store.close()

    monkeypatch.setattr("veles.cli._run_agent_streaming_aware", lambda *a, **kw: _make_completed())
    monkeypatch.setattr("veles.cli._make_tool_aware_provider", lambda *a, **kw: _stub_provider())
    monkeypatch.setattr(
        "veles.cli._load_skills",
        lambda project, base, *, provider, model: _empty_registry(),
    )
    monkeypatch.setattr("veles.cli._qualify_for_provider", lambda p, *a, **kw: p)

    _cmd_curate(_make_args(), project)
    raw = (project.state_dir / "curator.state.json").read_text(encoding="utf-8")
    parsed = json.loads(raw)
    # M67 extends state with dream cursors; assert legacy fields still present
    # and required, but allow newer keys to coexist.
    assert {"last_curated_at", "sessions_curated_total"}.issubset(set(parsed.keys()))
    assert parsed["sessions_curated_total"] == 1


# ---- M28: continuous curator triggers ----


def _run_args(**overrides: Any) -> Any:
    """Args shaped for `veles run` — includes resume + no_curator flags."""
    base: dict[str, Any] = {"resume": None, "no_curator": False}
    base.update(overrides)
    return _make_args(**base)


def test_eligible_when_fresh_openrouter_run_with_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "fake")
    assert _continuous_curator_eligible(_run_args()) is True


def test_not_eligible_when_no_curator_set(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "fake")
    assert _continuous_curator_eligible(_run_args(no_curator=True)) is False


def test_not_eligible_on_resume(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "fake")
    assert _continuous_curator_eligible(_run_args(resume="abc123")) is False


def test_not_eligible_on_cli_delegate_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "fake")
    assert _continuous_curator_eligible(_run_args(provider="claude-cli")) is False


def test_not_eligible_without_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    assert _continuous_curator_eligible(_run_args()) is False


def test_eligible_on_local_provider_without_key(monkeypatch: pytest.MonkeyPatch) -> None:
    # M184: local providers (ollama/llamacpp/openai-compat) authenticate via
    # their own runtime, not an API key, so the continuous curator must treat
    # them as eligible. The old `provider in PROVIDER_API_KEY_ENVS` membership
    # gate silently excluded them, disabling curation for local-model setups.
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    assert _continuous_curator_eligible(_run_args(provider="ollama")) is True


def test_not_eligible_when_provider_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    # M184: a bare `args.provider` of None (the daemon/channel start Namespace
    # when no `--provider` was passed) must not be eligible — the effective
    # provider has to be resolved upstream first.
    monkeypatch.setenv("OPENROUTER_API_KEY", "fake")
    assert _continuous_curator_eligible(_run_args(provider=None)) is False


def test_idle_curator_skips_when_cursor_is_fresh(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = init_project(tmp_path, name="t")
    monkeypatch.setenv("OPENROUTER_API_KEY", "fake")
    # Seed a stale session to ensure inaction is from the threshold gate, not
    # from "no candidates".
    store = SessionStore(project.memory_db_path)
    _seed_session(store, n_turns=2, age_sec=120)
    store.close()
    # Save state with last_curated_at = now → way under 24h threshold.
    save_curator_state(
        project.state_dir / "curator.state.json",
        CuratorState(last_curated_at=time.time(), sessions_curated_total=0),
    )
    called = []

    def fake_pass(*args, **kwargs):
        called.append(kwargs.get("mode_label"))
        return None

    monkeypatch.setattr("veles.cli._run_curator_pass", fake_pass)
    _maybe_run_idle_curator(_run_args(), project)
    assert called == []


def test_idle_curator_fires_when_cursor_stale(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    project = init_project(tmp_path, name="t")
    monkeypatch.setenv("OPENROUTER_API_KEY", "fake")
    save_curator_state(
        project.state_dir / "curator.state.json",
        CuratorState(
            last_curated_at=time.time() - _CURATOR_IDLE_THRESHOLD_SEC - 60,
            sessions_curated_total=0,
        ),
    )
    captured = []

    def fake_pass(args, project, *, max_sessions, mode_label):
        captured.append((max_sessions, mode_label))
        return None

    monkeypatch.setattr("veles.cli._run_curator_pass", fake_pass)
    _maybe_run_idle_curator(_run_args(), project)
    assert captured == [(5, "idle")]
    assert "idle curator" in capsys.readouterr().err


def test_idle_curator_skipped_when_eligibility_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = init_project(tmp_path, name="t")
    monkeypatch.setenv("OPENROUTER_API_KEY", "fake")
    save_curator_state(
        project.state_dir / "curator.state.json",
        CuratorState(
            last_curated_at=time.time() - _CURATOR_IDLE_THRESHOLD_SEC - 60,
            sessions_curated_total=0,
        ),
    )
    called = []
    monkeypatch.setattr(
        "veles.cli._run_curator_pass",
        lambda *a, **kw: called.append(kw.get("mode_label")),
    )
    # --no-curator → bail before even reading state.
    _maybe_run_idle_curator(_run_args(no_curator=True), project)
    # resume → bail.
    _maybe_run_idle_curator(_run_args(resume="abc"), project)
    # provider != openrouter → bail.
    _maybe_run_idle_curator(_run_args(provider="claude-cli"), project)
    assert called == []


def test_post_turn_curator_invokes_pass_when_eligible(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = init_project(tmp_path, name="t")
    monkeypatch.setenv("OPENROUTER_API_KEY", "fake")
    captured = []

    def fake_pass(args, project, *, max_sessions, mode_label):
        captured.append((max_sessions, mode_label))
        return None

    monkeypatch.setattr("veles.cli._run_curator_pass", fake_pass)
    _maybe_run_post_turn_curator(_run_args(), project)
    assert captured == [(1, "post-turn")]


def test_post_turn_curator_logs_skip_on_exception(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = init_project(tmp_path, name="t")
    monkeypatch.setenv("OPENROUTER_API_KEY", "fake")

    def boom(*a, **kw):
        raise RuntimeError("kaboom")

    monkeypatch.setattr("veles.cli._run_curator_pass", boom)
    _maybe_run_post_turn_curator(_run_args(), project)
    log = (project.memory_dir / "LOG.md").read_text(encoding="utf-8")
    assert "curate-skip" in log
    assert "kaboom" in log


def test_post_turn_curator_skipped_when_eligibility_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = init_project(tmp_path, name="t")
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    called = []
    monkeypatch.setattr(
        "veles.cli._run_curator_pass",
        lambda *a, **kw: called.append(kw.get("mode_label")),
    )
    _maybe_run_post_turn_curator(_run_args(), project)
    assert called == []

"""Tests for core/doctor.py — Tier δ M59 health checks."""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any, cast

import pytest

from veles.core.approval import record_approval
from veles.core.doctor import (
    CheckResult,
    DoctorReport,
    _check_agents_md,
    _check_agents_md_identity,
    _check_approval_audit,
    _check_embedding_backend,
    _check_events_health,
    _check_provider_keys,
    _check_python_version,
    _check_registry_paths,
    _check_symlinks,
    _check_trace_health,
    _check_user_config,
    _check_user_home,
    _check_wiki_files,
    run_all,
)
from veles.core.project import Project
from veles.core.trace import TraceRecord, TraceWriter, trace_path_for_project


def _make_project(tmp_path: Path) -> Project:
    state = tmp_path / ".veles"
    state.mkdir(parents=True, exist_ok=True)
    return Project(root=tmp_path, name="test", created_at=0.0)


# ---------- CheckResult / DoctorReport ----------


def test_check_result_is_failing() -> None:
    assert CheckResult(name="x", status="error", message="m").is_failing() is True
    assert CheckResult(name="x", status="warn", message="m").is_failing() is False
    assert CheckResult(name="x", status="ok", message="m").is_failing() is False


def test_report_to_json_round_trip() -> None:
    report = DoctorReport(results=[CheckResult(name="a", status="ok", message="fine")])
    obj = json.loads(report.to_json())
    assert obj["results"][0]["status"] == "ok"
    assert obj["results"][0]["name"] == "a"


def test_report_has_errors_and_warnings() -> None:
    r = DoctorReport(
        results=[
            CheckResult(name="a", status="ok", message="m"),
            CheckResult(name="b", status="warn", message="m"),
            CheckResult(name="c", status="error", message="m"),
        ]
    )
    assert r.has_errors is True
    assert r.has_warnings is True


# ---------- individual checks ----------


def test_python_version_ok() -> None:
    r = _check_python_version()
    assert r.status == "ok"


def test_user_config_invalid_toml(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VELES_USER_HOME", str(tmp_path))
    (tmp_path / ".veles").mkdir()
    (tmp_path / ".veles" / "config.toml").write_text("not = valid = toml = at all")
    r = _check_user_config()
    assert r.status == "error"
    assert "unparseable" in r.message


def test_user_config_missing_is_info(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VELES_USER_HOME", str(tmp_path))
    r = _check_user_config()
    assert r.status == "info"


def test_user_home_missing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VELES_USER_HOME", str(tmp_path / "nope"))
    r = _check_user_home()
    assert r.status == "info"


def test_provider_keys_warn_when_none(monkeypatch: pytest.MonkeyPatch) -> None:
    for env in (
        "OPENROUTER_API_KEY",
        "ANTHROPIC_API_KEY",
        "OPENAI_API_KEY",
        "GOOGLE_API_KEY",
    ):
        monkeypatch.delenv(env, raising=False)
    r = _check_provider_keys()
    assert r.status == "warn"


def test_provider_keys_ok_when_set(monkeypatch: pytest.MonkeyPatch) -> None:
    for env in (
        "OPENROUTER_API_KEY",
        "ANTHROPIC_API_KEY",
        "OPENAI_API_KEY",
        "GOOGLE_API_KEY",
    ):
        monkeypatch.delenv(env, raising=False)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    r = _check_provider_keys()
    assert r.status == "ok"
    assert "anthropic" in r.details["providers"]  # type: ignore[index]


def test_agents_md_missing(tmp_path: Path) -> None:
    proj = _make_project(tmp_path)
    r = _check_agents_md(proj)
    assert r.status == "warn"
    assert "missing" in r.message


def test_agents_md_present(tmp_path: Path) -> None:
    proj = _make_project(tmp_path)
    (tmp_path / "AGENTS.md").write_text("# project")
    r = _check_agents_md(proj)
    assert r.status == "ok"


def test_agents_md_empty_is_warning(tmp_path: Path) -> None:
    proj = _make_project(tmp_path)
    (tmp_path / "AGENTS.md").write_text("")
    r = _check_agents_md(proj)
    assert r.status == "warn"
    assert "empty" in r.message


def test_symlinks_intact(tmp_path: Path) -> None:
    proj = _make_project(tmp_path)
    (tmp_path / "AGENTS.md").write_text("x")
    (tmp_path / "CLAUDE.md").symlink_to("AGENTS.md")
    (tmp_path / "GEMINI.md").symlink_to("AGENTS.md")
    r = _check_symlinks(proj)
    assert r.status == "ok"


def test_symlinks_pointing_elsewhere_warns(tmp_path: Path) -> None:
    proj = _make_project(tmp_path)
    (tmp_path / "AGENTS.md").write_text("x")
    (tmp_path / "CLAUDE.md").symlink_to("OTHER.md")
    (tmp_path / "GEMINI.md").symlink_to("AGENTS.md")
    r = _check_symlinks(proj)
    assert r.status == "warn"
    assert "CLAUDE.md" in r.message


def test_wiki_files_missing(tmp_path: Path) -> None:
    proj = _make_project(tmp_path)
    r = _check_wiki_files(proj)
    assert r.status == "warn"
    assert "INDEX.md" in r.message
    assert "LOG.md" in r.message


def test_wiki_files_present(tmp_path: Path) -> None:
    proj = _make_project(tmp_path)
    (tmp_path / "INDEX.md").write_text("# idx")
    (tmp_path / "LOG.md").write_text("# log")
    r = _check_wiki_files(proj)
    assert r.status == "ok"


def test_trace_health_no_file(tmp_path: Path) -> None:
    proj = _make_project(tmp_path)
    r = _check_trace_health(proj)
    assert r.status == "info"


def test_trace_health_ok_when_small(tmp_path: Path) -> None:
    proj = _make_project(tmp_path)
    w = TraceWriter(trace_path_for_project(proj.state_dir))
    w.write(
        TraceRecord(
            request_id="r",
            session_id=None,
            ts="2026-05-15T00:00:00Z",
            provider="p",
            model="m",
            system_prompt_hash="sha256:abc",
            tool_bundle_hash="sha256:def",
        )
    )
    r = _check_trace_health(proj)
    assert r.status == "ok"
    assert r.details["records"] == 1


def test_trace_health_warns_on_cache_fragmentation(tmp_path: Path) -> None:
    proj = _make_project(tmp_path)
    path = trace_path_for_project(proj.state_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as f:
        for _ in range(6):
            f.write(
                json.dumps(
                    {
                        "request_id": "r",
                        "system_prompt_hash": "sha256:fixed",
                        "cache_read_tokens": 0,
                        "model": "m1",
                        "provider": "p1",
                    }
                )
                + "\n"
            )
    r = _check_trace_health(proj)
    assert r.status == "warn"
    assert "fragmentation" in r.message


def test_events_health_no_file(tmp_path: Path) -> None:
    proj = _make_project(tmp_path)
    r = _check_events_health(proj)
    assert r.status == "info"


def test_approval_audit_no_records(tmp_path: Path) -> None:
    proj = _make_project(tmp_path)
    r = _check_approval_audit(proj)
    assert r.status == "info"
    assert "no approval records" in r.message


def test_approval_audit_flags_recent_autopilot(tmp_path: Path) -> None:
    proj = _make_project(tmp_path)
    record_approval(proj.state_dir, tool_name="t", rule="trust_ladder", via_autopilot=True)
    r = _check_approval_audit(proj)
    assert r.status == "info"
    assert "autopilot" in r.message
    assert r.details["autopilot_count"] == 1  # type: ignore[index]


def test_approval_audit_ok_when_all_user_granted(tmp_path: Path) -> None:
    proj = _make_project(tmp_path)
    record_approval(proj.state_dir, tool_name="t", rule="trust_ladder")
    r = _check_approval_audit(proj)
    assert r.status == "ok"


# ---------- run_all ----------


def test_run_all_skips_project_checks_when_no_project(monkeypatch: pytest.MonkeyPatch) -> None:
    """When project is None, the project-aware checks must short-circuit
    to `info` rather than crashing on missing paths."""
    # Wipe env-dependent state to keep the test deterministic-ish.
    for env in (
        "OPENROUTER_API_KEY",
        "ANTHROPIC_API_KEY",
        "OPENAI_API_KEY",
        "GOOGLE_API_KEY",
    ):
        monkeypatch.delenv(env, raising=False)
    report = run_all(None)
    names = [r.name for r in report.results]
    assert "python_version" in names
    assert "active_project" in names
    assert "approval_audit" in names
    # No error-level results when project is None.
    assert not report.has_errors


def test_run_all_with_project_returns_full_list(tmp_path: Path) -> None:
    proj = _make_project(tmp_path)
    (tmp_path / "AGENTS.md").write_text("# x")
    (tmp_path / "INDEX.md").write_text("# idx")
    (tmp_path / "LOG.md").write_text("# log")
    (tmp_path / "CLAUDE.md").symlink_to("AGENTS.md")
    (tmp_path / "GEMINI.md").symlink_to("AGENTS.md")
    report = run_all(proj)
    # All project-aware checks executed, at least one not 'info'.
    statuses = {r.name: r.status for r in report.results}
    assert statuses["active_project"] == "ok"
    assert statuses["agents_md"] == "ok"
    assert statuses["symlinks"] == "ok"
    assert statuses["wiki_files"] == "ok"


def test_text_output_includes_glyphs(tmp_path: Path) -> None:
    """Sanity for the human-readable renderer — every status maps to a glyph."""
    report = DoctorReport(
        results=[
            CheckResult(name="a", status="ok", message="m"),
            CheckResult(name="b", status="warn", message="m"),
            CheckResult(name="c", status="error", message="m"),
            CheckResult(name="d", status="info", message="m"),
        ]
    )
    text = report.to_text()
    assert "OK" in text
    assert "WARN" in text
    assert "ERROR" in text
    assert "INFO" in text
    assert "1 ok" in text
    assert "1 warn" in text
    assert "1 error" in text


# ---------- M181: stale-clone / dead-registry checks ----------

_DEFAULT_AGENTS = "# {name}\n\nAdd your project context here.\n\n## Layout\n\n- x\n"


def test_agents_md_identity_flags_cloned_default(tmp_path: Path) -> None:
    """Unmodified default whose H1 names a *different* project → warn."""
    project = _make_project(tmp_path)  # name="test"
    (tmp_path / "AGENTS.md").write_text(
        _DEFAULT_AGENTS.format(name="mind-palace"), encoding="utf-8"
    )
    result = _check_agents_md_identity(project)
    assert result.status == "warn"
    assert "mind-palace" in result.message and "test" in result.message


def test_agents_md_identity_ok_when_title_matches(tmp_path: Path) -> None:
    project = _make_project(tmp_path)
    (tmp_path / "AGENTS.md").write_text(_DEFAULT_AGENTS.format(name="test"), encoding="utf-8")
    assert _check_agents_md_identity(project).status == "ok"


def test_agents_md_identity_never_flags_customised(tmp_path: Path) -> None:
    """A customised AGENTS.md (default marker gone) is user content — never
    flagged, even if its title differs from the project name."""
    project = _make_project(tmp_path)
    (tmp_path / "AGENTS.md").write_text("# Something Else\n\nReal project context.\n", "utf-8")
    assert _check_agents_md_identity(project).status == "ok"


def test_registry_paths_flags_missing_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    reg = tmp_path / "registry.json"
    reg.write_text(
        json.dumps(
            {
                "version": 1,
                "projects": {
                    "gone": {
                        "slug": "gone",
                        "name": "gone",
                        "path": "/no/such/dir",
                        "last_active_at": 0.0,
                    },
                    "here": {
                        "slug": "here",
                        "name": "here",
                        "path": str(tmp_path),
                        "last_active_at": 0.0,
                    },
                },
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("VELES_REGISTRY_PATH", str(reg))
    result = _check_registry_paths(None)
    assert result.status == "warn"
    assert result.details["dead_slugs"] == ["gone"]


def test_registry_paths_ok_when_all_exist(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    reg = tmp_path / "registry.json"
    reg.write_text(
        json.dumps(
            {
                "version": 1,
                "projects": {
                    "here": {
                        "slug": "here",
                        "name": "here",
                        "path": str(tmp_path),
                        "last_active_at": 0.0,
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("VELES_REGISTRY_PATH", str(reg))
    assert _check_registry_paths(None).status == "ok"


# ---- M231: is semantic insight recall actually on? ---------------------------
#
# M192 routes the recall query and the insight backfill through a **local**
# embedder only — project text must never reach a cloud one. Autodetect still
# falls back to a cloud adapter whenever an API key is set, and that adapter
# fails the local gate. So the common setup (API key, no Ollama) got keyword-only
# recall with no signal anywhere. These three states are that signal.


class _FakeAdapter:
    """Minimal stand-in for the EmbeddingAdapter protocol."""

    dim = 8

    def __init__(self, name: str, *, is_local: bool) -> None:
        self.name = name
        self.is_local = is_local

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [[0.0] * self.dim for _ in texts]


@pytest.fixture(autouse=True)
def _offline_embedding_autodetect(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Keep every doctor test hermetic and deterministic.

    `run_all` now includes the embedding check, and autodetect probes
    `localhost:11434` — a real HTTP call whose answer depends on whether the
    developer happens to be running Ollama. Patched on
    `embedding_autodetect`, not on the defining modules: autodetect binds both
    names with a module-level `from ... import`, so patching the origin would
    not affect the already-bound reference.
    """
    from veles.modules.embedding import reset_embedding_adapter

    monkeypatch.setattr("veles.modules.embedding_autodetect.probe_ollama", lambda *_a, **_k: False)
    monkeypatch.setattr("veles.modules.embedding_autodetect.build_from_env", lambda *_a: None)
    reset_embedding_adapter()
    yield
    reset_embedding_adapter()


def test_embedding_backend_ok_with_a_local_adapter() -> None:
    from veles.modules.embedding import register_embedding_adapter

    register_embedding_adapter(cast(Any, _FakeAdapter("ollama:nomic-embed-text", is_local=True)))
    result = _check_embedding_backend()
    assert result.status == "ok"
    assert result.details["local"] is True


def test_embedding_backend_warns_when_only_a_cloud_adapter_exists() -> None:
    """The regression this check exists for: an API key is NOT enough.

    M192 accepts an on-device embedder only, so a cloud adapter leaves insight
    recall keyword-only — while being present enough to look configured.
    """
    from veles.modules.embedding import register_embedding_adapter

    register_embedding_adapter(
        cast(Any, _FakeAdapter("openai:text-embedding-3-small", is_local=False))
    )
    result = _check_embedding_backend()
    assert result.status == "warn"
    assert result.details["local"] is False
    assert "cloud" in result.message
    assert "ollama" in result.fix_hint.lower()


def test_embedding_backend_warns_when_nothing_is_detected() -> None:
    result = _check_embedding_backend()
    assert result.status == "warn"
    assert result.details["local"] is False


def test_embedding_backend_check_runs_in_the_full_report() -> None:
    names = {r.name for r in run_all(None).results}
    assert "embedding_backend" in names

"""M204 Phase 2: structured job kinds in the jobs stack.

A background op (recursive wiki ingest) is a STRUCTURED job — `kind="ingest"`
with machine-readable `params` — dispatched by `JobRunner` straight to the
kernel, never re-interpreted by an LLM turn (audit M5: a user-facing "I'll
report back" promise must not depend on a model paraphrasing a prompt into a
tool call). `kind="prompt"` jobs behave exactly as before.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from veles.core.job_runner import JobRunner
from veles.core.jobs_store import JobsStore


def _mem_store() -> JobsStore:
    return JobsStore(":memory:")


# ---- store: kind + params persist ----


def test_add_job_defaults_to_prompt_kind() -> None:
    s = _mem_store()
    rec = s.add_job(name="n", prompt="p", schedule_expr="once:+0s")
    assert rec.kind == "prompt"
    assert rec.params is None


def test_add_job_persists_structured_kind_and_params() -> None:
    s = _mem_store()
    rec = s.add_job(
        name="ingest docs",
        prompt="",  # structured kinds need no prompt
        schedule_expr="once:+0s",
        kind="ingest",
        params={"source": "/v/docs", "glob": "*.md", "resume_depth": 0},
        deliver_to="telegram:12345",
    )
    got = s.get_job(rec.id)
    assert got is not None
    assert got.kind == "ingest"
    assert got.params == {"source": "/v/docs", "glob": "*.md", "resume_depth": 0}
    assert got.deliver_to == "telegram:12345"


def test_prompt_kind_still_requires_prompt() -> None:
    s = _mem_store()
    try:
        s.add_job(name="n", prompt="", schedule_expr="once:+0s")
        raise AssertionError("empty prompt for kind=prompt must raise")
    except ValueError:
        pass


def test_kind_survives_existing_v3_database(tmp_path: Path) -> None:
    """A pre-M204 database (no kind/params columns) upgrades in place."""
    import sqlite3

    db = tmp_path / "memory.db"
    # Build a v3-era jobs table (no kind/params_json).
    conn = sqlite3.connect(db)
    conn.executescript(
        """
        CREATE TABLE jobs (
            id TEXT PRIMARY KEY, name TEXT NOT NULL, prompt TEXT NOT NULL,
            schedule_kind TEXT NOT NULL, schedule_expr TEXT NOT NULL,
            schedule_meta_json TEXT, repeat_times INTEGER,
            repeat_completed INTEGER NOT NULL DEFAULT 0, context_from TEXT,
            deliver_to TEXT, enabled INTEGER NOT NULL DEFAULT 1,
            state TEXT NOT NULL DEFAULT 'scheduled', created_at REAL NOT NULL,
            next_run_at REAL NOT NULL, last_run_at REAL, last_status TEXT,
            last_error TEXT, last_output_path TEXT
        );
        CREATE TABLE job_runs (
            run_id TEXT PRIMARY KEY, job_id TEXT NOT NULL, started_at REAL NOT NULL,
            finished_at REAL, status TEXT NOT NULL, iterations INTEGER,
            output_path TEXT, error TEXT
        );
        PRAGMA user_version = 3;
        """
    )
    conn.execute(
        "INSERT INTO jobs (id,name,prompt,schedule_kind,schedule_expr,created_at,next_run_at)"
        " VALUES ('job-x','old','say hi','interval','30m',0,0)"
    )
    conn.commit()
    conn.close()

    s = JobsStore(db)
    old = s.get_job("job-x")
    assert old is not None and old.kind == "prompt" and old.params is None
    new = s.add_job(name="i", prompt="", schedule_expr="once:+0s", kind="ingest", params={"a": 1})
    assert s.get_job(new.id).params == {"a": 1}  # type: ignore[union-attr]


# ---- runner: kind dispatch ----


class _NoAgentFactory:
    def __call__(self, session_id):  # pragma: no cover - must not be called
        raise AssertionError("structured kinds must NOT build an LLM job agent")


def test_runner_dispatches_structured_kind_to_handler(tmp_path: Path) -> None:
    s = _mem_store()
    rec = s.add_job(
        name="ingest docs",
        prompt="",
        schedule_expr="once:+0s",
        kind="ingest",
        params={"source": "/v/docs", "glob": "*"},
    )
    seen: dict = {}

    def ingest_handler(job) -> str:
        seen["params"] = job.params
        return "Ingested 3/3 file(s) into the wiki."

    finished: list[tuple[str, str]] = []

    async def on_op_finished(job, summary: str) -> None:
        finished.append((job.id, summary))

    runner = JobRunner(
        store=s,
        agent_factory=_NoAgentFactory(),
        output_root=tmp_path / "jobs",
        kind_handlers={"ingest": ingest_handler},
        on_op_finished=on_op_finished,
    )
    summaries = asyncio.run(runner._tick_once(rec.next_run_at + 1))
    assert len(summaries) == 1 and summaries[0].status == "ok"
    assert seen["params"] == {"source": "/v/docs", "glob": "*"}
    assert finished and finished[0][0] == rec.id and "3/3" in finished[0][1]
    # Output written like any job run.
    out = s.get_job(rec.id)
    assert out is not None and out.last_status == "ok" and out.last_output_path


def test_runner_unknown_kind_is_an_error_not_a_crash(tmp_path: Path) -> None:
    s = _mem_store()
    rec = s.add_job(name="x", prompt="", schedule_expr="once:+0s", kind="mystery", params={})
    runner = JobRunner(store=s, agent_factory=_NoAgentFactory(), output_root=tmp_path / "jobs")
    summaries = asyncio.run(runner._tick_once(rec.next_run_at + 1))
    assert summaries[0].status == "error"
    assert "mystery" in (summaries[0].error or "")

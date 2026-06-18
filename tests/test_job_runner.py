"""M75 — JobRunner: tick spawns due jobs, writes output, advances schedule."""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from veles.core.job_runner import JobRunner
from veles.core.jobs_store import JobsStore


class _StubResult:
    def __init__(self, text: str = "OK", iterations: int = 1) -> None:
        self.text = text
        self.iterations = iterations


class _StubAgent:
    def __init__(self, *, text: str = "OK", raise_exc: Exception | None = None) -> None:
        self._text = text
        self._raise = raise_exc
        self.prompts: list[str] = []

    def run(self, prompt: str) -> _StubResult:
        self.prompts.append(prompt)
        if self._raise:
            raise self._raise
        return _StubResult(text=self._text)


def _make_factory(*, text: str = "OK", raise_exc: Exception | None = None):
    last: list[_StubAgent] = []

    def factory(_session_id):
        a = _StubAgent(text=text, raise_exc=raise_exc)
        last.append(a)
        return a

    return factory, last


@pytest.fixture()
def store():
    s = JobsStore(":memory:")
    yield s
    s.close()


@pytest.fixture()
def output_root(tmp_path: Path) -> Path:
    return tmp_path / "jobs-out"


async def test_tick_writes_output_and_advances_interval(
    store: JobsStore, output_root: Path
) -> None:
    factory, agents = _make_factory(text="hello world")
    runner = JobRunner(store=store, agent_factory=factory, output_root=output_root)
    rec = store.add_job(name="t", prompt="say hi", schedule_expr="30m", now=100)
    summaries = await runner._tick_once(200_000.0)
    assert len(summaries) == 1
    s = summaries[0]
    assert s.status == "ok"
    assert s.output_path is not None
    out = Path(s.output_path).read_text(encoding="utf-8")
    assert "hello world" in out
    assert "say hi" in out  # prompt embedded
    # next_run_at advanced
    refreshed = store.get_job(rec.id)
    assert refreshed.next_run_at > 200_000.0
    assert refreshed.last_status == "ok"
    assert refreshed.repeat_completed == 1
    # exactly one Agent constructed
    assert len(agents) == 1


async def test_tick_handles_agent_exception(store: JobsStore, output_root: Path) -> None:
    factory, _ = _make_factory(raise_exc=RuntimeError("boom"))
    runner = JobRunner(store=store, agent_factory=factory, output_root=output_root)
    rec = store.add_job(name="t", prompt="x", schedule_expr="30m", now=100)
    summaries = await runner._tick_once(200_000.0)
    assert summaries[0].status == "error"
    assert "boom" in (summaries[0].error or "")
    refreshed = store.get_job(rec.id)
    assert refreshed.last_status == "error"


async def test_context_from_prefixes_prompt(store: JobsStore, output_root: Path) -> None:
    factory, agents = _make_factory(text="first output text")
    runner = JobRunner(store=store, agent_factory=factory, output_root=output_root)
    # First job
    parent = store.add_job(name="p", prompt="generate report", schedule_expr="30m", now=100)
    await runner._tick_once(200_000.0)
    # Second job consumes parent's output
    store.add_job(
        name="child",
        prompt="rephrase",
        schedule_expr="30m",
        context_from=parent.id,
        now=100,
    )
    agents.clear()
    await runner._tick_once(200_000.0)
    # The 'child' run is the only one due at 200_000 (parent's next_run advanced)
    # but parent could also be due if its schedule cycled. Filter by name.
    child_prompts = [a.prompts[0] for a in agents]
    assert any("<context_from" in p for p in child_prompts)
    assert any("first output text" in p for p in child_prompts)


async def test_once_schedule_marks_done(store: JobsStore, output_root: Path) -> None:
    factory, _ = _make_factory(text="bye")
    runner = JobRunner(store=store, agent_factory=factory, output_root=output_root)
    rec = store.add_job(
        name="reminder",
        prompt="ping me",
        schedule_expr="2020-01-01T00:00:00Z",  # in the past → due immediately
        now=100,
    )
    summaries = await runner._tick_once(time.time())
    assert summaries[0].status == "ok"
    refreshed = store.get_job(rec.id)
    assert refreshed.state == "done"
    assert refreshed.enabled is False


async def test_repeat_times_marks_done_after_n(store: JobsStore, output_root: Path) -> None:
    factory, _ = _make_factory()
    runner = JobRunner(store=store, agent_factory=factory, output_root=output_root)
    rec = store.add_job(
        name="thrice",
        prompt="x",
        schedule_expr="1s",
        repeat_times=2,
        now=100,
    )
    # First tick — one run
    await runner._tick_once(200.0)
    assert store.get_job(rec.id).state == "scheduled"
    # Second tick — last run, should mark done
    await runner._tick_once(400.0)
    assert store.get_job(rec.id).state == "done"


async def test_deliver_to_pushes_output_via_router(store: JobsStore, output_root: Path) -> None:
    """M165: a due job with `deliver_to` set hands its output to the
    DeliveryRouter, which dispatches to the registered platform deliverer.
    This is the production push path (runner → router → gateway.deliver)."""
    from veles.channels.delivery import DeliveryRouter

    seen: list[tuple[str, str, str | None]] = []

    async def fake_telegram(chat_id: str, text: str, thread_id: str | None) -> None:
        seen.append((chat_id, text, thread_id))

    router = DeliveryRouter()
    router.register_deliverer("telegram", fake_telegram)

    factory, _ = _make_factory(text="DB looks healthy")
    runner = JobRunner(
        store=store,
        agent_factory=factory,
        output_root=output_root,
        delivery_router=router,
    )
    store.add_job(
        name="monitor",
        prompt="check db",
        schedule_expr="30m",
        deliver_to="telegram:42",
        now=100,
    )
    summaries = await runner._tick_once(200_000.0)

    assert summaries[0].status == "ok"
    assert seen == [("42", "DB looks healthy", None)]


async def test_no_deliver_to_skips_router(store: JobsStore, output_root: Path) -> None:
    """A job without `deliver_to` never touches the router."""
    from veles.channels.delivery import DeliveryRouter

    seen: list[str] = []

    async def fake(chat_id: str, text: str, thread_id: str | None) -> None:
        seen.append(text)

    router = DeliveryRouter()
    router.register_deliverer("telegram", fake)

    factory, _ = _make_factory(text="out")
    runner = JobRunner(
        store=store,
        agent_factory=factory,
        output_root=output_root,
        delivery_router=router,
    )
    store.add_job(name="silent", prompt="x", schedule_expr="30m", now=100)
    await runner._tick_once(200_000.0)
    assert seen == []


async def test_delivery_failure_does_not_break_run(store: JobsStore, output_root: Path) -> None:
    """A broken deliverer is best-effort: the run still completes 'ok' and
    the schedule advances — a dead Telegram bot can't wedge a schedule."""
    from veles.channels.delivery import DeliveryRouter

    async def boom(chat_id: str, text: str, thread_id: str | None) -> None:
        raise RuntimeError("telegram down")

    router = DeliveryRouter()
    router.register_deliverer("telegram", boom)

    factory, _ = _make_factory(text="out")
    runner = JobRunner(
        store=store,
        agent_factory=factory,
        output_root=output_root,
        delivery_router=router,
    )
    rec = store.add_job(name="m", prompt="x", schedule_expr="30m", deliver_to="telegram:9", now=100)
    summaries = await runner._tick_once(200_000.0)
    assert summaries[0].status == "ok"
    refreshed = store.get_job(rec.id)
    assert refreshed.last_status == "ok"
    assert refreshed.next_run_at > 200_000.0  # schedule still advanced


async def test_status_returns_dict(store: JobsStore, output_root: Path) -> None:
    factory, _ = _make_factory()
    runner = JobRunner(store=store, agent_factory=factory, output_root=output_root)
    s = runner.status()
    assert s["enabled"] is False  # not started yet
    assert "inflight" in s

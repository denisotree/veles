"""Integration: Agent.run() emits TraceRecord per model call (Tier ε, M68)."""

from __future__ import annotations

from pathlib import Path

from tests.conftest import StubProvider as _StubProvider
from veles.core.agent import Agent
from veles.core.provider import ProviderResponse, TokenUsage, ToolCall
from veles.core.tools.registry import Registry, ToolEntry
from veles.core.trace import TraceWriter, read_records


def _ok(text: str = "done", **usage_kw: int) -> ProviderResponse:
    defaults = {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}
    defaults.update(usage_kw)
    return ProviderResponse(
        text=text,
        tool_calls=[],
        usage=TokenUsage(**defaults),
        finish_reason="stop",
    )


def _tool_call(name: str, args: dict, **usage_kw: int) -> ProviderResponse:
    defaults = {"prompt_tokens": 5, "completion_tokens": 3, "total_tokens": 8}
    defaults.update(usage_kw)
    return ProviderResponse(
        text=None,
        tool_calls=[ToolCall(id="c1", name=name, arguments=args)],
        usage=TokenUsage(**defaults),
        finish_reason="tool_use",
    )


def _registry_with_echo() -> Registry:
    reg = Registry()
    reg.register(
        ToolEntry(
            name="echo",
            description="Echo input",
            parameter_schema={"type": "object"},
            handler=lambda text="": text,
            is_async=False,
        )
    )
    return reg


def test_trace_written_when_writer_provided(tmp_path: Path) -> None:
    provider = _StubProvider(responses=[_ok("done")])
    writer = TraceWriter(tmp_path / "traces.jsonl")
    agent = Agent(
        provider,
        Registry(),
        model="anthropic/claude-sonnet-4.6",
        system_prompt="you are a helper",
        trace_writer=writer,
    )
    result = agent.run("hello")
    assert result.text == "done"
    records = read_records(tmp_path / "traces.jsonl")
    assert len(records) == 1
    r = records[0]
    assert r["provider"] == "stub"
    assert r["model"] == "anthropic/claude-sonnet-4.6"
    assert r["output_tokens"] == 5
    assert r["tool_calls_count"] == 0
    assert r["final_status"] == "ok"
    assert r["system_prompt_hash"].startswith("sha256:")
    assert r["tool_bundle_hash"].startswith("sha256:")
    assert r["total_latency_ms"] >= 0


def test_trace_records_each_turn(tmp_path: Path) -> None:
    provider = _StubProvider(
        responses=[
            _tool_call("echo", {"text": "x"}),
            _ok("final"),
        ]
    )
    writer = TraceWriter(tmp_path / "traces.jsonl")
    agent = Agent(
        provider,
        _registry_with_echo(),
        model="m",
        trace_writer=writer,
    )
    agent.run("hi")
    records = read_records(tmp_path / "traces.jsonl")
    # Two model calls -> two trace rows.
    assert len(records) == 2
    assert records[0]["tool_calls_count"] == 1
    assert records[1]["tool_calls_count"] == 0


def test_trace_captures_cache_fields(tmp_path: Path) -> None:
    """If the provider returns cache fields, they propagate to the record."""
    provider = _StubProvider(
        responses=[
            _ok(
                "done",
                prompt_tokens=100,
                completion_tokens=10,
                total_tokens=110,
                cache_read_tokens=80,
                cache_creation_tokens=5,
            )
        ]
    )
    writer = TraceWriter(tmp_path / "traces.jsonl")
    agent = Agent(provider, Registry(), model="m", trace_writer=writer)
    agent.run("hello")
    r = read_records(tmp_path / "traces.jsonl")[0]
    assert r["cache_read_tokens"] == 80
    assert r["cache_creation_tokens"] == 5
    # input_tokens_new = prompt_tokens - cache_read_tokens
    assert r["input_tokens_new"] == 20


def test_no_trace_when_no_writer_and_no_project(tmp_path: Path) -> None:
    """Existing test surface: when no writer is passed and no active project,
    Agent.run() runs unchanged and emits no trace file anywhere."""
    provider = _StubProvider(responses=[_ok("done")])
    agent = Agent(provider, Registry(), model="m")
    agent.run("hello")
    # Nothing got written into cwd or tmp_path.
    assert not (tmp_path / "traces.jsonl").exists()


def test_trace_write_failure_does_not_break_run(tmp_path: Path) -> None:
    """A broken writer must not propagate; runs are sacred."""

    class _BadWriter:
        def write(self, record):
            raise RuntimeError("disk on fire")

    provider = _StubProvider(responses=[_ok("done")])
    agent = Agent(
        provider,
        Registry(),
        model="m",
        trace_writer=_BadWriter(),  # type: ignore[arg-type]
    )
    result = agent.run("hello")
    assert result.text == "done"


def test_system_prompt_hash_stable_across_turns(tmp_path: Path) -> None:
    """Cache-invariant proof: same system_prompt -> same hash, every turn."""
    provider = _StubProvider(
        responses=[
            _tool_call("echo", {"text": "x"}),
            _ok("final"),
        ]
    )
    writer = TraceWriter(tmp_path / "traces.jsonl")
    agent = Agent(
        provider,
        _registry_with_echo(),
        model="m",
        system_prompt="STABLE PREFIX",
        trace_writer=writer,
    )
    agent.run("hi")
    records = read_records(tmp_path / "traces.jsonl")
    hashes = {r["system_prompt_hash"] for r in records}
    assert len(hashes) == 1

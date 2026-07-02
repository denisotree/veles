"""`delegate` — the model-callable decompose → scoped worker → integrate primitive.

A capable root delegates a small subtask to a fresh sub-agent with a narrow
toolset; the worker runs to completion and its report comes back. Tested with a
stub SubagentFactory (no provider/network): we assert the worker receives the
right scoped tools + system prompt, the report flows back, unknown tools are
dropped, the read-only default applies, depth is capped, and it degrades
cleanly with no factory installed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from veles.core.orchestration.delegation import (
    MAX_DELEGATE_DEPTH,
    reset_subagent_factory,
    set_subagent_factory,
)
from veles.core.tools.builtin.delegate import delegate
from veles.core.tools.registry import registry


@dataclass
class _StubAgent:
    """Records what the factory handed it; its run() returns a canned report."""

    system_prompt: str
    tools: list[str]
    report: str = "did the thing; wrote wiki/concepts/x.md"

    def run(self, prompt: str, **_kw: Any):
        self.seen_prompt = prompt

        @dataclass
        class _RR:
            text: str
            session_id: str | None = "w1"
            usage: Any = None

        return _RR(text=self.report)


@dataclass
class _Recorder:
    built: list[_StubAgent] = field(default_factory=list)

    def factory(self, *, system_prompt: str, tools: list[str]) -> _StubAgent:
        a = _StubAgent(system_prompt=system_prompt, tools=tools)
        self.built.append(a)
        return a


def _with_factory(rec: _Recorder):
    return set_subagent_factory(rec.factory)


def test_delegate_runs_worker_with_scoped_tools_and_returns_report() -> None:
    rec = _Recorder()
    tok = _with_factory(rec)
    try:
        out = delegate(
            "Summarise wiki/concepts/x.md",
            tools=["read_file", "write_file"],
            context="target: wiki/concepts/",
        )
    finally:
        reset_subagent_factory(tok)

    assert "did the thing" in out
    assert len(rec.built) == 1
    worker = rec.built[0]
    assert worker.tools == ["read_file", "write_file"]  # exactly the scoped set
    assert worker.seen_prompt == "Summarise wiki/concepts/x.md"
    assert "focused sub-agent" in worker.system_prompt  # the worker frame
    assert "target: wiki/concepts/" in worker.system_prompt  # context embedded


def test_delegate_defaults_to_readonly_tools() -> None:
    rec = _Recorder()
    tok = _with_factory(rec)
    try:
        delegate("Look at the tree")  # no tools → read-only default
    finally:
        reset_subagent_factory(tok)
    worker = rec.built[0]
    assert "read_file" in worker.tools
    assert "write_file" not in worker.tools and "delete_file" not in worker.tools


def test_delegate_drops_unknown_tools() -> None:
    rec = _Recorder()
    tok = _with_factory(rec)
    try:
        out = delegate("x", tools=["read_file", "no_such_tool"])
    finally:
        reset_subagent_factory(tok)
    assert rec.built[0].tools == ["read_file"]  # unknown dropped
    assert "no_such_tool" in out  # reported


def test_delegate_all_tools_unknown_is_an_error() -> None:
    rec = _Recorder()
    tok = _with_factory(rec)
    try:
        out = delegate("x", tools=["bogus1", "bogus2"])
    finally:
        reset_subagent_factory(tok)
    assert out.startswith("<error:")
    assert rec.built == []  # never spawned


def test_delegate_without_factory_degrades() -> None:
    # No factory installed (headless / non-run context) → clean error, no crash.
    assert delegate("x", tools=["read_file"]).startswith("<error:")


def test_delegate_depth_cap() -> None:
    from veles.core.orchestration import delegation

    rec = _Recorder()
    tok = _with_factory(rec)
    dtok = delegation._depth.set(MAX_DELEGATE_DEPTH)  # simulate being nested deep
    try:
        out = delegate("x", tools=["read_file"])
    finally:
        delegation._depth.reset(dtok)
        reset_subagent_factory(tok)
    assert "max delegation depth" in out
    assert rec.built == []  # refused before spawning


def test_delegate_registered_and_in_run_toolset() -> None:
    from veles.core.tools.toolsets import TOOLSETS

    assert registry.get("delegate") is not None
    assert "delegate" in TOOLSETS["run"]

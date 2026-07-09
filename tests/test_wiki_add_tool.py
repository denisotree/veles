"""M204 Phase 1: the agent-callable `wiki_add` tool (inline path).

`veles add` as a TOOL: the agent inside a turn ingests a file — or a whole
directory — through the same kernel loop the CLI uses, spawning a FRESH
per-file sub-agent (clean context; no more one-giant-context migrations).
Inline-only here; the daemon/background path is Phase 2.

Contract under test:
- one sub-agent per file, sequential, via `current_subagent_factory()`;
- sub-agents get ingest-scoped tools; never `wiki_add` itself (no recursion),
  never `run_shell`/`fetch_url` (B1 — ingested content is untrusted);
- no factory installed → a helpful error string, not a crash;
- toolset membership: `wiki_add` in [engine-wiki], [run], [ingest].
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest

from veles.core.orchestration.delegation import (
    reset_subagent_factory,
    set_subagent_factory,
)
from veles.modules.wiki.tools import wiki_add


@dataclass
class _StubAgent:
    system_prompt: str
    tools: list[str]

    def run(self, prompt: str, **_kw: Any):
        self.seen_prompt = prompt

        @dataclass
        class _RR:
            text: str
            session_id: str | None = "w1"
            usage: Any = None

        return _RR(text="ingested; wrote wiki/concepts/x.md")


@dataclass
class _Recorder:
    built: list[_StubAgent] = field(default_factory=list)

    def factory(self, *, system_prompt: str, tools: list[str]) -> _StubAgent:
        a = _StubAgent(system_prompt=system_prompt, tools=list(tools))
        self.built.append(a)
        return a


@pytest.fixture
def rec():
    r = _Recorder()
    tok = set_subagent_factory(r.factory)
    try:
        yield r
    finally:
        reset_subagent_factory(tok)


def test_no_factory_returns_helpful_error(tmp_path: Path) -> None:
    f = tmp_path / "a.md"
    f.write_text("x", encoding="utf-8")
    out = wiki_add(str(f))
    assert out.startswith("<error") and "wiki_add" in out


def test_single_file_spawns_one_ingest_worker(rec: _Recorder, tmp_path: Path) -> None:
    f = tmp_path / "a.md"
    f.write_text("x", encoding="utf-8")
    out = wiki_add(str(f))
    assert len(rec.built) == 1
    worker = rec.built[0]
    assert str(f) in worker.seen_prompt  # the per-file ingest user turn
    assert "topic" in worker.seen_prompt.lower()  # content-aware directive rides along
    assert "1/1" in out or "1" in out  # success report


def test_recursive_spawns_one_worker_per_file_in_order(rec: _Recorder, tmp_path: Path) -> None:
    (tmp_path / "b.md").write_text("b", encoding="utf-8")
    (tmp_path / "a.md").write_text("a", encoding="utf-8")
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "x.md").write_text("x", encoding="utf-8")

    out = wiki_add(str(tmp_path), recursive=True, glob="*.md")
    assert len(rec.built) == 2  # dot-dir skipped
    seen = [w.seen_prompt for w in rec.built]
    assert "a.md" in seen[0] and "b.md" in seen[1]  # sorted, sequential
    assert "2" in out  # summary counts


def test_worker_tools_are_ingest_scoped_no_recursion_no_egress(
    rec: _Recorder, tmp_path: Path
) -> None:
    f = tmp_path / "a.md"
    f.write_text("x", encoding="utf-8")
    wiki_add(str(f))
    tools = set(rec.built[0].tools)
    assert "wiki_write_page" in tools  # can actually write pages
    assert "wiki_add" not in tools  # no self-recursion
    assert "run_shell" not in tools and "fetch_url" not in tools  # B1
    assert "delegate" not in tools  # a per-file worker doesn't sub-delegate


def test_recursive_on_missing_dir_errors(rec: _Recorder, tmp_path: Path) -> None:
    out = wiki_add(str(tmp_path / "nope"), recursive=True)
    assert out.startswith("<error")
    assert rec.built == []


def test_toolset_membership() -> None:
    from veles.core.tools.toolsets import TOOLSETS

    assert "wiki_add" in TOOLSETS["engine-wiki"]
    assert "wiki_add" in TOOLSETS["run"]
    assert "wiki_add" in TOOLSETS["ingest"]

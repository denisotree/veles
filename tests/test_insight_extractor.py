"""M31 — heuristic-driven insight extraction from completed sessions.

Pure-detection tests cover the EN/RU keyword regex and the tool-error
pairing logic. The closure factory test verifies wiki write + LOG
append happen on a remember-trigger when the sub-agent emits a
well-formed slug + body, and that a `SKIP` reply is silently dropped.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from veles.core.insight_extractor import (
    _parse_extractor_output,
    find_recovery_triggers,
    find_remember_triggers,
    make_insight_extractor,
)
from veles.core.project import init_project
from veles.core.provider import (
    Message,
    ProviderResponse,
    TokenUsage,
    ToolCall,
)
from veles.core.wiki import Wiki

# ---- find_remember_triggers ----


def test_remember_trigger_matches_english_keyword() -> None:
    h = [Message(role="user", content="Please remember to use ruff before commit.")]
    out = find_remember_triggers(h)
    assert len(out) == 1
    assert out[0].user_idx == 0


def test_remember_trigger_matches_russian_keyword() -> None:
    h = [Message(role="user", content="запомни: не делай git push --force на main")]
    out = find_remember_triggers(h)
    assert len(out) == 1


def test_remember_trigger_skips_assistant_messages() -> None:
    h = [
        Message(role="user", content="hello"),
        Message(role="assistant", content="I will remember this for next time."),
    ]
    assert find_remember_triggers(h) == []


def test_remember_trigger_passthrough_when_no_keyword() -> None:
    h = [
        Message(role="user", content="What's the weather?"),
        Message(role="assistant", content="Sunny."),
    ]
    assert find_remember_triggers(h) == []


def test_remember_trigger_is_case_insensitive() -> None:
    h = [Message(role="user", content="REMEMBER this is important")]
    assert len(find_remember_triggers(h)) == 1


# ---- find_recovery_triggers ----


def test_recovery_trigger_pairs_error_with_window() -> None:
    fail_call = ToolCall(id="c1", name="x", arguments={})
    h = [
        Message(role="system", content="sys"),
        Message(role="user", content="run it"),
        Message(role="assistant", content=None, tool_calls=[fail_call]),
        Message(role="tool", content="<error: ValueError: nope>", tool_call_id="c1"),
        Message(role="assistant", content="Sorry, retrying with valid input."),
    ]
    out = find_recovery_triggers(h)
    assert len(out) == 1
    trig = out[0]
    assert trig.error_idx == 3
    assert trig.window_start == 0
    assert trig.window_end == len(h)


def test_recovery_trigger_collapses_consecutive_errors() -> None:
    fail_call = ToolCall(id="c1", name="x", arguments={})
    h = [
        Message(role="user", content="run"),
        Message(role="assistant", content=None, tool_calls=[fail_call]),
        Message(role="tool", content="<error: A>", tool_call_id="c1"),
        Message(role="tool", content="<error: B>", tool_call_id="c2"),
    ]
    # Two adjacent error tool messages → only the first is emitted.
    out = find_recovery_triggers(h)
    assert len(out) == 1
    assert out[0].error_idx == 2


def test_recovery_trigger_ignores_non_error_tool_messages() -> None:
    h = [
        Message(role="user", content="ok"),
        Message(role="tool", content="result", tool_call_id="c1"),
    ]
    assert find_recovery_triggers(h) == []


def test_recovery_trigger_emits_two_when_separated() -> None:
    h = [
        Message(role="user", content="run"),
        Message(role="tool", content="<error: A>", tool_call_id="c1"),
        Message(role="assistant", content="ok"),
        Message(role="user", content="next"),
        Message(role="tool", content="<error: B>", tool_call_id="c2"),
    ]
    out = find_recovery_triggers(h)
    assert len(out) == 2


# ---- _parse_extractor_output ----


def test_parse_extractor_output_skip_returns_none() -> None:
    assert _parse_extractor_output("SKIP") is None
    assert _parse_extractor_output("  skip  ") is None


def test_parse_extractor_output_returns_slug_and_body() -> None:
    parsed = _parse_extractor_output(
        "use-ruff-before-commit\n\n# Use ruff before commit\n\nAlways run `ruff check`."
    )
    assert parsed is not None
    slug, body = parsed
    assert slug == "use-ruff-before-commit"
    assert body.startswith("# Use ruff before commit")


def test_parse_extractor_output_normalises_slug() -> None:
    parsed = _parse_extractor_output("Use Ruff Before Commit\n\nbody")
    assert parsed is not None
    assert parsed[0] == "use-ruff-before-commit"


def test_parse_extractor_output_rejects_empty_body() -> None:
    assert _parse_extractor_output("just-a-slug\n\n   ") is None


def test_parse_extractor_output_rejects_single_line() -> None:
    assert _parse_extractor_output("just-a-line") is None


# ---- Integration: closure factory writes wiki page on real trigger ----


@dataclass
class _ScriptedProvider:
    """Replays a queue of ProviderResponses for sub-Agent calls."""

    name: str = "stub"
    supports_tools: bool = False
    responses: list[ProviderResponse] = field(default_factory=list)
    _idx: int = 0

    def create_message(self, messages, tools=None, *, model: str, max_tokens: int = 4096):
        resp = self.responses[self._idx]
        self._idx += 1
        return resp


def _resp(text: str) -> ProviderResponse:
    return ProviderResponse(
        text=text,
        tool_calls=[],
        usage=TokenUsage(prompt_tokens=10, completion_tokens=10, total_tokens=20),
        finish_reason="stop",
    )


def test_extractor_writes_wiki_page_on_remember_trigger(tmp_path: Path) -> None:
    project = init_project(tmp_path, name="t")
    provider = _ScriptedProvider(
        responses=[_resp("ruff-before-commit\n\n# Ruff before commit\n\nAlways run ruff.")]
    )
    extractor = make_insight_extractor(provider=provider, model="m", project=project)

    history = [
        Message(role="user", content="запомни запускать ruff перед коммитом"),
        Message(role="assistant", content="ok, will do."),
    ]
    written = extractor(history, "session-abc")
    assert written == 1

    pages = Wiki(project.wiki_root).list_pages()
    insights = [p for p in pages if p.category == "insights"]
    assert len(insights) == 1
    assert "ruff-before-commit" in insights[0].slug


def test_extractor_silently_drops_skip_response(tmp_path: Path) -> None:
    project = init_project(tmp_path, name="t")
    provider = _ScriptedProvider(responses=[_resp("SKIP")])
    extractor = make_insight_extractor(provider=provider, model="m", project=project)
    history = [Message(role="user", content="remember this trivial fact")]
    written = extractor(history, "s1")
    assert written == 0
    pages = Wiki(project.wiki_root).list_pages()
    assert [p for p in pages if p.category == "insights"] == []


def test_extractor_no_triggers_returns_zero_without_llm_call(tmp_path: Path) -> None:
    project = init_project(tmp_path, name="t")
    provider = _ScriptedProvider(responses=[])  # would IndexError if called
    extractor = make_insight_extractor(provider=provider, model="m", project=project)
    history = [
        Message(role="user", content="What's the weather?"),
        Message(role="assistant", content="Sunny."),
    ]
    assert extractor(history, "s1") == 0


def test_extractor_writes_log_entry_on_success(tmp_path: Path) -> None:
    project = init_project(tmp_path, name="t")
    provider = _ScriptedProvider(
        responses=[_resp("avoid-force-push\n\n# Avoid force push\n\nNever force push to main.")]
    )
    extractor = make_insight_extractor(provider=provider, model="m", project=project)
    history = [Message(role="user", content="never force push to main")]
    extractor(history, "s2")

    log_path = project.wiki_root / "LOG.md"
    assert log_path.is_file()
    log = log_path.read_text(encoding="utf-8")
    assert "insight" in log
    assert "remember-trigger" in log

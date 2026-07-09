"""Real token usage in the live HUD (`≈N tok`).

Live report: a tool-call-heavy turn showed `≈0 tok · 56 tool(s)` — the HUD
estimated output tokens as `stream_chars // 4`, and a turn that only emits
tool calls streams no text at all. The fix: the agent emits a `round_usage`
event after every provider round (real usage from the response), the REPL maps
it into the HUD, and the HUD displays the real cumulative count — the text
estimate remains only as a live lower bound while a round is still streaming.
"""

from __future__ import annotations

from dataclasses import dataclass

from veles.core.agent import Agent
from veles.core.provider import ProviderResponse, TokenUsage, ToolCall
from veles.core.tools.registry import Registry, ToolEntry


def _usage(total: int) -> TokenUsage:
    return TokenUsage(prompt_tokens=total - 10, completion_tokens=10, total_tokens=total)


@dataclass
class _ToolThenAnswerProvider:
    name: str = "stub"
    supports_tools: bool = True
    supports_streaming: bool = False
    n: int = 0

    def create_message(self, messages, tools=None, *, model, max_tokens=4096):
        del messages, model, max_tokens
        self.n += 1
        if tools and self.n == 1:
            return ProviderResponse(
                text=None,
                tool_calls=[ToolCall(id="c1", name="noop", arguments={})],
                usage=_usage(100),
                finish_reason="tool_use",
            )
        return ProviderResponse(text="done", tool_calls=[], usage=_usage(50), finish_reason="stop")


def _registry() -> Registry:
    reg = Registry()
    reg.register(
        ToolEntry(
            name="noop",
            description="",
            parameter_schema={"type": "object"},
            handler=lambda **_: "ok",
            is_async=False,
            sensitive=False,
        )
    )
    return reg


def test_agent_emits_round_usage_after_every_provider_round() -> None:
    events: list = []
    agent = Agent(_ToolThenAnswerProvider(), _registry(), model="m")
    agent.run("go", event_listener=events.append)

    usage_events = [e for e in events if getattr(e, "type", "") == "round_usage"]
    assert len(usage_events) == 2  # one per provider round
    assert usage_events[0].total_tokens == 100
    assert usage_events[1].total_tokens == 50
    # Cumulative climbs across the turn — this is what the HUD displays.
    assert usage_events[0].cumulative_total == 100
    assert usage_events[1].cumulative_total == 150
    assert usage_events[1].cumulative_completion == 20


def test_turn_callbacks_map_round_usage_to_meta() -> None:
    from types import SimpleNamespace

    from veles.cli.repl.terminal import _console, _resolve_theme
    from veles.cli.repl.turn import _make_turn_callbacks

    seen: list = []

    def on_meta(kind, text, **_kw):
        seen.append((kind, text))

    theme = _resolve_theme(SimpleNamespace(theme_name="everforest"))
    _post, _text, on_event, _holder, _flush = _make_turn_callbacks(
        _console(), theme, [], on_meta=on_meta
    )
    on_event(SimpleNamespace(type="round_usage", cumulative_completion=42, cumulative_total=150))
    assert ("usage", "42") in seen


def test_hud_shows_real_tokens_for_a_toolcall_only_turn(tmp_path) -> None:
    """`≈0 tok` regression: no streamed text, but real usage arrived."""
    import argparse

    from veles.cli.commands.repl import _console, _ReplApp, _resolve_theme
    from veles.cli.repl.slash import build_default_registry
    from veles.core.memory import SessionStore
    from veles.core.project import init_project
    from veles.core.session_state import AppState

    project = init_project(tmp_path / "p", name="hud")
    store = SessionStore(project.memory_db_path)
    state = AppState(session_id=None, provider_name="openrouter", model="m")
    app = _ReplApp(
        argparse.Namespace(),
        project,
        state,
        lambda *_a, **_k: None,
        store,
        build_default_registry(project=project),
        _console(),
        _resolve_theme(state),
        [],
    )
    try:
        app.busy = False
        app.stream_chars = 0  # tool-call-only turn: no text streamed
        app._push_meta("usage", "654")
        text = "".join(t for _s, t in app._meta_fragments())
        assert "≈654 tok" in text  # real usage, not 0
    finally:
        store.close()

"""M238: a repeated deterministic read blanks its own earlier result.

Read a file on turn 2, read it again on turn 9, and before M238 BOTH results
stayed in the history — the stale copy competing with the fresh one for
attention. SKILL.state (arXiv 2608.26263) measured the cost of exactly that:
after the world changes underneath the agent, history-based runtimes hallucinate
for 5-8 consecutive turns because obsolete facts in the prompt overpower
contradictory new observations.

Two dispatch paths, two mechanisms: native recovers the (tool, args) key from
`assistant.tool_calls`; fenced keeps no arguments in the history at all, so the
key is written into the chunk header at dispatch time.
"""

from __future__ import annotations

from dataclasses import dataclass

from veles.core.agent import Agent
from veles.core.fenced_tools import FENCED_RESULT_HEADER
from veles.core.history_repair import (
    call_key,
    supersede_fenced,
    supersede_native,
)
from veles.core.provider import Message, ProviderResponse, TokenUsage, ToolCall
from veles.core.tools.registry import Registry, ToolEntry

# ---------- key ----------


def test_call_key_is_stable_across_argument_order() -> None:
    assert call_key("read_file", {"path": "a", "limit": 1}) == call_key(
        "read_file", {"limit": 1, "path": "a"}
    )


def test_call_key_separates_tools_and_arguments() -> None:
    assert call_key("read_file", {"path": "a"}) != call_key("read_file", {"path": "b"})
    assert call_key("read_file", {"path": "a"}) != call_key("list_files", {"path": "a"})


def test_call_key_survives_unserialisable_arguments() -> None:
    """`default=str` — a weird argument must not raise inside the dispatch loop."""
    assert call_key("read_file", {"path": object()}).startswith("#")


# ---------- native path ----------


def _pair(cid: str, name: str, args: dict, result: str) -> list[Message]:
    return [
        Message(
            role="assistant", content=None, tool_calls=[ToolCall(id=cid, name=name, arguments=args)]
        ),
        Message(role="tool", content=result, tool_call_id=cid),
    ]


def test_native_supersedes_an_identical_earlier_read() -> None:
    history = _pair("c1", "read_file", {"path": "a.py"}, "OLD CONTENT")
    assert supersede_native(history, "read_file", {"path": "a.py"}) == 1
    assert history[1].content == "<superseded by a newer identical read_file call>"


def test_native_leaves_a_different_argument_alone() -> None:
    history = _pair("c1", "read_file", {"path": "a.py"}, "CONTENT OF A")
    assert supersede_native(history, "read_file", {"path": "b.py"}) == 0
    assert history[1].content == "CONTENT OF A"


def test_native_never_supersedes_a_nondeterministic_tool() -> None:
    """Two `run_shell` runs of one command can legitimately differ — that
    difference is often the evidence. Same for `fetch_url`."""
    for tool in ("run_shell", "fetch_url"):
        history = _pair("c1", tool, {"cmd": "pytest"}, "3 failed")
        assert supersede_native(history, tool, {"cmd": "pytest"}) == 0
        assert history[1].content == "3 failed"


def test_native_supersede_keeps_the_tool_call_pairing_intact() -> None:
    """Blanking, not deleting: dropping the message would orphan `tool_call_id`
    and force `repair_tool_pairing` to synthesise it back."""
    from veles.core.history_repair import repair_tool_pairing

    history = _pair("c1", "read_file", {"path": "a.py"}, "OLD")
    supersede_native(history, "read_file", {"path": "a.py"})
    assert repair_tool_pairing(history) is history  # already consistent
    assert history[1].tool_call_id == "c1"


def test_native_supersede_is_idempotent() -> None:
    history = _pair("c1", "read_file", {"path": "a.py"}, "OLD")
    assert supersede_native(history, "read_file", {"path": "a.py"}) == 1
    assert supersede_native(history, "read_file", {"path": "a.py"}) == 0


# ---------- fenced path ----------


def _fenced(*chunks: str) -> Message:
    return Message(role="user", content=f"{FENCED_RESULT_HEADER}\n\n" + "\n\n".join(chunks))


def test_fenced_supersedes_the_tagged_chunk_only() -> None:
    tag_a = call_key("read_file", {"path": "a.py"})
    tag_b = call_key("read_file", {"path": "b.py"})
    msg = _fenced(f"[read_file {tag_a}]\nOLD A", f"[read_file {tag_b}]\nCONTENT B")
    history = [msg]

    assert supersede_fenced(history, "read_file", tag_a, FENCED_RESULT_HEADER) == 1
    assert "OLD A" not in (msg.content or "")
    assert "CONTENT B" in (msg.content or "")
    assert f"[read_file {tag_b}]" in (msg.content or "")


def test_fenced_supersedes_a_multiline_chunk() -> None:
    tag = call_key("read_file", {"path": "a.py"})
    msg = _fenced(f"[read_file {tag}]\nline1\nline2\nline3")
    assert supersede_fenced([msg], "read_file", tag, FENCED_RESULT_HEADER) == 1
    assert "line2" not in (msg.content or "")


def test_fenced_ignores_messages_that_are_not_result_blocks() -> None:
    tag = call_key("read_file", {"path": "a.py"})
    plain = Message(role="user", content=f"[read_file {tag}]\nnot a result block")
    assert supersede_fenced([plain], "read_file", tag, FENCED_RESULT_HEADER) == 0
    assert plain.content == f"[read_file {tag}]\nnot a result block"


def test_fenced_supersede_is_idempotent() -> None:
    tag = call_key("read_file", {"path": "a.py"})
    msg = _fenced(f"[read_file {tag}]\nOLD")
    assert supersede_fenced([msg], "read_file", tag, FENCED_RESULT_HEADER) == 1
    assert supersede_fenced([msg], "read_file", tag, FENCED_RESULT_HEADER) == 0


# ---------- M245: superseding a history loaded from the store ----------


def test_loaded_history_keeps_only_the_last_of_each_duplicate_read() -> None:
    from veles.core.history_repair import supersede_loaded_history

    history = [
        *_pair("c1", "read_file", {"path": "a.py"}, "VERSION 1"),
        *_pair("c2", "read_file", {"path": "b.py"}, "OTHER FILE"),
        *_pair("c3", "read_file", {"path": "a.py"}, "VERSION 2"),
        *_pair("c4", "read_file", {"path": "a.py"}, "VERSION 3"),
    ]
    assert supersede_loaded_history(history, FENCED_RESULT_HEADER) == 2

    tools = [m.content for m in history if m.role == "tool"]
    marker = "<superseded by a newer identical read_file call>"
    assert tools == [marker, "OTHER FILE", marker, "VERSION 3"], (
        "only the freshest read of a.py survives; b.py is untouched"
    )


def test_loaded_history_supersede_is_idempotent() -> None:
    from veles.core.history_repair import supersede_loaded_history

    history = [
        *_pair("c1", "read_file", {"path": "a.py"}, "OLD"),
        *_pair("c2", "read_file", {"path": "a.py"}, "NEW"),
    ]
    assert supersede_loaded_history(history, FENCED_RESULT_HEADER) == 1
    assert supersede_loaded_history(history, FENCED_RESULT_HEADER) == 0


def test_loaded_history_leaves_nondeterministic_tools_alone() -> None:
    from veles.core.history_repair import supersede_loaded_history

    history = [
        *_pair("c1", "run_shell", {"cmd": "pytest"}, "3 failed"),
        *_pair("c2", "run_shell", {"cmd": "pytest"}, "0 failed"),
    ]
    assert supersede_loaded_history(history, FENCED_RESULT_HEADER) == 0
    assert [m.content for m in history if m.role == "tool"] == ["3 failed", "0 failed"]


def test_loaded_history_collapses_fenced_duplicates() -> None:
    from veles.core.history_repair import supersede_loaded_history

    tag = call_key("read_file", {"path": "a.py"})
    first = _fenced(f"[read_file {tag}]\nVERSION 1")
    second = _fenced(f"[read_file {tag}]\nVERSION 2")
    history = [first, second]

    assert supersede_loaded_history(history, FENCED_RESULT_HEADER) == 1
    assert "VERSION 1" not in (first.content or "")
    assert "VERSION 2" in (second.content or ""), "the newest fenced chunk survives"


def test_resumed_session_does_not_rehydrate_the_stale_read(tmp_path) -> None:
    """The whole point: the store is an append-only archive, so a resume used to
    hand the model back both versions of the same file."""
    from veles.core.history_repair import supersede_loaded_history
    from veles.core.memory import SessionStore

    store = SessionStore(tmp_path / "memory.db")
    try:
        sid = store.create_session()
        for m in [
            *_pair("c1", "read_file", {"path": "a.py"}, "STALE CONTENT"),
            *_pair("c2", "read_file", {"path": "a.py"}, "FRESH CONTENT"),
        ]:
            store.append_turn(sid, m)

        loaded = store.load_messages(sid)
        assert "STALE CONTENT" in [m.content for m in loaded], "archive keeps everything"

        supersede_loaded_history(loaded, FENCED_RESULT_HEADER)
        contents = [m.content for m in loaded if m.role == "tool"]
        assert "STALE CONTENT" not in contents
        assert "FRESH CONTENT" in contents
    finally:
        store.close()


# ---------- end to end through the agent loop ----------


def _read_registry() -> Registry:
    reg = Registry()
    reg.register(
        ToolEntry(
            name="read_file",
            description="",
            parameter_schema={"type": "object", "properties": {"path": {"type": "string"}}},
            handler=lambda path: f"contents of {path}",
            is_async=False,
            sensitive=False,
        )
    )
    return reg


@dataclass
class _ReadTwiceProvider:
    """Asks for the same read twice, then answers."""

    name: str = "stub"
    supports_tools: bool = True
    supports_streaming: bool = False
    n: int = 0

    def create_message(self, messages, tools=None, *, model, max_tokens=4096):
        del messages, tools, model, max_tokens
        self.n += 1
        if self.n <= 2:
            return ProviderResponse(
                text=None,
                tool_calls=[
                    ToolCall(id=f"c{self.n}", name="read_file", arguments={"path": "a.py"})
                ],
                usage=TokenUsage(total_tokens=1),
                finish_reason="tool_use",
            )
        return ProviderResponse(
            text="done", tool_calls=[], usage=TokenUsage(total_tokens=1), finish_reason="stop"
        )


def test_agent_supersedes_the_duplicate_read_in_the_live_history() -> None:
    agent = Agent(_ReadTwiceProvider(), _read_registry(), model="m", fenced_tools=False)
    result = agent.run("go")

    tool_msgs = [m for m in result.history if m.role == "tool"]
    assert len(tool_msgs) == 2, "both messages stay — only the content is blanked"
    assert tool_msgs[0].content == "<superseded by a newer identical read_file call>"
    assert tool_msgs[1].content == "contents of a.py"
    assert result.stopped_reason == "completed"

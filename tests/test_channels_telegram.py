"""M52 channels — TelegramGateway behavioural tests.

We don't hit api.telegram.org. Instead we inject a stub `_telegram_send`
that records calls + returns canned responses, plus a fake daemon
client that yields scripted events. This isolates the gateway's
update→run→stream→edit logic without network I/O.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import pytest

from veles.channels.daemon_client import DaemonClientError
from veles.channels.session_map import SessionMap
from veles.channels.telegram import TelegramGateway
from veles.core.i18n import t


class _FakeDaemonClient:
    def __init__(
        self,
        *,
        events: list[dict[str, Any]] | None = None,
        run_id: str = "run-1",
        submit_error: Exception | None = None,
    ) -> None:
        self.events = events or [
            {"type": "started", "run_id": run_id},
            {"type": "text_delta", "delta": "hello "},
            {"type": "text_delta", "delta": "world"},
            {
                "type": "completed",
                "text": "hello world",
                "session_id": "ses-final",
            },
        ]
        self.run_id = run_id
        self.submit_error = submit_error
        self.submitted: list[tuple[str, str | None]] = []

    async def submit_run(
        self, prompt: str, *, session_id: str | None = None, origin: str | None = None
    ):
        if self.submit_error is not None:
            raise self.submit_error
        self.submitted.append((prompt, session_id))
        return {"run_id": self.run_id, "session_id": session_id, "state": "running"}

    async def stream_events(self, run_id: str):
        for event in self.events:
            yield event


@pytest.fixture()
def session_map(tmp_path: Path) -> SessionMap:
    return SessionMap.load(tmp_path / "telegram-sessions.json")


def _make_gateway(
    daemon_client: Any,
    session_map: SessionMap,
    sends: list[tuple[str, dict[str, Any]]],
) -> TelegramGateway:
    async def stub_send(method: str, payload: dict[str, Any]) -> dict[str, Any]:
        sends.append((method, payload))
        if method == "sendMessage":
            return {"message_id": 99, "chat": payload["chat_id"]}
        if method == "editMessageText":
            return {"edited": True, "message_id": payload["message_id"]}
        if method == "sendChatAction":
            return {"ok": True}
        return {}

    gateway = TelegramGateway(
        bot_token="X",
        daemon_client=daemon_client,
        session_map=session_map,
    )
    gateway._telegram_send = stub_send
    return gateway


def _message_update(chat_id: int, text: str) -> dict[str, Any]:
    return {
        "update_id": 1,
        "message": {
            "chat": {"id": chat_id, "type": "private"},
            "text": text,
        },
    }


# ---- tests ----


async def test_start_command_replies_with_greeting(session_map: SessionMap) -> None:
    daemon = _FakeDaemonClient()
    sends: list[tuple[str, dict[str, Any]]] = []
    gateway = _make_gateway(daemon, session_map, sends)
    await gateway._handle_update(_message_update(42, "/start"))
    methods = [m for m, _ in sends]
    assert methods == ["sendMessage"]
    assert "Veles" in sends[0][1]["text"]


# ---- M116.1: slash-command dispatcher ----


async def test_help_command_lists_commands(session_map: SessionMap) -> None:
    daemon = _FakeDaemonClient()
    sends: list[tuple[str, dict[str, Any]]] = []
    gateway = _make_gateway(daemon, session_map, sends)
    await gateway._handle_update(_message_update(42, "/help"))
    assert [m for m, _ in sends] == ["sendMessage"]
    text = sends[0][1]["text"]
    assert "/help" in text and "/status" in text and "/session" in text


async def test_status_command_returns_snapshot(session_map: SessionMap) -> None:
    session_map.set("42", "ses-xyz")
    daemon = _FakeDaemonClient()
    sends: list[tuple[str, dict[str, Any]]] = []
    gateway = _make_gateway(daemon, session_map, sends)
    await gateway._handle_update(_message_update(42, "/status"))
    text = sends[0][1]["text"]
    assert "ses-xyz" in text
    assert "status" in text.lower()


async def test_session_command_without_session(session_map: SessionMap) -> None:
    daemon = _FakeDaemonClient()
    sends: list[tuple[str, dict[str, Any]]] = []
    gateway = _make_gateway(daemon, session_map, sends)
    await gateway._handle_update(_message_update(42, "/session"))
    text = sends[0][1]["text"]
    assert "none yet" in text or "start one" in text


async def test_session_command_with_active_session(session_map: SessionMap) -> None:
    session_map.set("42", "ses-active-1")
    daemon = _FakeDaemonClient()
    sends: list[tuple[str, dict[str, Any]]] = []
    gateway = _make_gateway(daemon, session_map, sends)
    await gateway._handle_update(_message_update(42, "/session"))
    assert "ses-active-1" in sends[0][1]["text"]


async def test_tokens_and_context_return_placeholders(
    session_map: SessionMap,
) -> None:
    """Until the daemon HTTP API exposes per-session usage, /tokens and
    /context return WIP notices — they're in the menu so the surface
    area matches TUI, but they don't lie about being unimplemented."""
    daemon = _FakeDaemonClient()
    sends: list[tuple[str, dict[str, Any]]] = []
    gateway = _make_gateway(daemon, session_map, sends)
    await gateway._handle_update(_message_update(42, "/tokens"))
    await gateway._handle_update(_message_update(42, "/context"))
    assert "tokens" in sends[0][1]["text"].lower()
    assert "context" in sends[1][1]["text"].lower()


async def test_unknown_command_hints_at_help(session_map: SessionMap) -> None:
    """Unknown commands don't get forwarded to the agent — the bot
    replies with a hint pointing at /help."""
    daemon = _FakeDaemonClient()
    sends: list[tuple[str, dict[str, Any]]] = []
    gateway = _make_gateway(daemon, session_map, sends)
    await gateway._handle_update(_message_update(42, "/whatisthis"))
    # No agent submission, just the hint.
    assert daemon.submitted == []
    assert "/help" in sends[0][1]["text"]


async def test_publish_command_menu_sends_setmycommands(
    session_map: SessionMap,
) -> None:
    """`_publish_command_menu` hits `setMyCommands` with the descriptor
    payload from `menu_descriptors()`."""
    daemon = _FakeDaemonClient()
    sends: list[tuple[str, dict[str, Any]]] = []
    gateway = _make_gateway(daemon, session_map, sends)
    await gateway._publish_command_menu()
    assert sends, "expected at least one Telegram call"
    method, payload = sends[0]
    assert method == "setMyCommands"
    assert isinstance(payload, dict)
    assert "commands" in payload
    cmds = payload["commands"]
    assert isinstance(cmds, list) and len(cmds) >= 5
    assert all("command" in c and "description" in c for c in cmds)


async def test_reset_command_with_active_session(session_map: SessionMap) -> None:
    session_map.set("42", "ses-old")
    daemon = _FakeDaemonClient()
    sends: list[tuple[str, dict[str, Any]]] = []
    gateway = _make_gateway(daemon, session_map, sends)
    await gateway._handle_update(_message_update(42, "/reset"))
    assert session_map.get("42") is None
    assert sends[0][1]["text"] == t("telegram.history_cleared")


async def test_reset_command_without_active_session(session_map: SessionMap) -> None:
    daemon = _FakeDaemonClient()
    sends: list[tuple[str, dict[str, Any]]] = []
    gateway = _make_gateway(daemon, session_map, sends)
    await gateway._handle_update(_message_update(42, "/reset"))
    assert sends[0][1]["text"] == t("telegram.history_empty")


async def test_message_creates_session_mapping(session_map: SessionMap) -> None:
    daemon = _FakeDaemonClient()
    sends: list[tuple[str, dict[str, Any]]] = []
    gateway = _make_gateway(daemon, session_map, sends)
    await gateway._handle_update(_message_update(42, "tell me a joke"))

    # First daemon submit had no session_id (cold start)
    assert daemon.submitted == [("tell me a joke", None)]
    # After completed event, session_id is persisted
    assert session_map.get("42") == "ses-final"

    # M108: send placeholder first, then a single final edit. The
    # typing-indicator background task may or may not get a tick in
    # before completion fires (fast stub streams settle near-instantly),
    # so we don't assert on its presence here — _typing_loop has its
    # own dedicated tests.
    methods = [m for m, _ in sends]
    assert methods[0] == "sendMessage"  # placeholder
    assert "editMessageText" in methods  # final edit


async def test_second_message_reuses_existing_session(session_map: SessionMap) -> None:
    session_map.set("42", "ses-existing")
    daemon = _FakeDaemonClient()
    sends: list[tuple[str, dict[str, Any]]] = []
    gateway = _make_gateway(daemon, session_map, sends)
    await gateway._handle_update(_message_update(42, "follow-up"))
    assert daemon.submitted == [("follow-up", "ses-existing")]


async def test_final_edit_carries_complete_text(session_map: SessionMap) -> None:
    daemon = _FakeDaemonClient()
    sends: list[tuple[str, dict[str, Any]]] = []
    gateway = _make_gateway(daemon, session_map, sends)
    await gateway._handle_update(_message_update(42, "hi"))
    edits = [p for m, p in sends if m == "editMessageText"]
    assert edits, "expected at least one edit"
    assert edits[-1]["text"] == "hello world"


async def test_error_event_surfaces_to_user(session_map: SessionMap) -> None:
    daemon = _FakeDaemonClient(
        events=[
            {"type": "started", "run_id": "run-1"},
            {"type": "error", "error": "provider blew up"},
        ]
    )
    sends: list[tuple[str, dict[str, Any]]] = []
    gateway = _make_gateway(daemon, session_map, sends)
    await gateway._handle_update(_message_update(42, "hi"))
    edits = [p for m, p in sends if m == "editMessageText"]
    assert "provider blew up" in edits[-1]["text"]
    # Failed run must NOT persist a session mapping
    assert session_map.get("42") is None


async def test_daemon_unavailable_responds_with_error(
    session_map: SessionMap,
) -> None:
    daemon = _FakeDaemonClient(submit_error=DaemonClientError("daemon down", status=502))
    sends: list[tuple[str, dict[str, Any]]] = []
    gateway = _make_gateway(daemon, session_map, sends)
    await gateway._handle_update(_message_update(42, "hi"))
    # No placeholder was sent because we returned before sendMessage:
    sent = [p for m, p in sends if m == "sendMessage"]
    assert sent
    assert "daemon error" in sent[0]["text"]


async def test_non_text_messages_ignored(session_map: SessionMap) -> None:
    daemon = _FakeDaemonClient()
    sends: list[tuple[str, dict[str, Any]]] = []
    gateway = _make_gateway(daemon, session_map, sends)
    # update with no message at all
    await gateway._handle_update({"update_id": 1})
    # update with photo-only message (no text)
    await gateway._handle_update({"update_id": 2, "message": {"chat": {"id": 42}, "photo": []}})
    assert sends == []


async def test_long_response_truncated_to_telegram_cap(
    session_map: SessionMap,
) -> None:
    big_text = "x" * 5000
    daemon = _FakeDaemonClient(
        events=[
            {"type": "started", "run_id": "run-1"},
            {"type": "completed", "text": big_text, "session_id": "ses-X"},
        ]
    )
    sends: list[tuple[str, dict[str, Any]]] = []
    gateway = _make_gateway(daemon, session_map, sends)
    await gateway._handle_update(_message_update(42, "hi"))
    edits = [p for m, p in sends if m == "editMessageText"]
    final = edits[-1]["text"]
    assert len(final) <= 4000


async def test_text_deltas_aggregate_in_final_edit(session_map: SessionMap) -> None:
    # Force many small deltas — the gateway should still produce the full text
    # on completion, regardless of how many intermediate edits it issued.
    deltas = [{"type": "text_delta", "delta": ch} for ch in "abcdefghij"]
    daemon = _FakeDaemonClient(
        events=[
            {"type": "started", "run_id": "run-1"},
            *deltas,
            {"type": "completed", "text": "abcdefghij", "session_id": "ses-Y"},
        ]
    )
    sends: list[tuple[str, dict[str, Any]]] = []
    gateway = _make_gateway(daemon, session_map, sends)
    await gateway._handle_update(_message_update(42, "stream me"))
    edits = [p for m, p in sends if m == "editMessageText"]
    assert edits[-1]["text"] == "abcdefghij"


async def test_run_turn_emits_only_one_final_edit(session_map: SessionMap) -> None:
    """M108: many text_delta events in flight, but the gateway sends a
    single placeholder + a single final edit — no intermediate
    editMessageText calls (which previously tripped Telegram's
    per-chat rate limit on long replies)."""
    deltas = [{"type": "text_delta", "delta": ch} for ch in "abcdefghij"]
    daemon = _FakeDaemonClient(
        events=[
            {"type": "started", "run_id": "run-1"},
            *deltas,
            {"type": "completed", "text": "abcdefghij", "session_id": "ses-X"},
        ]
    )
    sends: list[tuple[str, dict[str, Any]]] = []
    gateway = _make_gateway(daemon, session_map, sends)
    await gateway._handle_update(_message_update(42, "stream me"))
    edits = [p for m, p in sends if m == "editMessageText"]
    assert len(edits) == 1
    assert edits[0]["text"] == "abcdefghij"


async def test_second_message_while_busy_gets_queued_ack(session_map: SessionMap) -> None:
    """A message arriving while a turn runs for the same chat gets an
    immediate 'queued' ack, then waits its turn (FIFO)."""
    daemon = _FakeDaemonClient()
    sends: list[tuple[str, dict[str, Any]]] = []
    gateway = _make_gateway(daemon, session_map, sends)
    # Simulate an in-flight turn by holding the chat's serial lock.
    lock = asyncio.Lock()
    gateway._chat_locks["42"] = lock
    await lock.acquire()
    task = asyncio.create_task(gateway._run_turn_serial(42, "42", "second"))
    await asyncio.sleep(0)  # let the coroutine reach the lock
    assert any(m == "sendMessage" and p.get("text") == t("telegram.ack_queued") for m, p in sends)
    lock.release()
    await task


async def test_single_message_gets_no_queued_ack(session_map: SessionMap) -> None:
    daemon = _FakeDaemonClient()
    sends: list[tuple[str, dict[str, Any]]] = []
    gateway = _make_gateway(daemon, session_map, sends)
    await gateway._handle_update(_message_update(42, "hi"))
    assert not any(p.get("text") == t("telegram.ack_queued") for _m, p in sends)


async def test_run_turn_shows_contextual_ack_on_tool_call(session_map: SessionMap) -> None:
    """When the agent's first action is a tool call, the "..." holder is
    edited into a contextual ack and the final answer arrives as a NEW
    message (the spec'd "accepted → final" two-message flow)."""
    daemon = _FakeDaemonClient(
        events=[
            {"type": "started", "run_id": "run-1", "session_id": "ses-A"},
            {"type": "tool_call", "name": "wiki_search", "tool_call_id": "t1"},
            {"type": "completed", "text": "the answer", "session_id": "ses-A"},
        ]
    )
    sends: list[tuple[str, dict[str, Any]]] = []
    gateway = _make_gateway(daemon, session_map, sends)
    await gateway._handle_update(_message_update(42, "look it up"))
    edits = [p for m, p in sends if m == "editMessageText"]
    # One edit only: placeholder → ack. The answer is not an edit.
    assert len(edits) == 1
    assert "🔍" in edits[0]["text"]
    assert "the answer" not in edits[0]["text"]
    # The final answer arrives as a fresh message beyond the "..." holder.
    new_msgs = [p for m, p in sends if m == "sendMessage" and p.get("text") != "..."]
    assert any("the answer" in p["text"] for p in new_msgs)


async def test_run_turn_no_ack_when_text_first(session_map: SessionMap) -> None:
    """A turn that answers directly (no tool call) shows no ack — the
    placeholder is edited straight into the answer, as before."""
    daemon = _FakeDaemonClient(
        events=[
            {"type": "started", "run_id": "run-1", "session_id": "ses-A"},
            {"type": "completed", "text": "quick reply", "session_id": "ses-A"},
        ]
    )
    sends: list[tuple[str, dict[str, Any]]] = []
    gateway = _make_gateway(daemon, session_map, sends)
    await gateway._handle_update(_message_update(42, "hi"))
    edits = [p for m, p in sends if m == "editMessageText"]
    assert len(edits) == 1
    assert edits[0]["text"] == "quick reply"


async def test_run_turn_splits_long_answer_into_chunks(session_map: SessionMap) -> None:
    """A reply longer than the Telegram limit is split, not truncated:
    the first chunk edits the placeholder, the rest arrive as new
    messages and no chunk exceeds the limit."""
    long_text = "word " * 2000  # ~10000 chars
    daemon = _FakeDaemonClient(
        events=[
            {"type": "started", "run_id": "run-1"},
            {"type": "completed", "text": long_text, "session_id": "ses-L"},
        ]
    )
    sends: list[tuple[str, dict[str, Any]]] = []
    gateway = _make_gateway(daemon, session_map, sends)
    await gateway._handle_update(_message_update(42, "give me a lot"))
    edits = [p for m, p in sends if m == "editMessageText"]
    # Extra chunks are new sendMessage calls beyond the "..." placeholder.
    extra = [p for m, p in sends if m == "sendMessage" and p.get("text") != "..."]
    assert len(edits) == 1
    assert len(extra) >= 2
    for payload in [edits[0], *extra]:
        assert len(payload["text"]) <= 4096


async def test_drain_stream_returns_completed_text_and_session(
    session_map: SessionMap,
) -> None:
    """M-R2.4: `_drain_stream` exposes the harvest of the event loop as
    a `_TurnOutcome` dataclass — testable without the surrounding
    submit/placeholder/deliver pipeline."""
    daemon = _FakeDaemonClient()
    sends: list[tuple[str, dict[str, Any]]] = []
    gateway = _make_gateway(daemon, session_map, sends)
    outcome = await gateway._drain_stream("run-1", chat_id=42)
    assert outcome.text == "hello world"
    assert outcome.session_id == "ses-final"
    assert outcome.error is None


async def test_drain_stream_captures_error_event(session_map: SessionMap) -> None:
    daemon = _FakeDaemonClient(
        events=[
            {"type": "started", "run_id": "run-1"},
            {"type": "error", "error": "boom"},
        ]
    )
    gateway = _make_gateway(daemon, session_map, [])
    outcome = await gateway._drain_stream("run-1", chat_id=42)
    assert outcome.error == "boom"
    assert outcome.session_id is None


async def test_drain_stream_adopts_session_id_from_started(session_map: SessionMap) -> None:
    """When the daemon puts the session id on `started`, the drain keeps
    it even if the run then errors with no `completed` — so the mapping
    can be persisted and the chat continues the same session."""
    daemon = _FakeDaemonClient(
        events=[
            {"type": "started", "run_id": "run-1", "session_id": "ses-early"},
            {"type": "error", "error": "boom", "session_id": "ses-early"},
        ]
    )
    gateway = _make_gateway(daemon, session_map, [])
    outcome = await gateway._drain_stream("run-1", chat_id=42)
    assert outcome.error == "boom"
    assert outcome.session_id == "ses-early"


async def test_deliver_persists_session_mapping_on_error(session_map: SessionMap) -> None:
    """An errored turn must still persist the chat→session mapping: the
    session existed (user turn stored) before the failure, so the next
    message continues it instead of starting a fresh, empty session."""
    daemon = _FakeDaemonClient(
        events=[
            {"type": "started", "run_id": "run-1", "session_id": "ses-early"},
            {"type": "error", "error": "boom", "session_id": "ses-early"},
        ]
    )
    sends: list[tuple[str, dict[str, Any]]] = []
    gateway = _make_gateway(daemon, session_map, sends)
    await gateway._handle_update(_message_update(42, "will fail"))
    assert session_map.get("42") == "ses-early"


async def test_typing_indicator_cancelled_after_completion(
    session_map: SessionMap,
) -> None:
    """The typing-indicator background task is cancelled when the run
    completes — it must not leak past the turn."""
    daemon = _FakeDaemonClient()
    sends: list[tuple[str, dict[str, Any]]] = []
    gateway = _make_gateway(daemon, session_map, sends)
    await gateway._handle_update(_message_update(42, "hi"))
    # After _handle_update returns the typing loop is already cancelled,
    # so no further sendChatAction calls fire after the final edit.
    methods_order = [m for m, _ in sends]
    final_edit_idx = next(i for i, m in enumerate(methods_order) if m == "editMessageText")
    assert "sendChatAction" not in methods_order[final_edit_idx + 1 :]


# ---- whitelist filter ----


def _message_with_sender(
    chat_id: int, text: str, *, user_id: int | None = None, username: str | None = None
) -> dict[str, Any]:
    msg: dict[str, Any] = {
        "chat": {"id": chat_id, "type": "private"},
        "text": text,
    }
    sender: dict[str, Any] = {}
    if user_id is not None:
        sender["id"] = user_id
    if username is not None:
        sender["username"] = username
    if sender:
        msg["from"] = sender
    return {"update_id": 1, "message": msg}


async def test_whitelist_blocks_non_whitelisted_sender(session_map: SessionMap) -> None:
    daemon = _FakeDaemonClient()
    sends: list[tuple[str, dict[str, Any]]] = []
    gateway = _make_gateway(daemon, session_map, sends)
    gateway.whitelist = ("12345", "@allowed_user")
    await gateway._handle_update(_message_with_sender(42, "hi", user_id=99999, username="stranger"))
    assert sends == []
    assert daemon.submitted == []


async def test_whitelist_allows_numeric_match(session_map: SessionMap) -> None:
    daemon = _FakeDaemonClient()
    sends: list[tuple[str, dict[str, Any]]] = []
    gateway = _make_gateway(daemon, session_map, sends)
    gateway.whitelist = ("12345",)
    await gateway._handle_update(_message_with_sender(42, "hi", user_id=12345, username="anyname"))
    assert daemon.submitted == [("hi", None)]


async def test_whitelist_allows_username_case_insensitive(session_map: SessionMap) -> None:
    daemon = _FakeDaemonClient()
    sends: list[tuple[str, dict[str, Any]]] = []
    gateway = _make_gateway(daemon, session_map, sends)
    gateway.whitelist = ("@AllowedUser",)
    await gateway._handle_update(_message_with_sender(42, "hi", user_id=1, username="alloweduser"))
    assert daemon.submitted == [("hi", None)]


async def test_empty_whitelist_allows_everyone(session_map: SessionMap) -> None:
    daemon = _FakeDaemonClient()
    sends: list[tuple[str, dict[str, Any]]] = []
    gateway = _make_gateway(daemon, session_map, sends)
    await gateway._handle_update(_message_with_sender(42, "hi", user_id=7, username="random"))
    assert daemon.submitted == [("hi", None)]


# ---- inline-keyboard prompts (channel approval) ----


class _PromptingFakeDaemon(_FakeDaemonClient):
    """Daemon that emits a `trust_prompt` mid-run, then completes once
    `submit_prompt_answer` is called. Lets us exercise the gateway's
    prompt round-trip end-to-end inside one test."""

    def __init__(self, *, kind: str = "trust", prompt_id: str = "abcd1234"):
        super().__init__(events=[])
        self.kind = kind
        self.prompt_id = prompt_id
        self.answers: list[tuple[str, str, str]] = []
        self._answered = asyncio.Event()

    async def submit_prompt_answer(
        self, run_id: str, prompt_id: str, choice: str
    ) -> dict[str, Any]:
        self.answers.append((run_id, prompt_id, choice))
        self._answered.set()
        return {"accepted": True, "choice": choice}

    async def stream_events(self, run_id: str):
        if self.kind == "trust":
            yield {
                "type": "trust_prompt",
                "prompt_id": self.prompt_id,
                "tool": "Bash",
                "options": [
                    {"key": "once", "label": "Once"},
                    {"key": "always_project", "label": "Always for project"},
                    {"key": "refuse", "label": "Refuse"},
                ],
            }
        elif self.kind == "critical":
            yield {
                "type": "critical_prompt",
                "prompt_id": self.prompt_id,
                "op": "dispatch fetch_url",
                "summary": "possible prompt-injection exfiltration",
                "options": [
                    {"key": "yes", "label": "Allow"},
                    {"key": "no", "label": "Cancel"},
                ],
            }
        else:
            yield {
                "type": "approval_prompt",
                "prompt_id": self.prompt_id,
                "tool": "Write",
                "reason": "writes outside project",
                "arguments": {"path": "/etc/x"},
                "options": [
                    {"key": "yes", "label": "Allow"},
                    {"key": "no", "label": "Deny"},
                ],
            }
        # Block until a button is "tapped" so the gateway has time to
        # register the pending prompt.
        await self._answered.wait()
        yield {
            "type": "prompt_resolved",
            "prompt_id": self.prompt_id,
            "choice": self.answers[-1][2],
        }
        yield {"type": "completed", "text": "done", "session_id": "ses-prompt"}


def _callback_update(chat_id: int, message_id: int, callback_id: str, data: str) -> dict[str, Any]:
    return {
        "update_id": 99,
        "callback_query": {
            "id": callback_id,
            "from": {"id": 42, "username": "u"},
            "message": {"message_id": message_id, "chat": {"id": chat_id}},
            "data": data,
        },
    }


async def test_trust_prompt_renders_inline_keyboard(session_map: SessionMap) -> None:
    daemon = _PromptingFakeDaemon(kind="trust", prompt_id="aaaa1111")
    sends: list[tuple[str, dict[str, Any]]] = []
    gateway = _make_gateway(daemon, session_map, sends)

    async def drive() -> None:
        # Simulate the button tap after the prompt is registered.
        for _ in range(50):
            if "aaaa1111" in gateway._pending_prompts:
                break
            await asyncio.sleep(0.01)
        await gateway._handle_callback_query(
            {
                "id": "cb-1",
                "from": {"id": 42, "username": "u"},
                "data": "v:aaaa1111:o",
            }
        )

    driver = asyncio.create_task(drive())
    await gateway._handle_update(_message_update(42, "run a shell command"))
    await driver

    # Three buttons in the inline keyboard.
    prompt_sends = [p for m, p in sends if m == "sendMessage" and "reply_markup" in p]
    assert prompt_sends, "expected a prompt sendMessage with reply_markup"
    row = prompt_sends[0]["reply_markup"]["inline_keyboard"][0]
    assert len(row) == 3
    assert [b["text"] for b in row] == [
        "Once",
        "Always for project",
        "Refuse",
    ]
    # callback_data carries the prompt id + short code.
    assert [b["callback_data"] for b in row] == [
        "v:aaaa1111:o",
        "v:aaaa1111:p",
        "v:aaaa1111:r",
    ]
    # Tap was forwarded to the daemon with the full key, not the short.
    assert daemon.answers == [("run-1", "aaaa1111", "once")]
    # answerCallbackQuery is invoked to dismiss the spinner.
    assert any(m == "answerCallbackQuery" for m, _ in sends)


async def test_approval_prompt_renders_two_buttons(session_map: SessionMap) -> None:
    daemon = _PromptingFakeDaemon(kind="approval", prompt_id="bbbb2222")
    sends: list[tuple[str, dict[str, Any]]] = []
    gateway = _make_gateway(daemon, session_map, sends)

    async def drive() -> None:
        for _ in range(50):
            if "bbbb2222" in gateway._pending_prompts:
                break
            await asyncio.sleep(0.01)
        await gateway._handle_callback_query(
            {
                "id": "cb-2",
                "from": {"id": 42},
                "data": "v:bbbb2222:n",
            }
        )

    driver = asyncio.create_task(drive())
    await gateway._handle_update(_message_update(42, "do dangerous thing"))
    await driver

    prompt_sends = [p for m, p in sends if m == "sendMessage" and "reply_markup" in p]
    row = prompt_sends[0]["reply_markup"]["inline_keyboard"][0]
    assert [b["text"] for b in row] == ["Allow", "Deny"]
    assert [b["callback_data"] for b in row] == [
        "v:bbbb2222:y",
        "v:bbbb2222:n",
    ]
    assert daemon.answers == [("run-1", "bbbb2222", "no")]


async def test_critical_prompt_renders_keyboard_and_resolves(session_map: SessionMap) -> None:
    """M213: a `critical_prompt` event (always-confirm / exfiltration gate)
    renders an alarming two-button keyboard; the tap resolves back to the
    daemon with the full key — same round-trip as approval."""
    daemon = _PromptingFakeDaemon(kind="critical", prompt_id="dddd4444")
    sends: list[tuple[str, dict[str, Any]]] = []
    gateway = _make_gateway(daemon, session_map, sends)

    async def drive() -> None:
        for _ in range(50):
            if "dddd4444" in gateway._pending_prompts:
                break
            await asyncio.sleep(0.01)
        await gateway._handle_callback_query(
            {
                "id": "cb-4",
                "from": {"id": 42},
                "data": "v:dddd4444:y",
            }
        )

    driver = asyncio.create_task(drive())
    await gateway._handle_update(_message_update(42, "fetch that law text"))
    await driver

    prompt_sends = [p for m, p in sends if m == "sendMessage" and "reply_markup" in p]
    assert prompt_sends, "expected a critical prompt sendMessage with reply_markup"
    body = prompt_sends[0]["text"]
    assert "Critical operation" in body
    assert "dispatch fetch_url" in body
    assert "possible prompt-injection exfiltration" in body
    row = prompt_sends[0]["reply_markup"]["inline_keyboard"][0]
    assert [b["callback_data"] for b in row] == [
        "v:dddd4444:y",
        "v:dddd4444:n",
    ]
    # Tap forwarded with the full key — the daemon side maps "yes" → allow.
    assert daemon.answers == [("run-1", "dddd4444", "yes")]


async def test_prompt_resolved_strips_buttons_on_original_message(
    session_map: SessionMap,
) -> None:
    daemon = _PromptingFakeDaemon(kind="trust", prompt_id="cccc3333")
    sends: list[tuple[str, dict[str, Any]]] = []
    gateway = _make_gateway(daemon, session_map, sends)

    async def drive() -> None:
        for _ in range(50):
            if "cccc3333" in gateway._pending_prompts:
                break
            await asyncio.sleep(0.01)
        await gateway._handle_callback_query({"id": "cb-3", "from": {}, "data": "v:cccc3333:p"})

    driver = asyncio.create_task(drive())
    await gateway._handle_update(_message_update(42, "hi"))
    await driver

    # After prompt_resolved arrives, the gateway edits the prompt
    # message to empty out the keyboard.
    cleared_edits = [
        p
        for m, p in sends
        if m == "editMessageText" and p.get("reply_markup", {}).get("inline_keyboard") == []
    ]
    assert cleared_edits, "prompt_resolved should clear the inline keyboard"
    # Pending entry was popped — a stale tap can't double-resolve.
    assert "cccc3333" not in gateway._pending_prompts


async def test_unknown_callback_data_is_dismissed_quietly(
    session_map: SessionMap,
) -> None:
    daemon = _FakeDaemonClient(events=[])
    sends: list[tuple[str, dict[str, Any]]] = []
    gateway = _make_gateway(daemon, session_map, sends)
    await gateway._handle_callback_query({"id": "cb-x", "from": {}, "data": "v:missing:o"})
    # No daemon call, but the spinner is still dismissed.
    assert any(m == "answerCallbackQuery" for m, _ in sends)


# ---- HTML / parse_mode / fallback (TG-3) ----


async def test_payload_carries_parse_mode_html(session_map: SessionMap) -> None:
    """Every send/edit must request HTML rendering so Telegram parses
    `<b>`, `<code>`, etc. instead of showing them as text."""
    daemon = _FakeDaemonClient()
    sends: list[tuple[str, dict[str, Any]]] = []
    gateway = _make_gateway(daemon, session_map, sends)
    await gateway._handle_update(_message_update(42, "hi"))
    edits = [p for m, p in sends if m == "editMessageText"]
    sent = [p for m, p in sends if m == "sendMessage"]
    assert sent and sent[0].get("parse_mode") == "HTML"
    assert edits and edits[-1].get("parse_mode") == "HTML"


async def test_markdown_response_renders_as_html(session_map: SessionMap) -> None:
    """Bold/code in the agent's Markdown answer reach the user as HTML
    tags Telegram knows how to render, not as raw `**` or backticks."""
    daemon = _FakeDaemonClient(
        events=[
            {"type": "started", "run_id": "run-1"},
            {
                "type": "completed",
                "text": "Use `read_file` — it's **safe**.",
                "session_id": "ses-md",
            },
        ]
    )
    sends: list[tuple[str, dict[str, Any]]] = []
    gateway = _make_gateway(daemon, session_map, sends)
    await gateway._handle_update(_message_update(42, "hi"))
    final = [p for m, p in sends if m == "editMessageText"][-1]["text"]
    assert "<code>read_file</code>" in final
    assert "<b>safe</b>" in final
    assert "**" not in final  # raw markdown is gone


async def test_parse_error_falls_back_to_plain_text(
    session_map: SessionMap,
) -> None:
    """If Telegram rejects the HTML (`can't parse entities`) we retry
    without parse_mode and with tags stripped — the user still gets the
    message, just without rich formatting."""
    daemon = _FakeDaemonClient()
    sends: list[tuple[str, dict[str, Any]]] = []
    call_count = {"send": 0, "edit": 0}

    async def stub_send(method: str, payload: dict[str, Any]) -> dict[str, Any]:
        sends.append((method, payload))
        if method == "sendMessage":
            call_count["send"] += 1
            # First sendMessage (the placeholder) succeeds normally.
            return {"message_id": 99, "chat": payload["chat_id"]}
        if method == "editMessageText":
            call_count["edit"] += 1
            # First edit (with parse_mode=HTML) — pretend Telegram rejects.
            if call_count["edit"] == 1 and payload.get("parse_mode") == "HTML":
                raise RuntimeError(
                    "telegram editMessageText failed: Bad Request: can't parse entities"
                )
            return {"edited": True, "message_id": payload["message_id"]}
        return {}

    gateway = TelegramGateway(
        bot_token="X",
        daemon_client=daemon,
        session_map=session_map,
    )
    gateway._telegram_send = stub_send
    await gateway._handle_update(_message_update(42, "hi"))
    edits = [p for m, p in sends if m == "editMessageText"]
    assert len(edits) == 2, "expected one rejected edit + one retry"
    assert edits[0].get("parse_mode") == "HTML"
    assert "parse_mode" not in edits[1]


# ---- prompt body (TG-4) ----


def test_format_prompt_body_html_no_raw_dict() -> None:
    """Approval-prompt body must not dump the raw Python dict of args
    (`{'path': '/Users/...'}`) — neither the dict syntax nor abs paths."""
    import tempfile

    from veles.channels.telegram import _format_prompt_body
    from veles.core.context import reset_active_project, set_active_project
    from veles.core.project import init_project

    with tempfile.TemporaryDirectory() as td:
        from pathlib import Path

        project = init_project(Path(td) / "mp", name="mind-palace")
        token = set_active_project(project)
        try:
            body = _format_prompt_body(
                "approval",
                {
                    "tool": "write_file",
                    "reason": "writes outside project",
                    "arguments": {"path": str(project.root.resolve()) + "/x.md"},
                },
            )
        finally:
            reset_active_project(token)
    # HTML structure, no raw Python repr of dict.
    assert "<b>Approval required</b>" in body
    assert "<code>write_file</code>" in body
    assert "<code>path</code>" in body
    # `{'path': ...}` style must not appear.
    assert "{'path'" not in body
    # Project root sanitized through `core.sanitize` (Round 2). The
    # `<mind-palace>` placeholder is then HTML-escaped to `&lt;…&gt;`
    # so Telegram doesn't try to read it as a tag — but Telegram
    # decodes the entity back to literal angles on display.
    assert "/Users/" not in body
    assert "&lt;mind-palace&gt;" in body


# ---- attachment / forward / aggregation (DOC-6) ----


from veles.channels.telegram import (  # noqa: E402
    _build_combined_prompt,
    _classify,
    _forward_source,
    _has_forward,
    _is_textual,
    _Kind,
    _reject_reason,
    _render_forwarded,
    _safe_filename,
)

# ---- unit: pure helpers ----


def test_safe_filename_strips_traversal() -> None:
    """The Telegram-supplied `file_name` is user input — `..`, `/`, and
    other spice mustn't survive into a real path. `Path.name` strips
    parent components, so only the trailing basename survives."""
    assert _safe_filename("../../../etc/passwd") == "passwd"
    assert _safe_filename("/abs/path/foo.md") == "foo.md"
    assert _safe_filename("evil.md\x00trailing") == "evil.md_trailing"
    assert _safe_filename("") == "file"
    assert _safe_filename("a" * 200).startswith("a" * 80)
    assert len(_safe_filename("a" * 200)) == 80


def test_is_textual_by_mime_and_extension() -> None:
    assert _is_textual("foo.md", "text/markdown")
    assert _is_textual("data.json", "application/json")
    assert _is_textual("config.yaml", "application/x-yaml")
    # mime missing — fall back on extension.
    assert _is_textual("notes.txt", "")
    assert _is_textual("script.py", "")
    # Binary stays binary.
    assert not _is_textual("photo.jpg", "image/jpeg")
    assert not _is_textual("doc.pdf", "application/pdf")
    assert not _is_textual("archive.zip", "application/zip")


def test_reject_reason_size_then_type() -> None:
    """Too-large beats wrong-type — the user gets the more relevant
    refusal first if both apply."""
    assert _reject_reason("foo.md", "text/markdown", 6 * 1024 * 1024).startswith(
        "📎 File larger than 5 MB"
    )
    assert _reject_reason("photo.jpg", "image/jpeg", 1024).startswith("📎 I only handle text files")
    assert _reject_reason("ok.md", "text/markdown", 1024) is None


def test_classify_priority() -> None:
    """Document beats forward beats text — a forwarded post with a
    .md attachment is classified as DOCUMENT and downloaded."""
    assert _classify({"text": "hi"}) is _Kind.TEXT
    assert _classify({"forward_from": {"username": "x"}, "text": "y"}) is _Kind.FORWARD
    assert _classify({"document": {"file_id": "1"}, "caption": "c"}) is _Kind.DOCUMENT
    assert _classify({"photo": []}) is _Kind.IGNORED


def test_has_forward_matches_all_known_keys() -> None:
    assert _has_forward({"forward_origin": {"type": "user"}})
    assert _has_forward({"forward_from": {"id": 1}})
    assert _has_forward({"forward_from_chat": {"id": 1}})
    assert _has_forward({"forward_sender_name": "Hidden"})
    assert not _has_forward({"text": "plain"})


def test_forward_source_extracts_channel_title() -> None:
    msg = {"forward_from_chat": {"title": "Indie News", "username": "indie_news"}}
    assert _forward_source(msg) == "Indie News"


def test_forward_source_falls_back_to_sender_name() -> None:
    assert _forward_source({"forward_sender_name": "Hidden Soul"}) == "Hidden Soul"


def test_render_forwarded_wraps_body_in_quote() -> None:
    out = _render_forwarded({"forward_from_chat": {"title": "News"}, "text": "Line 1\nLine 2"})
    assert out.startswith("↪️ Forwarded from News:")
    assert "> Line 1" in out
    assert "> Line 2" in out


def test_build_combined_prompt_appends_attachment_listing(tmp_path: Path) -> None:
    project_root = tmp_path
    att = tmp_path / ".veles" / "tmp" / "abc-foo.md"
    att.parent.mkdir(parents=True)
    att.write_text("body", encoding="utf-8")
    out = _build_combined_prompt(["summarise"], [att], project_root)
    assert out.startswith("summarise")
    assert "`.veles/tmp/abc-foo.md`" in out
    assert "read_file" in out


def test_build_combined_prompt_no_attachments_no_trailer(tmp_path: Path) -> None:
    out = _build_combined_prompt(["hi"], [], tmp_path)
    assert out == "hi"
    assert "Attachments" not in out


def test_build_combined_prompt_generic_when_only_attachment(tmp_path: Path) -> None:
    att = tmp_path / "doc.md"
    att.write_text("x", encoding="utf-8")
    out = _build_combined_prompt([], [att], tmp_path)
    assert out.startswith("I sent you a file")


# ---- integration: _dispatch_messages + aggregator ----


class _StubBackend:
    """Records `submit_run` calls without invoking a real daemon."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, str | None]] = []

    async def submit_run(
        self, prompt: str, *, session_id: str | None = None, origin: str | None = None
    ):
        self.calls.append((prompt, session_id))
        return {"run_id": "run-x", "session_id": session_id, "state": "running"}

    async def stream_events(self, run_id):
        if False:
            yield {}


def _gateway_with_attachments(
    session_map: SessionMap, tmp_path: Path, sends: list[tuple[str, dict[str, Any]]]
) -> TelegramGateway:
    """Gateway with attachment_dir wired so document tests can save
    real bytes into a tmp tree without spinning up a project."""
    attachment_dir = tmp_path / ".veles" / "tmp"
    project_root = tmp_path

    backend = _StubBackend()

    async def stub_send(method: str, payload: dict[str, Any]) -> dict[str, Any]:
        sends.append((method, payload))
        if method == "sendMessage":
            return {"message_id": 99 + len(sends), "chat": payload["chat_id"]}
        if method == "editMessageText":
            return {"edited": True, "message_id": payload["message_id"]}
        if method == "sendChatAction":
            return {"ok": True}
        if method == "getFile":
            return {"file_path": "documents/foo.md"}
        return {}

    gateway = TelegramGateway(
        bot_token="X",
        daemon_client=backend,
        session_map=session_map,
        attachment_dir=attachment_dir,
        project_root=project_root,
    )
    gateway._telegram_send = stub_send
    gateway.daemon_client = backend  # type: ignore[attr-defined]
    return gateway


async def test_plain_text_dispatched_immediately(session_map: SessionMap, tmp_path: Path) -> None:
    """Single text message with empty buffer — submit_run runs at once,
    no debounce delay (instant interactive feel)."""
    sends: list[tuple[str, dict[str, Any]]] = []
    gateway = _gateway_with_attachments(session_map, tmp_path, sends)
    await gateway._handle_update(_message_update(42, "hello"))
    # No buffer left behind for the chat.
    assert gateway._buffers == {}
    assert gateway.daemon_client.calls
    prompt, _sid = gateway.daemon_client.calls[0]
    assert prompt == "hello"


async def test_forward_then_comment_merged_into_one_turn(
    session_map: SessionMap, tmp_path: Path
) -> None:
    """Forwarded post + user's comment — one prompt, one submit_run.
    The comment goes first (user intent), the forwarded body second as
    a quote so the agent sees what it's commenting on."""
    sends: list[tuple[str, dict[str, Any]]] = []
    gateway = _gateway_with_attachments(session_map, tmp_path, sends)
    # 1. Forwarded post — buffers, no instant dispatch.
    await gateway._handle_update(
        {
            "update_id": 1,
            "message": {
                "chat": {"id": 42, "type": "private"},
                "forward_from_chat": {"title": "Indie News", "type": "channel"},
                "text": "Breaking: cats can program",
            },
        }
    )
    assert "42" in gateway._buffers
    assert gateway.daemon_client.calls == []
    # 2. User's comment lands within the window.
    await gateway._handle_update(_message_update(42, "what do you think?"))
    # 3. Drive the debounce: flush manually (timer would also fire after 1.5s).
    await gateway._flush_buffer("42")
    assert len(gateway.daemon_client.calls) == 1
    prompt, _sid = gateway.daemon_client.calls[0]
    # Forwarded block first (it's the context), comment second (the
    # user's reaction to that context) — the order matches the human
    # reading order in Telegram.
    assert "↪️ Forwarded from Indie News:" in prompt
    assert "> Breaking: cats can program" in prompt
    assert "what do you think?" in prompt
    assert prompt.index("Breaking") < prompt.index("what do you think?")


async def test_document_then_comment_merged(
    session_map: SessionMap, tmp_path: Path, monkeypatch
) -> None:
    """Document + text in the same window → one turn, comment in prompt,
    file saved and referenced as attachment."""
    sends: list[tuple[str, dict[str, Any]]] = []
    gateway = _gateway_with_attachments(session_map, tmp_path, sends)

    async def fake_download(self, file_id: str, expected_size: int) -> bytes:
        return b"# Notes\nsome content"

    monkeypatch.setattr(TelegramGateway, "_download_telegram_file", fake_download)

    await gateway._handle_update(
        {
            "update_id": 1,
            "message": {
                "chat": {"id": 42, "type": "private"},
                "document": {
                    "file_id": "ABC",
                    "file_name": "notes.md",
                    "mime_type": "text/markdown",
                    "file_size": 100,
                },
            },
        }
    )
    await gateway._handle_update(_message_update(42, "summarise"))
    await gateway._flush_buffer("42")
    assert len(gateway.daemon_client.calls) == 1
    prompt, _sid = gateway.daemon_client.calls[0]
    assert prompt.startswith("summarise")
    assert ".veles/tmp/" in prompt
    assert "notes.md" in prompt
    # The file was actually persisted.
    saved = list((tmp_path / ".veles" / "tmp").iterdir())
    assert len(saved) == 1
    assert saved[0].read_bytes() == b"# Notes\nsome content"


async def test_document_too_large_rejected(
    session_map: SessionMap, tmp_path: Path, monkeypatch
) -> None:
    """Bigger than 5 MB → reject, no download, no submit_run."""
    sends: list[tuple[str, dict[str, Any]]] = []
    gateway = _gateway_with_attachments(session_map, tmp_path, sends)

    async def boom(self, *_a: Any, **_k: Any) -> bytes:
        raise AssertionError("must not download oversized file")

    monkeypatch.setattr(TelegramGateway, "_download_telegram_file", boom)
    await gateway._handle_update(
        {
            "update_id": 1,
            "message": {
                "chat": {"id": 42, "type": "private"},
                "document": {
                    "file_id": "BIG",
                    "file_name": "huge.md",
                    "mime_type": "text/markdown",
                    "file_size": 10 * 1024 * 1024,
                },
            },
        }
    )
    await gateway._flush_buffer("42")
    # User got a reject message; agent was not invoked.
    rejects = [p["text"] for m, p in sends if m == "sendMessage"]
    assert any("larger than 5 MB" in r for r in rejects)
    assert gateway.daemon_client.calls == []


async def test_document_non_textual_rejected(
    session_map: SessionMap, tmp_path: Path, monkeypatch
) -> None:
    sends: list[tuple[str, dict[str, Any]]] = []
    gateway = _gateway_with_attachments(session_map, tmp_path, sends)

    async def boom(self, *_a: Any, **_k: Any) -> bytes:
        raise AssertionError("must not download binary file")

    monkeypatch.setattr(TelegramGateway, "_download_telegram_file", boom)
    await gateway._handle_update(
        {
            "update_id": 1,
            "message": {
                "chat": {"id": 42, "type": "private"},
                "document": {
                    "file_id": "PDF",
                    "file_name": "manual.pdf",
                    "mime_type": "application/pdf",
                    "file_size": 1024,
                },
            },
        }
    )
    await gateway._flush_buffer("42")
    rejects = [p["text"] for m, p in sends if m == "sendMessage"]
    assert any("only handle text files" in r for r in rejects)
    assert gateway.daemon_client.calls == []


async def test_buffer_caps_at_five_messages_flushes_immediately(
    session_map: SessionMap, tmp_path: Path
) -> None:
    """A flood of 5+ forwards in one window flushes early — the user
    doesn't wait 10+ seconds if their finger gets stuck on the share
    button."""
    sends: list[tuple[str, dict[str, Any]]] = []
    gateway = _gateway_with_attachments(session_map, tmp_path, sends)
    for i in range(5):
        await gateway._handle_update(
            {
                "update_id": 100 + i,
                "message": {
                    "chat": {"id": 42, "type": "private"},
                    "forward_from_chat": {"title": f"Chan{i}"},
                    "text": f"Post {i}",
                },
            }
        )
    # Hard cap reached → flush without waiting.
    assert "42" not in gateway._buffers
    assert len(gateway.daemon_client.calls) == 1
    prompt, _sid = gateway.daemon_client.calls[0]
    for i in range(5):
        assert f"Post {i}" in prompt


# ---- M210: getUpdates backoff + log suppression ----


async def test_poll_loop_backs_off_and_suppresses_repeat_warnings(
    session_map: SessionMap, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """An offline machine fails every poll with the same error: one WARNING
    (not one per ~2s retry — a real offline hour used to log ~1800 identical
    lines) and exponentially growing sleeps capped at 60s."""
    import logging

    sends: list[tuple[str, dict[str, Any]]] = []
    gateway = _make_gateway(_FakeDaemonClient(), session_map, sends)

    async def _net_down(method: str, payload: dict[str, Any]) -> dict[str, Any]:
        raise RuntimeError("Cannot connect to host api.telegram.org:443")

    gateway._telegram_send = _net_down
    gateway._running = True
    delays: list[float] = []

    async def _instant_sleep(seconds: float) -> None:
        delays.append(seconds)
        if len(delays) >= 6:
            gateway._running = False

    monkeypatch.setattr(asyncio, "sleep", _instant_sleep)
    with caplog.at_level(logging.INFO, logger="veles.channels.telegram._gateway"):
        await gateway._poll_loop()

    assert delays == [2, 4, 8, 16, 32, 60]
    warnings = [r for r in caplog.records if "getUpdates failed" in r.getMessage()]
    assert len(warnings) == 1


async def test_poll_loop_logs_recovery_and_resets_backoff(
    session_map: SessionMap, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    import logging

    sends: list[tuple[str, dict[str, Any]]] = []
    gateway = _make_gateway(_FakeDaemonClient(), session_map, sends)
    calls = {"n": 0}

    async def _flaky(method: str, payload: dict[str, Any]) -> dict[str, Any]:
        calls["n"] += 1
        if calls["n"] <= 2:
            raise RuntimeError("boom")
        gateway._running = False  # one successful poll, then stop
        return {"raw": []}

    gateway._telegram_send = _flaky
    gateway._running = True
    delays: list[float] = []

    async def _instant_sleep(seconds: float) -> None:
        delays.append(seconds)

    monkeypatch.setattr(asyncio, "sleep", _instant_sleep)
    with caplog.at_level(logging.INFO, logger="veles.channels.telegram._gateway"):
        await gateway._poll_loop()

    assert delays == [2, 4]
    recoveries = [r for r in caplog.records if "recovered after 2 failed polls" in r.getMessage()]
    assert len(recoveries) == 1


async def test_poll_loop_formats_bare_timeouts_and_logs_error_changes(
    session_map: SessionMap, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """A bare `TimeoutError` has an empty str() — the log line used to end at
    `getUpdates failed:` with no reason. Fall back to repr; a *change* of
    error text is logged even mid-suppression, a repeat is not."""
    import logging

    sends: list[tuple[str, dict[str, Any]]] = []
    gateway = _make_gateway(_FakeDaemonClient(), session_map, sends)
    errors: list[Exception] = [RuntimeError("dns down"), TimeoutError(), TimeoutError()]

    async def _mixed(method: str, payload: dict[str, Any]) -> dict[str, Any]:
        if errors:
            raise errors.pop(0)
        gateway._running = False
        return {"raw": []}

    gateway._telegram_send = _mixed
    gateway._running = True

    async def _instant_sleep(seconds: float) -> None:
        pass

    monkeypatch.setattr(asyncio, "sleep", _instant_sleep)
    with caplog.at_level(logging.INFO, logger="veles.channels.telegram._gateway"):
        await gateway._poll_loop()

    warnings = [r.getMessage() for r in caplog.records if "getUpdates failed" in r.getMessage()]
    assert len(warnings) == 2  # "dns down", then the changed text; repeat suppressed
    assert "dns down" in warnings[0]
    assert "TimeoutError()" in warnings[1]

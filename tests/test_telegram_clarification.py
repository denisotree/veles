"""M116c: Telegram clarification inline keyboards.

Manager-spawn emits `clarification_prompt` daemon events with an
arbitrary option list (one per `PromptOption`) plus an optional
freeform entry. Telegram renders them as an inline keyboard row,
maps the user's tap back to the daemon's key, and surfaces freeform
text replies through the existing `_finalise_prompt_message` path.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from veles.channels.session_map import SessionMap
from veles.channels.telegram import (
    TelegramGateway,
    _build_buttons,
    _format_prompt_body,
)


@pytest.fixture()
def session_map(tmp_path: Path) -> SessionMap:
    return SessionMap.load(tmp_path / "telegram-sessions.json")


# ---- _build_buttons for clarification ----


def test_clarification_buttons_use_index_shorts() -> None:
    """Trust/approval prompts use fixed short codes (o/p/g/r, y/n).
    Clarification prompts can have arbitrary option counts and
    arbitrary keys — so the short codes are plain integer indexes."""
    options = [
        {"key": "alpha", "label": "Variant A"},
        {"key": "beta", "label": "Variant B"},
        {"key": "free", "label": "Type my own"},
    ]
    shorts, buttons, mapping = _build_buttons("p1", "clarification", options)
    assert shorts == ["0", "1", "2"]
    assert mapping == {"0": "alpha", "1": "beta", "2": "free"}
    assert len(buttons) == 3
    assert buttons[0]["text"] == "Variant A"
    assert buttons[0]["callback_data"] == "v:p1:0"


def test_clarification_buttons_skip_malformed_options() -> None:
    options = [
        {"key": "ok", "label": "Good"},
        {"key": 12, "label": "Bad key"},  # non-string key
        "not a dict",
        {"key": "missing-label"},
    ]
    shorts, buttons, mapping = _build_buttons("p1", "clarification", options)
    assert shorts == ["0"]
    assert mapping == {"0": "ok"}
    assert len(buttons) == 1


def test_trust_buttons_still_use_fixed_shorts() -> None:
    """M116c doesn't change trust prompt encoding."""
    options = [
        {"key": "once", "label": "Once"},
        {"key": "refuse", "label": "Refuse"},
    ]
    shorts, _buttons, mapping = _build_buttons("p1", "trust", options)
    assert shorts == ["o", "r"]
    assert mapping == {"o": "once", "r": "refuse"}


def test_approval_buttons_still_use_fixed_shorts() -> None:
    options = [{"key": "yes", "label": "Yes"}, {"key": "no", "label": "No"}]
    shorts, _buttons, mapping = _build_buttons("p1", "approval", options)
    assert shorts == ["y", "n"]
    assert mapping == {"y": "yes", "n": "no"}


# ---- _format_prompt_body for clarification ----


def test_clarification_body_includes_question() -> None:
    event = {
        "type": "clarification_prompt",
        "question": "Which deploy target do you mean: staging or production?",
    }
    body = _format_prompt_body("clarification", event)
    assert "❓" in body
    assert "staging or production" in body


def test_clarification_body_sanitises_secrets() -> None:
    """Questions go through `core.sanitize` so secret-shaped text
    doesn't leak through the prompt body."""
    home = str(Path.home())
    event = {
        "type": "clarification_prompt",
        "question": f"Process file at {home}/secret/key.txt?",
    }
    body = _format_prompt_body("clarification", event)
    # `sanitize` replaces home prefix with `~`
    assert home not in body
    assert "~" in body


def test_clarification_body_handles_missing_question() -> None:
    body = _format_prompt_body("clarification", {"type": "clarification_prompt"})
    assert "no question" in body.lower()


def test_unrecognised_kind_falls_back_to_approval() -> None:
    """A kind the gateway doesn't know shouldn't crash — falls back
    to the approval shape (least permissive)."""
    body = _format_prompt_body(
        "unknown",
        {"type": "approval_prompt", "tool": "x", "reason": "y", "arguments": {}},
    )
    assert "Approval required" in body or "🔐" in body


# ---- integration via _post_prompt ----


def _make_gateway(session_map: SessionMap, sends: list[tuple[str, dict[str, Any]]]):
    """Stub gateway capturing _telegram_send calls (mirrors
    test_channels_telegram.py pattern)."""

    class _NullClient:
        async def submit_run(self, prompt: str, *, session_id=None):
            return {"run_id": "x", "session_id": session_id, "state": "running"}

        async def stream_events(self, run_id):
            if False:
                yield

    async def stub_send(method: str, payload: dict[str, Any]) -> dict[str, Any]:
        sends.append((method, payload))
        if method == "sendMessage":
            return {"message_id": 99, "chat": payload["chat_id"]}
        if method == "editMessageText":
            return {"edited": True, "message_id": payload["message_id"]}
        return {}

    gateway = TelegramGateway(
        bot_token="X",
        daemon_client=_NullClient(),  # type: ignore[arg-type]
        session_map=session_map,
    )
    gateway._telegram_send = stub_send
    return gateway


async def test_post_prompt_renders_clarification_keyboard(
    session_map: SessionMap,
) -> None:
    sends: list[tuple[str, dict[str, Any]]] = []
    gateway = _make_gateway(session_map, sends)
    event = {
        "type": "clarification_prompt",
        "prompt_id": "c1",
        "question": "Which env?",
        "options": [
            {"key": "staging", "label": "Staging"},
            {"key": "prod", "label": "Production"},
            {"key": "__free__", "label": "Type my own"},
        ],
    }
    await gateway._post_prompt(chat_id=42, run_id="r1", event=event)

    assert sends, "expected at least one sendMessage call"
    method, payload = sends[0]
    assert method == "sendMessage"
    assert "Which env?" in payload["text"]
    # Inline keyboard wired
    kb = payload["reply_markup"]["inline_keyboard"]
    assert len(kb) == 1
    row = kb[0]
    assert [b["text"] for b in row] == ["Staging", "Production", "Type my own"]
    assert all(b["callback_data"].startswith("v:c1:") for b in row)
    # Pending registry holds the mapping for the inbound callback
    assert "c1" in gateway._pending_prompts
    pending = gateway._pending_prompts["c1"]
    assert pending.kind == "clarification"
    assert pending.short_to_key == {"0": "staging", "1": "prod", "2": "__free__"}


async def test_callback_resolves_clarification_choice(
    session_map: SessionMap,
) -> None:
    """End-to-end: post clarification, simulate a button tap, verify
    daemon receives the canonical key back."""
    sends: list[tuple[str, dict[str, Any]]] = []
    submitted_answers: list[tuple[str, str]] = []

    class _RecordingClient:
        async def submit_run(self, prompt: str, *, session_id=None):
            return {"run_id": "x", "session_id": session_id, "state": "running"}

        async def stream_events(self, run_id):
            if False:
                yield

        async def submit_prompt_answer(self, run_id: str, prompt_id: str, key: str):
            submitted_answers.append((prompt_id, key))
            return {"ok": True}

    async def stub_send(method: str, payload: dict[str, Any]) -> dict[str, Any]:
        sends.append((method, payload))
        if method == "sendMessage":
            return {"message_id": 99, "chat": payload["chat_id"]}
        return {"ok": True}

    gateway = TelegramGateway(
        bot_token="X",
        daemon_client=_RecordingClient(),  # type: ignore[arg-type]
        session_map=session_map,
    )
    gateway._telegram_send = stub_send

    event = {
        "type": "clarification_prompt",
        "prompt_id": "c1",
        "question": "Pick one",
        "options": [
            {"key": "alpha", "label": "Alpha"},
            {"key": "beta", "label": "Beta"},
        ],
    }
    await gateway._post_prompt(chat_id=42, run_id="r1", event=event)

    # Simulate user tap on the second button (Beta → short "1" → key "beta")
    callback = {
        "id": "cb1",
        "data": "v:c1:1",
        "from": {"id": 42},
        "message": {"chat": {"id": 42}, "message_id": 99},
    }
    await gateway._handle_callback_query(callback)
    assert submitted_answers == [("c1", "beta")]

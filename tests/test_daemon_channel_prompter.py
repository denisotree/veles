"""`make_unified_prompter` builds a PromptRequest-based prompter whose
answers come from a channel client (Telegram, etc.) via the run's
event stream.

The prompter blocks on a `concurrent.futures.Future` that the daemon's
HTTP endpoint resolves when the client POSTs a choice. These tests
drive the prompter on a worker thread and resolve the future from the
asyncio loop — same shape as the production wiring."""

from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor

import pytest

from veles.core.permission.prompt import PromptAnswer, PromptRequest
from veles.daemon.channel_prompter import make_unified_prompter
from veles.daemon.runner import RunHandle


def _new_handle() -> RunHandle:
    return RunHandle(run_id="run-test", session_id=None)


def _trust_req(tool: str = "Bash", **kwargs) -> PromptRequest:
    return PromptRequest(
        tool_name=tool,
        arguments=kwargs.pop("arguments", {}),
        reason=kwargs.pop("reason", ""),
        kind="trust",
    )


def _approval_req(
    tool: str = "Write", arguments: dict | None = None, reason: str = ""
) -> PromptRequest:
    return PromptRequest(
        tool_name=tool,
        arguments=arguments or {},
        reason=reason,
        kind="approval",
    )


async def _run_prompter_on_thread(prompter, req):
    """Mirror the daemon: prompter runs on a worker thread, the test
    drives the event loop in parallel."""
    return await asyncio.to_thread(prompter, req)


@pytest.mark.asyncio
async def test_trust_prompt_emits_event_and_returns_resolved_choice() -> None:
    handle = _new_handle()
    loop = asyncio.get_running_loop()
    prompter = make_unified_prompter(handle, loop, timeout=5.0)

    task = asyncio.create_task(_run_prompter_on_thread(prompter, _trust_req("Bash")))
    # Wait for the event to land in the buffer.
    for _ in range(50):
        if handle.events:
            break
        await asyncio.sleep(0.01)
    assert handle.events, "trust_prompt event never emitted"
    event = handle.events[0]
    assert event["type"] == "trust_prompt"
    assert event["tool"] == "Bash"
    assert {opt["key"] for opt in event["options"]} == {
        "once",
        "always_project",
        "refuse",
    }
    # Labels carry emoji prefixes so the inline keyboard isn't a wall
    # of grey text — keys stay machine-readable, labels stay human.
    labels = {opt["key"]: opt["label"] for opt in event["options"]}
    assert labels["once"].startswith("⏱")
    assert labels["always_project"].startswith("🔓")
    assert labels["refuse"].startswith("🚫")

    prompt_id = event["prompt_id"]
    pending = handle.pending_prompts[prompt_id]
    pending.future.set_result("always_project")

    answer = await task
    assert answer == PromptAnswer("allow_project")


@pytest.mark.asyncio
async def test_trust_prompt_carries_arguments_and_reason() -> None:
    handle = _new_handle()
    loop = asyncio.get_running_loop()
    prompter = make_unified_prompter(handle, loop, timeout=5.0)
    req = _trust_req("run_shell", arguments={"cmd": "ls"}, reason="listing files")
    task = asyncio.create_task(_run_prompter_on_thread(prompter, req))
    for _ in range(50):
        if handle.events:
            break
        await asyncio.sleep(0.01)
    event = handle.events[0]
    assert event["arguments"] == {"cmd": "ls"}
    assert event["reason"] == "listing files"
    handle.pending_prompts[event["prompt_id"]].future.set_result("once")
    assert await task == PromptAnswer("allow_once")


@pytest.mark.asyncio
async def test_trust_prompt_unknown_key_falls_back_to_deny() -> None:
    handle = _new_handle()
    loop = asyncio.get_running_loop()
    prompter = make_unified_prompter(handle, loop, timeout=5.0)
    task = asyncio.create_task(_run_prompter_on_thread(prompter, _trust_req("Bash")))
    for _ in range(50):
        if handle.pending_prompts:
            break
        await asyncio.sleep(0.01)
    pid = next(iter(handle.pending_prompts))
    handle.pending_prompts[pid].future.set_result("garbage-key")
    assert await task == PromptAnswer("deny")


def test_trust_prompt_timeout_returns_deny_and_cleans_up() -> None:
    """Use a sync executor so we can run the prompter with a tiny
    timeout without the test session waiting on it."""
    handle = _new_handle()
    loop = asyncio.new_event_loop()
    try:
        prompter = make_unified_prompter(handle, loop, timeout=0.05)
        with ThreadPoolExecutor(max_workers=1) as pool:
            fut = pool.submit(prompter, _trust_req("Bash"))
            answer = fut.result(timeout=2.0)
        assert answer == PromptAnswer("deny")
        # The prompter must remove its own entry on timeout.
        assert handle.pending_prompts == {}
    finally:
        loop.close()


@pytest.mark.asyncio
async def test_approval_prompt_emits_event_and_returns_allow_once() -> None:
    handle = _new_handle()
    loop = asyncio.get_running_loop()
    prompter = make_unified_prompter(handle, loop, timeout=5.0)
    task = asyncio.create_task(
        _run_prompter_on_thread(
            prompter,
            _approval_req("Write", arguments={"path": "/etc/x"}, reason="writes outside project"),
        )
    )
    for _ in range(50):
        if handle.pending_prompts:
            break
        await asyncio.sleep(0.01)
    event = handle.events[0]
    assert event["type"] == "approval_prompt"
    assert event["tool"] == "Write"
    assert event["arguments"] == {"path": "/etc/x"}
    assert {opt["key"] for opt in event["options"]} == {"yes", "no"}
    # Approval buttons carry ✅/❌ for at-a-glance scanning.
    labels = {opt["key"]: opt["label"] for opt in event["options"]}
    assert labels["yes"].startswith("✅")
    assert labels["no"].startswith("❌")
    pid = event["prompt_id"]
    handle.pending_prompts[pid].future.set_result("yes")
    answer = await task
    assert answer == PromptAnswer("allow_once")
    assert answer.approved is True


@pytest.mark.asyncio
async def test_approval_prompt_no_returns_deny() -> None:
    handle = _new_handle()
    loop = asyncio.get_running_loop()
    prompter = make_unified_prompter(handle, loop, timeout=5.0)
    task = asyncio.create_task(_run_prompter_on_thread(prompter, _approval_req("Write")))
    for _ in range(50):
        if handle.pending_prompts:
            break
        await asyncio.sleep(0.01)
    pid = next(iter(handle.pending_prompts))
    handle.pending_prompts[pid].future.set_result("no")
    answer = await task
    assert answer == PromptAnswer("deny")
    assert answer.approved is False


@pytest.mark.asyncio
async def test_unknown_kind_denies_without_event() -> None:
    handle = _new_handle()
    loop = asyncio.get_running_loop()
    prompter = make_unified_prompter(handle, loop, timeout=5.0)
    req = PromptRequest(tool_name="X", arguments={}, kind="bogus")  # type: ignore[arg-type]
    answer = await asyncio.to_thread(prompter, req)
    assert answer == PromptAnswer("deny")
    assert handle.events == []

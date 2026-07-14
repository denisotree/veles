"""M214 — end-to-end proactive delivery: dream discovers a dated event, it is
materialised as a reminder, the sweep resolves the last active channel, and the
notice is delivered. Chains the seams the unit tests cover in isolation.
"""

from __future__ import annotations

import datetime as _dt
from pathlib import Path

from veles.channels.session_map import SessionMap, channel_session_path
from veles.core.dreaming import DreamResult, _step_proactive_events
from veles.core.proactive.delivery_log import DeliveryLog
from veles.core.proactive.target_resolver import last_active_target
from veles.core.project import init_project
from veles.core.provider import ProviderResponse, TokenUsage
from veles.core.reminder_runner import ReminderRunner
from veles.core.tasks_store import TasksStore

_NOW = _dt.datetime(2026, 7, 14, 22, 0, tzinfo=_dt.UTC).timestamp()


class _FakeProvider:
    supports_tools = False

    def __init__(self, reply: str) -> None:
        self._reply = reply

    def create_message(self, messages, tools=None, *, model, max_tokens=4096) -> ProviderResponse:
        return ProviderResponse(text=self._reply, tool_calls=[], usage=TokenUsage())


class _RecordingRouter:
    def __init__(self) -> None:
        self.sent: list[tuple[str, str]] = []

    async def deliver(self, target, text):
        self.sent.append((target, text))


async def test_dream_to_delivery_end_to_end(tmp_path: Path):
    project = init_project(tmp_path / "proj", name="p")
    when = _dt.datetime.fromtimestamp(_NOW + 60, tz=_dt.UTC).isoformat()
    reply = f'[{{"title": "BC GAME live processing", "when": "{when}", "note": "merchant"}}]'

    # 1) dream discovers + materialises the definite event (no delivery target yet)
    _step_proactive_events(
        project,
        _FakeProvider(reply),
        "stub",
        lambda: "user: turn on BC GAME live tonight",
        DreamResult(),
        now=_NOW,
        dry_run=False,
    )

    # 2) a chat becomes active (SessionMap under a base_dir we control)
    maps_dir = tmp_path / "channels"
    smap = SessionMap.load(channel_session_path("telegram", base_dir=maps_dir))
    smap.set("telegram:4242", "sess-1")

    # 3) the sweep resolves the last active channel and delivers the notice
    router = _RecordingRouter()
    log = DeliveryLog(":memory:")
    runner = ReminderRunner(
        store=TasksStore(project.memory_db_path),
        delivery_router=router,
        target_resolver=lambda: last_active_target(["telegram"], base_dir=maps_dir),
        delivery_log=log,
    )
    delivered = await runner.tick(now=_NOW + 120)

    assert delivered == 1
    assert router.sent == [("telegram:4242", "⏰ BC GAME live processing\n\nmerchant")]
    assert [a.ok for a in log.recent()] == [True]
    # idempotent: a second sweep does not re-deliver
    assert await runner.tick(now=_NOW + 180) == 0
    await runner.stop()
    log.close()

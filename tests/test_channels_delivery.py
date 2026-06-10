"""M74 — DeliveryTarget parser and DeliveryRouter dispatch."""

from __future__ import annotations

import pytest

from veles.channels import platform_registry as pr
from veles.channels.delivery import DeliveryError, DeliveryRouter, DeliveryTarget


@pytest.fixture(autouse=True)
def _isolated_registry():
    snapshot = dict(pr._REGISTRY)
    pr._reset_registry_for_tests()
    yield
    pr._reset_registry_for_tests()
    pr._REGISTRY.update(snapshot)


# ---- DeliveryTarget.parse ----


def test_parse_local():
    t = DeliveryTarget.parse("local")
    assert t.kind == "local"
    assert t.platform is None
    assert t.render() == "local"


def test_parse_origin():
    t = DeliveryTarget.parse("origin")
    assert t.kind == "origin"
    assert t.render() == "origin"


def test_parse_platform_chat():
    t = DeliveryTarget.parse("telegram:42")
    assert t.kind == "platform"
    assert t.platform == "telegram"
    assert t.chat_id == "42"
    assert t.thread_id is None
    assert t.render() == "telegram:42"


def test_parse_platform_with_thread():
    t = DeliveryTarget.parse("slack:C01:1700.000")
    assert t.kind == "platform"
    assert t.platform == "slack"
    assert t.chat_id == "C01"
    assert t.thread_id == "1700.000"
    assert t.render() == "slack:C01:1700.000"


def test_parse_empty_raises():
    with pytest.raises(ValueError):
        DeliveryTarget.parse("")
    with pytest.raises(ValueError):
        DeliveryTarget.parse("   ")


def test_parse_invalid_shape_raises():
    with pytest.raises(ValueError):
        DeliveryTarget.parse("just-a-name")
    with pytest.raises(ValueError):
        DeliveryTarget.parse(":no-platform")
    with pytest.raises(ValueError):
        DeliveryTarget.parse("telegram:")


# ---- DeliveryRouter ----


async def test_local_sink_called():
    received: list[str] = []
    router = DeliveryRouter(local_sink=received.append)
    info = await router.deliver("local", "hello")
    assert info == {"kind": "local", "delivered": True}
    assert received == ["hello"]


async def test_local_without_sink_reports_no_handler():
    router = DeliveryRouter()
    info = await router.deliver("local", "hello")
    assert info["delivered"] is False
    assert "no local_sink" in str(info["reason"])


async def test_origin_handler_called():
    captured: list[str] = []

    async def handler(text: str) -> None:
        captured.append(text)

    router = DeliveryRouter(origin_handler=handler)
    info = await router.deliver("origin", "ping")
    assert info["delivered"] is True
    assert captured == ["ping"]


async def test_origin_without_handler_raises():
    router = DeliveryRouter()
    with pytest.raises(DeliveryError):
        await router.deliver("origin", "ping")


async def test_platform_deliverer_dispatch():
    pr.register_platform("fake", lambda **_: None)
    seen: list[tuple[str, str, str | None]] = []

    async def deliverer(chat_id: str, text: str, thread_id: str | None) -> None:
        seen.append((chat_id, text, thread_id))

    router = DeliveryRouter()
    router.register_deliverer("fake", deliverer)
    info = await router.deliver("fake:42:thr", "hi")
    assert info == {"kind": "platform", "platform": "fake", "delivered": True}
    assert seen == [("42", "hi", "thr")]


async def test_platform_unregistered_raises():
    router = DeliveryRouter()
    with pytest.raises(DeliveryError) as excinfo:
        await router.deliver("nope:42", "hi")
    assert "nope" in str(excinfo.value)


async def test_platform_registered_but_no_deliverer_raises():
    pr.register_platform("fake", lambda **_: None)
    router = DeliveryRouter()
    with pytest.raises(DeliveryError) as excinfo:
        await router.deliver("fake:42", "hi")
    assert "no deliverer" in str(excinfo.value)

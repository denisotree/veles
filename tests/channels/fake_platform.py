"""A channel platform for tests: its gateway records what it is asked to deliver.

Core tests use it instead of a real platform; `register(api)` makes it a module
like any other (the `fake_platform` fixture in `tests/conftest.py` loads it)."""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass, field

from veles.core.platforms import ChannelCaps, ChannelContext, CredField, PlatformSpec


@dataclass
class FakeGateway:
    ctx: ChannelContext
    sent: list[tuple[str, str]] = field(default_factory=list)
    started: bool = False

    async def start(self) -> None:
        self.started = True

    async def stop(self) -> None:
        self.started = False

    async def deliver(self, chat_id: str, text: str, thread_id: str | None = None) -> None:
        self.sent.append((chat_id, text))


def fake_spec(secret_key: str = "token") -> PlatformSpec:
    return PlatformSpec(
        build=FakeGateway,
        caps=ChannelCaps(asks_questions=True),
        cred_fields=(
            CredField(secret_key, "Fake token", secret=True, required=True, env="FAKE_TOKEN"),
            CredField("rooms", "Allowed rooms, comma-separated", list_value=True),
        ),
        config_keys=frozenset({"room"}),
    )


FAKE_SPEC = fake_spec()


def register(api) -> None:
    api.contribute("platform", "fake", FAKE_SPEC)


@contextmanager
def contributing(specs: Mapping[str, PlatformSpec]) -> Iterator[None]:
    """A live module registry whose module contributes `specs` (name → spec)."""
    from veles.core.modules import (
        ModuleAPI,
        ModuleRegistry,
        reset_module_registry,
        set_module_registry,
    )

    scratch, registry = ModuleRegistry(), ModuleRegistry()
    api = ModuleAPI(scratch, "fake-channels")
    for name, spec in specs.items():
        api.contribute("platform", name, spec)
    registry.merge_from(scratch, "fake-channels")
    token = set_module_registry(registry)
    try:
        yield
    finally:
        reset_module_registry(token)

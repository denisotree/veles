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


def install_as_user_module(name: str = "fakech") -> None:
    """This file as an approved user-level module (what a registry install leaves
    behind) — for paths that load modules themselves instead of reading a live
    registry. Needs an isolated user home."""
    from pathlib import Path

    from veles.core.registry.gate import approve_module
    from veles.core.user_paths import user_modules_dir

    mod = user_modules_dir() / name
    mod.mkdir(parents=True)
    (mod / "module.toml").write_text(
        f'[module]\nname = "{name}"\ndescription = "d"\nentrypoint = "e.py:register"\n',
        encoding="utf-8",
    )
    (mod / "e.py").write_text(Path(__file__).read_text(encoding="utf-8"), encoding="utf-8")
    approve_module(mod, name=name, project_root=None)


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

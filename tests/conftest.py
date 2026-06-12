"""Project-wide test fixtures and shared stubs.

M-R1.8: consolidates three near-identical `_FakeKeyring` stubs and
the `VELES_USER_HOME` isolation pattern (10+ test files) into shared
fixtures.

M150: adds the canonical `StubProvider` (was copy-pasted as
`_StubProvider` in ~23 test files) and `FakeAgent` (was `_FakeAgent`
in 7 files). Import them directly:

    from tests.conftest import StubProvider, FakeAgent
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest


class StubProvider:
    """Canonical scripted Provider stub.

    - ``responses``: ProviderResponse objects consumed one per
      ``create_message`` call. When exhausted: repeat the last one if
      ``repeat_last=True``, otherwise raise AssertionError (a test that
      triggers more provider calls than it scripted is a bug).
    - ``calls``: every ``create_message``/``stream_message`` invocation is
      recorded as a dict (messages/tools/model/max_tokens/stream).
    - ``stream_events``: optional list of StreamEvent objects replayed by
      ``stream_message``; if not given, ``stream_message`` raises
      NotImplementedError (matching the historical copies).

    Deliberately free of veles imports — tests supply the response/event
    objects themselves.
    """

    def __init__(
        self,
        responses: list[Any] | None = None,
        *,
        name: str = "stub",
        supports_tools: bool = True,
        supports_streaming: bool = False,
        stream_events: list[Any] | None = None,
        repeat_last: bool = False,
    ) -> None:
        self.responses = list(responses or [])
        self.name = name
        self.supports_tools = supports_tools
        self.supports_streaming = supports_streaming
        self.stream_events = list(stream_events) if stream_events is not None else None
        self.repeat_last = repeat_last
        self.calls: list[dict[str, Any]] = []
        self._idx = 0

    def create_message(
        self,
        messages=None,
        tools=None,
        *,
        model: str = "stub-model",
        max_tokens: int = 4096,
    ):
        # Snapshot: the agent mutates its history list in place between calls.
        self.calls.append(
            {
                "messages": list(messages) if messages is not None else None,
                "tools": list(tools) if tools is not None else None,
                "model": model,
                "max_tokens": max_tokens,
                "stream": False,
            }
        )
        if self._idx >= len(self.responses):
            if self.repeat_last and self.responses:
                return self.responses[-1]
            raise AssertionError(
                f"StubProvider exhausted: create_message call #{self._idx + 1} "
                f"but only {len(self.responses)} response(s) scripted"
            )
        resp = self.responses[self._idx]
        self._idx += 1
        return resp

    def stream_message(
        self,
        messages=None,
        tools=None,
        *,
        model: str = "stub-model",
        max_tokens: int = 4096,
    ):
        if self.stream_events is None:
            raise NotImplementedError("StubProvider: no stream_events scripted")
        self.calls.append(
            {
                "messages": list(messages) if messages is not None else None,
                "tools": list(tools) if tools is not None else None,
                "model": model,
                "max_tokens": max_tokens,
                "stream": True,
            }
        )
        yield from self.stream_events


class FakeAgent:
    """Canonical Agent stand-in: returns scripted RunResult(s) from ``run``.

    - ``result`` / ``results``: a single result repeats forever; a list is
      consumed in order with the last one repeating.
    - Records ``seen_prompt`` (last), ``prompts`` (all), plus the last
      ``on_text_delta`` / ``event_listener`` callbacks as ``seen_on_text`` /
      ``seen_on_event``.
    - Extra keyword attrs (e.g. ``provider=...``, ``captured_extra_system=...``)
      are setattr'd onto the instance for tests that need them.
    """

    def __init__(
        self,
        result: Any | None = None,
        *,
        results: list[Any] | None = None,
        provider: Any | None = None,
        **attrs: Any,
    ) -> None:
        if results is not None:
            self.results = list(results)
        elif result is not None:
            self.results = [result]
        else:
            self.results = []
        self.provider = provider
        self.seen_prompt: str | None = None
        self.prompts: list[str] = []
        self.seen_on_text: Any = None
        self.seen_on_event: Any = None
        self._idx = 0
        for key, value in attrs.items():
            setattr(self, key, value)

    def run(self, prompt: str, *, on_text_delta=None, event_listener=None, **_kw):
        self.seen_prompt = prompt
        self.prompts.append(prompt)
        self.seen_on_text = on_text_delta
        self.seen_on_event = event_listener
        if not self.results:
            raise AssertionError("FakeAgent.run called with no scripted results")
        res = self.results[min(self._idx, len(self.results) - 1)]
        self._idx += 1
        return res


_PROVIDER_ENV_VARS: tuple[str, ...] = (
    "OPENROUTER_API_KEY",
    "ANTHROPIC_API_KEY",
    "OPENAI_API_KEY",
    "GEMINI_API_KEY",
    "GOOGLE_API_KEY",
)


class FakeKeyring:
    """Dict-backed stand-in for the OS keychain.

    Mirrors the interface `core/secrets.py` actually consults — the
    real `keyring` module's `get_password`/`set_password`/`delete_password`
    plus a nested `errors` namespace with the two exception classes our
    code references. Tests use it through the `fake_keyring` fixture,
    which patches `veles.core.secrets._keyring` to return an instance.
    """

    class _Errs:
        class KeyringError(Exception):
            pass

        class PasswordDeleteError(Exception):
            pass

    errors = _Errs()

    def __init__(self) -> None:
        self.store: dict[tuple[str, str], str] = {}

    # `keyring`-compatible API ------------------------------------------------

    def get_password(self, service: str, name: str) -> str | None:
        return self.store.get((service, name))

    def set_password(self, service: str, name: str, value: str) -> None:
        self.store[(service, name)] = value

    def delete_password(self, service: str, name: str) -> None:
        if (service, name) not in self.store:
            raise self._Errs.PasswordDeleteError("no such entry")
        del self.store[(service, name)]


@pytest.fixture(autouse=True)
def _hermetic_user_home(
    tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Point `VELES_USER_HOME` at a fresh empty dir for *every* test (M125).

    Before M125 nothing on the agent hot path read `~/.veles/config.toml`
    in a way tests cared about, so they silently inherited the developer's
    real home. M125 made `route()` consult the user-level `[routing.tasks]`
    / `[user]` base, so a developer whose real `~/.veles/config.toml` sets
    `default_provider = "openai"` saw routing tests resolve to *their*
    model instead of the hardcoded default — green locally only by luck of
    an empty home. This autouse isolation makes the user scope empty by
    default; tests that need a populated user home (`isolated_user_home`,
    or their own `monkeypatch.setenv`) override it within the test body.

    Deliberately does NOT clear provider API-key env vars — that would
    change key-presence behaviour for unrelated tests; only the user
    *config file* scope is isolated here."""
    home_root = tmp_path_factory.mktemp("veles-user-home")
    monkeypatch.setenv("VELES_USER_HOME", str(home_root))


@pytest.fixture
def fake_keyring(monkeypatch: pytest.MonkeyPatch) -> FakeKeyring:
    """Install a FakeKeyring instance into `veles.core.secrets`.

    Pair with `isolated_user_home` when you also need the sidecar
    index file (`~/.veles/secrets.index.json`) to land in a tmp
    directory."""
    from veles.core import secrets

    kr = FakeKeyring()
    monkeypatch.setattr(secrets, "_keyring", lambda: (kr, kr.errors))
    return kr


@pytest.fixture(autouse=True)
def _in_memory_keyring() -> Iterator[None]:
    """Give every test a working in-memory OS-keyring backend.

    Headless CI (and some Linux dev boxes) ship no keyring backend, so any
    test that drives the real `keyring` path — storing a Telegram bot token,
    starting a channel gateway — died with `KeyringUnavailable`. The suite
    only passed on a maintainer's macOS box with a live Keychain.

    A fresh in-memory store per test keeps secrets from leaking across
    tests. Tests that need the keyring to *fail* (or want the tmp-isolated
    sidecar index) patch `secrets._keyring` themselves, which overrides this.
    """
    import keyring
    from keyring.backend import KeyringBackend

    class _InMemory(KeyringBackend):
        priority = 1  # type: ignore[assignment]

        def __init__(self) -> None:
            super().__init__()
            self._data: dict[tuple[str, str], str] = {}

        def get_password(self, service: str, username: str) -> str | None:
            return self._data.get((service, username))

        def set_password(self, service: str, username: str, password: str) -> None:
            self._data[(service, username)] = password

        def delete_password(self, service: str, username: str) -> None:
            from keyring.errors import PasswordDeleteError

            try:
                del self._data[(service, username)]
            except KeyError as exc:
                raise PasswordDeleteError("not found") from exc

    prev = keyring.get_keyring()
    keyring.set_keyring(_InMemory())
    try:
        yield
    finally:
        keyring.set_keyring(prev)


@pytest.fixture
def isolated_user_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """Point `VELES_USER_HOME` at a fresh temp dir and clear provider
    env vars so tests don't inherit a real user's key from the shell.

    Returns the `.veles/` subdirectory (where Veles writes daemon
    PID files, daemon logs, the token store, etc.) — the same shape
    the migrated `test_daemon_cli.py::isolated_user_home` exposes."""
    home_root = tmp_path / "veles-home"
    home_root.mkdir(exist_ok=True)
    monkeypatch.setenv("VELES_USER_HOME", str(home_root))
    for env in _PROVIDER_ENV_VARS:
        monkeypatch.delenv(env, raising=False)
    veles_dir = home_root / ".veles"
    veles_dir.mkdir(exist_ok=True)
    yield veles_dir

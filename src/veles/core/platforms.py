"""Channel platforms — the contract a channel module implements and what its
gateway talks to.

`RunBackend` is what a gateway needs from the daemon: `DaemonClient` (HTTP
loopback) and `InProcessRunBackend` (asyncio dispatch inside the daemon) both
implement it. It lives in core so `veles.sdk` can hand it to channel modules.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable, Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

from veles.core.chat_sessions import SessionMap

if TYPE_CHECKING:
    from veles.core.project import Project


class RunBackendError(RuntimeError):
    """A run backend (the HTTP daemon client or the in-process one) failed a request."""


@runtime_checkable
class RunBackend(Protocol):
    """What a channel gateway needs from the daemon: submit a prompt, follow its
    event stream, answer its prompts, and read or change the chat's session."""

    async def submit_run(
        self,
        prompt: str,
        *,
        session_id: str | None = None,
        origin: str | None = None,
        mode: str | None = None,
    ) -> dict[str, Any]:
        """POST one turn. Returns at least `{"run_id": ..., "session_id": ...}`.

        `origin` (M166) is the originating chat as a delivery target
        (e.g. "telegram:<id>") so reminder tools can default to "this chat".
        `mode` (M280b) switches the session's agent mode first."""
        ...

    def stream_events(self, run_id: str) -> AsyncIterator[dict[str, Any]]:
        """Yield typed event dicts until the run completes or errors.

        Events: `started`, `text_delta`, `tool_call`, `completed`,
        `error`, `trust_prompt`, `approval_prompt`, `prompt_resolved`.
        Older backends may emit only the first five; new event types
        from M-channel-prompts onward extend the stream without
        breaking forward-compat."""
        ...

    async def submit_prompt_answer(
        self, run_id: str, prompt_id: str, choice: str
    ) -> dict[str, Any]:
        """Resolve an outstanding `trust_prompt` / `approval_prompt`.

        Channels call this when the user picks a button. Backends that
        never emit prompts can stub it as `raise NotImplementedError`;
        the gateway only calls this in response to a prompt event."""
        ...

    async def get_session(self, session_id: str) -> dict[str, Any]:
        """The session's agent `mode` (`"default"` when never switched) and its `goal`."""
        ...

    async def get_session_usage(self, session_id: str) -> dict[str, Any]:
        """The session's `tokens_in`/`tokens_out`/`cache_read`/`last_prompt_tokens`
        since the daemon started, its `model` and `context_window` (M116b)."""
        ...

    async def update_session(self, session_id: str, *, mode: str) -> dict[str, Any]:
        """Switch the session's agent mode; `"default"` switches it back."""
        ...

    async def cancel_goal(self, session_id: str) -> dict[str, Any]:
        """Cancel the session's goal; `{"cancelled": null}` when it had none."""
        ...

    async def run_dream(self) -> dict[str, Any]:
        """Run a dream cycle now; `{"summary": ..., "notes": ...}`."""
        ...

    async def health(self) -> dict[str, Any]:
        """The daemon's status, project and fixed provider."""
        ...


@dataclass(frozen=True, slots=True)
class CredField:
    """One credential or setting the add-channel wizard collects for a platform.

    `secret=True` → kept in the keychain (`core/channel_setup.py` names the slot),
    else written to the channel's config block. `list_value=True` → the
    comma-separated answer is split into a list (e.g. a whitelist). `env` → the
    environment variable `veles channel run` reads the value from."""

    key: str
    label: str
    secret: bool = False
    list_value: bool = False
    required: bool = False
    env: str | None = None


@dataclass(frozen=True, slots=True)
class ChannelCaps:
    """What core needs to know about a platform. `asks_questions`: its gateway
    renders trust/approval/`ask_user` prompts and returns the answer."""

    asks_questions: bool = False


@dataclass(frozen=True, slots=True)
class ChannelContext:
    """Everything a platform's gateway is built from."""

    name: str
    config: Mapping[str, Any]  # [channels.<name>] or [daemon.<s>.channels.<name>]
    secrets: Mapping[str, str]  # the platform's secret fields, resolved
    backend: RunBackend
    session_map: SessionMap
    project: Project | None  # None for `veles channel run` outside a project


class ChannelGateway(Protocol):
    async def start(self) -> None: ...

    async def stop(self) -> None: ...

    async def deliver(self, chat_id: str, text: str, thread_id: str | None = None) -> None: ...


@dataclass(frozen=True, slots=True)
class PlatformSpec:
    """A messaging platform, contributed by a module under the `platform` point."""

    build: Callable[[ChannelContext], ChannelGateway]
    caps: ChannelCaps = ChannelCaps()
    cred_fields: tuple[CredField, ...] = ()
    config_keys: frozenset[str] = frozenset()  # channel config keys besides cred_fields


def _specs() -> dict[str, PlatformSpec]:
    from veles.core.contributions import contributions

    return {c.name: c.obj for c in contributions("platform") if isinstance(c.obj, PlatformSpec)}


def get_platform(name: str) -> PlatformSpec:
    """The spec a loaded module contributes for `name`; KeyError lists what there is."""
    specs = _specs()
    if name not in specs:
        available = ", ".join(sorted(specs)) or "(none)"
        raise KeyError(f"no channel platform {name!r}; available: {available}")
    return specs[name]


def list_platforms() -> list[str]:
    return sorted(_specs())

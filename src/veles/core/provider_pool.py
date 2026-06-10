"""Failover provider pool (Tier δ, M56).

Wraps N `Provider` instances behind one Provider-shaped surface and rotates
to the next on transient errors. Use when you've got multiple API keys
for the same provider (rate-limit smoothing) or a primary + a cheaper /
slower fallback for the same role.

Rotation is round-robin: when key K errors, K+1 takes the next call.
The pool does NOT pin a healthy key — that would require health-tracking,
back-off, and a control loop. For Veles' current cost-per-request the
simple rotation is enough; failure cascades are short.

`is_transient(exc)` is a duck-type heuristic over exception type name +
HTTP status. False positives (retrying a permanent failure) just waste a
call and surface the same error from the next provider. False negatives
(treating a transient as permanent) propagate. Both are acceptable
trade-offs for not coupling to every provider SDK's exception hierarchy.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Iterator
from typing import Any

from veles.core.provider import (
    Message,
    Provider,
    ProviderResponse,
    ProviderUnavailable,
    StreamEvent,
)


def is_transient(exc: BaseException) -> bool:
    """Return True when `exc` looks like a transient failure (worth retrying)."""
    name = type(exc).__name__
    # Common provider-SDK exception names.
    if name in {
        "RateLimitError",
        "TimeoutException",
        "ReadTimeout",
        "ConnectTimeout",
        "APIConnectionError",
        "APITimeoutError",
        "InternalServerError",
        "ServiceUnavailableError",
        "OverloadedError",
        "ConnectionError",
    }:
        return True
    # HTTPX/openai/anthropic: status_code attribute exists on response errors.
    status = getattr(exc, "status_code", None)
    if isinstance(status, int) and status >= 500:
        return True
    return False


class FailoverProvider:
    """A Provider that rotates across `providers` on transient errors.

    `supports_tools` / `supports_streaming` reflect the first provider —
    they're meant to be a homogeneous pool. Mixing providers with different
    capabilities is the caller's responsibility.

    M146 — dead-host cooldown: plain round-robin keeps routing INTO a flapping
    host every cycle. With cooldown on (the default), a provider that fails
    `fail_threshold` times in a row is marked dead for `cooldown_sec` and
    skipped — calls route straight to a healthy peer instead of timing out on
    the dead one, and a single-provider pool fails fast with
    `ProviderUnavailable` during the window rather than retry-storming. A
    success resets the host's failure streak and clears its cooldown; the
    window expires on its own so recovery needs no control loop. Set
    `cooldown_sec=0` to restore pure rotation (the M56 behaviour).
    """

    def __init__(
        self,
        providers: list[Provider],
        *,
        max_attempts: int = 3,
        cooldown_sec: float = 20.0,
        fail_threshold: int = 2,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if not providers:
            raise ValueError("FailoverProvider requires at least one provider")
        self._providers = providers
        self._max_attempts = max(1, min(max_attempts, len(providers)))
        self._idx = 0
        # M146 cooldown state, one slot per provider. `_dead_until` is a
        # monotonic deadline (0.0 = alive); `_fails` is the consecutive
        # failure streak that arms the cooldown at `fail_threshold`.
        self._cooldown_sec = cooldown_sec
        self._fail_threshold = max(1, fail_threshold)
        self._clock = clock
        self._dead_until = [0.0] * len(providers)
        self._fails = [0] * len(providers)

    @property
    def name(self) -> str:
        # Stable name for trace.provider so all pool-routed calls land under
        # a single bucket. Index suffix would fragment cache telemetry.
        return f"failover[{self._providers[0].name}*{len(self._providers)}]"

    @property
    def supports_tools(self) -> bool:
        return self._providers[0].supports_tools

    @property
    def supports_streaming(self) -> bool:
        return self._providers[0].supports_streaming

    @property
    def current_index(self) -> int:
        """Exposed for tests / observability."""
        return self._idx

    def cooling_down(self) -> list[int]:
        """Indices currently in cooldown (dead). For tests / observability."""
        return [i for i in range(len(self._providers)) if self._is_dead(i)]

    # ---- M146 cooldown helpers ----

    def _is_dead(self, idx: int) -> bool:
        return self._cooldown_sec > 0 and self._dead_until[idx] > self._clock()

    def _select_alive(self) -> int | None:
        """Next non-dead index scanning from `_idx`, or None if all are dead."""
        n = len(self._providers)
        for offset in range(n):
            idx = (self._idx + offset) % n
            if not self._is_dead(idx):
                return idx
        return None

    def _mark_failure(self, idx: int) -> None:
        if self._cooldown_sec <= 0:
            return
        self._fails[idx] += 1
        if self._fails[idx] >= self._fail_threshold:
            self._dead_until[idx] = self._clock() + self._cooldown_sec

    def _mark_success(self, idx: int) -> None:
        if self._cooldown_sec <= 0:
            return
        self._fails[idx] = 0
        self._dead_until[idx] = 0.0

    def create_message(
        self,
        messages: list[Message],
        tools: list[dict[str, Any]] | None = None,
        *,
        model: str,
        max_tokens: int = 4096,
    ) -> ProviderResponse:
        last: BaseException | None = None
        for _ in range(self._max_attempts):
            idx = self._select_alive()
            if idx is None:
                break  # every provider is cooling down
            self._idx = idx
            try:
                resp = self._providers[idx].create_message(
                    messages, tools=tools, model=model, max_tokens=max_tokens
                )
                self._mark_success(idx)
                return resp
            except Exception as exc:  # noqa: BLE001
                if not is_transient(exc):
                    raise
                last = exc
                self._mark_failure(idx)
                self._rotate()
        # Exhausted attempts (or all dead) — re-raise the last transient so the
        # caller sees what went wrong. If we never attempted (all providers were
        # already cooling down), surface that explicitly.
        if last is not None:
            raise last
        raise ProviderUnavailable(
            f"{self.name}: all {len(self._providers)} providers are cooling down"
        )

    def stream_message(
        self,
        messages: list[Message],
        tools: list[dict[str, Any]] | None = None,
        *,
        model: str,
        max_tokens: int = 4096,
    ) -> Iterator[StreamEvent]:
        last: BaseException | None = None
        for _ in range(self._max_attempts):
            idx = self._select_alive()
            if idx is None:
                break
            self._idx = idx
            try:
                yield from self._providers[idx].stream_message(
                    messages, tools=tools, model=model, max_tokens=max_tokens
                )
                self._mark_success(idx)
                return
            except Exception as exc:  # noqa: BLE001
                if not is_transient(exc):
                    raise
                last = exc
                self._mark_failure(idx)
                self._rotate()
        if last is not None:
            raise last
        raise ProviderUnavailable(
            f"{self.name}: all {len(self._providers)} providers are cooling down"
        )

    def _rotate(self) -> None:
        self._idx = (self._idx + 1) % len(self._providers)


__all__ = ["FailoverProvider", "is_transient"]

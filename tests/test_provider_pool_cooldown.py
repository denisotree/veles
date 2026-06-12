"""M146: dead-host cooldown on FailoverProvider.

Plain round-robin (M56) re-routes into a flapping host every cycle. M146 marks
a provider dead for `cooldown_sec` after `fail_threshold` consecutive transient
failures and skips it — routing to a healthy peer, or failing fast with
`ProviderUnavailable` when the whole pool is cooling down. A success resets the
streak and clears the cooldown; the window expires on its own.

A controllable `clock` makes the time-based window deterministic.

Invariants:
  1. A host marked dead is skipped; a healthy peer serves the call.
  2. When every provider is cooling down, the call fails fast with
     ProviderUnavailable (no attempt made).
  3. The cooldown expires after `cooldown_sec`; the host is retried.
  4. A success before the threshold resets the failure streak.
  5. `cooldown_sec=0` restores pure rotation (no host ever marked dead).
"""

from __future__ import annotations

import contextlib

from veles.core.provider import ProviderResponse, ProviderUnavailable, TokenUsage
from veles.core.provider_pool import FailoverProvider


class _Clock:
    """Manually advanced monotonic clock."""

    def __init__(self) -> None:
        self.t = 1000.0

    def __call__(self) -> float:
        return self.t

    def advance(self, dt: float) -> None:
        self.t += dt


class _RateLimit(Exception):
    pass


_RateLimit.__name__ = "RateLimitError"  # matches is_transient heuristic


class _Ok:
    name = "ok"
    supports_tools = True
    supports_streaming = False

    def __init__(self) -> None:
        self.call_count = 0

    def create_message(self, *a, **k):
        del a, k
        self.call_count += 1
        return ProviderResponse(text="ok", tool_calls=[], usage=TokenUsage(total_tokens=1))


class _Flaky:
    """Fails transiently until `heal_after` calls have been made, then succeeds."""

    name = "flaky"
    supports_tools = True
    supports_streaming = False

    def __init__(self, heal_after: int | None = None) -> None:
        self.call_count = 0
        self.heal_after = heal_after

    def create_message(self, *a, **k):
        del a, k
        self.call_count += 1
        if self.heal_after is not None and self.call_count > self.heal_after:
            return ProviderResponse(
                text="recovered", tool_calls=[], usage=TokenUsage(total_tokens=1)
            )
        raise _RateLimit("429")


def test_dead_host_is_skipped_for_healthy_peer() -> None:
    clock = _Clock()
    flaky = _Flaky()
    good = _Ok()
    pool = FailoverProvider(
        [flaky, good], max_attempts=2, cooldown_sec=20.0, fail_threshold=2, clock=clock
    )
    # Call 1: flaky fails (streak 1), rotate → good serves. flaky not yet dead.
    assert pool.create_message([], model="m").text == "ok"
    assert pool.cooling_down() == []
    # Force flaky back to index 0 and fail it again to reach the threshold.
    pool._idx = 0
    # flaky fails (streak 2 → dead), good serves
    assert pool.create_message([], model="m").text == "ok"
    assert pool.cooling_down() == [0]
    # Next call: flaky is dead → skipped entirely; good serves without touching flaky.
    before = flaky.call_count
    pool._idx = 0
    assert pool.create_message([], model="m").text == "ok"
    assert flaky.call_count == before  # dead host never called


def test_all_dead_fails_fast() -> None:
    clock = _Clock()
    a, b = _Flaky(), _Flaky()
    pool = FailoverProvider(
        [a, b], max_attempts=2, cooldown_sec=20.0, fail_threshold=1, clock=clock
    )
    # threshold=1: first failure of each marks it dead. One call fails both → both dead.
    with contextlib.suppress(_RateLimit):
        pool.create_message([], model="m")
    assert pool.cooling_down() == [0, 1]
    # Next call: every provider cooling down → fail fast, nothing called.
    a_before, b_before = a.call_count, b.call_count
    try:
        pool.create_message([], model="m")
        raise AssertionError("expected ProviderUnavailable")
    except ProviderUnavailable:
        pass
    assert a.call_count == a_before and b.call_count == b_before


def test_cooldown_expires_and_host_retried() -> None:
    clock = _Clock()
    flaky = _Flaky(heal_after=2)  # fails calls 1,2 then recovers
    pool = FailoverProvider(
        [flaky], max_attempts=1, cooldown_sec=20.0, fail_threshold=2, clock=clock
    )
    # Two failing calls arm the cooldown (single provider, max_attempts=1).
    for _ in range(2):
        with contextlib.suppress(_RateLimit):
            pool.create_message([], model="m")
    assert pool.cooling_down() == [0]
    # Within the window: fail fast, host not called.
    before = flaky.call_count
    with contextlib.suppress(ProviderUnavailable):
        pool.create_message([], model="m")
    assert flaky.call_count == before
    # After the window: host retried and (now healed) succeeds.
    clock.advance(21.0)
    assert pool.cooling_down() == []
    assert pool.create_message([], model="m").text == "recovered"


def test_success_resets_failure_streak() -> None:
    clock = _Clock()
    flaky = _Flaky(heal_after=1)  # fails call 1, succeeds from call 2
    pool = FailoverProvider(
        [flaky], max_attempts=1, cooldown_sec=20.0, fail_threshold=2, clock=clock
    )
    with contextlib.suppress(_RateLimit):
        pool.create_message([], model="m")  # streak 1
    pool.create_message([], model="m")  # success → streak reset to 0
    # A subsequent single failure must not immediately trip (streak restarts).
    flaky.heal_after = None  # make it always fail again
    flaky.call_count = 0
    # call fails once; streak is 1 (<2) so not dead.
    with contextlib.suppress(_RateLimit):
        pool.create_message([], model="m")
    assert pool.cooling_down() == []


def test_cooldown_disabled_restores_pure_rotation() -> None:
    clock = _Clock()
    a, b = _Flaky(), _Flaky()
    pool = FailoverProvider([a, b], max_attempts=2, cooldown_sec=0.0, clock=clock)
    # Both fail; with cooldown off nothing is ever marked dead.
    with contextlib.suppress(_RateLimit):
        pool.create_message([], model="m")
    assert pool.cooling_down() == []

"""M-R2.5: per-chip renderers in status bar.

Each `_chip_*` is unit-testable in isolation; `_collect_chips` filters
out None and preserves display order.
"""

from __future__ import annotations

from veles.tui.state import AppState
from veles.tui.widgets.status_bar import (
    _chip_busy,
    _chip_context,
    _chip_insights,
    _chip_mode,
    _chip_provider_model,
    _chip_queue,
    _chip_session,
    _chip_tokens,
    _collect_chips,
)


def _state(**overrides) -> AppState:
    base = dict(session_id=None, provider_name="openai", model="gpt-4o")
    base.update(overrides)
    return AppState(**base)  # type: ignore[arg-type]


def test_mode_chip_always_present() -> None:
    assert _chip_mode(_state()) == "[auto]"
    assert _chip_mode(_state(mode="planning")) == "[planning]"


def test_session_chip_uses_new_when_no_id() -> None:
    assert _chip_session(_state()) == "session new"
    assert _chip_session(_state(session_id="abc")) == "session abc"


def test_provider_model_strips_known_prefix() -> None:
    chip = _chip_provider_model(_state(provider_name="openai", model="openrouter/gpt-4o"))
    assert chip == "openai/gpt-4o"


def test_tokens_chip_off_until_first_turn() -> None:
    assert _chip_tokens(_state()) is None
    assert _chip_tokens(_state(tokens_in=100, tokens_out=50)) is not None


def test_context_chip_off_until_first_turn() -> None:
    assert _chip_context(_state()) is None


def test_insights_chip_counts() -> None:
    s = _state(insight_candidates=[("a", "t", "b"), ("c", "t", "b")])
    assert "2 insight(s)" in (_chip_insights(s) or "")


def test_busy_chip_off_when_idle() -> None:
    assert _chip_busy(_state()) is None
    assert _chip_busy(_state(busy=True)) == "[bold]busy[/bold]"


def test_queue_chip_off_when_empty() -> None:
    from collections import deque

    assert _chip_queue(_state()) is None
    assert _chip_queue(_state(queue=deque(["a", "b"]))) == "queue 2"


def test_collect_chips_drops_none_in_order() -> None:
    """Idle state: mode + session + provider/model — three chips total."""
    chips = _collect_chips(_state())
    assert chips == ["[auto]", "session new", "openai/gpt-4o"]


def test_collect_chips_full_state_order_preserved() -> None:
    """M115.3: select chip removed; remaining chips slide up one slot."""
    from collections import deque

    s = _state(
        mode="planning",
        session_id="s1",
        tokens_in=1000,
        tokens_out=500,
        last_turn_total_tokens=1500,
        insight_candidates=[("x", "t", "b")],
        busy=True,
        queue=deque(["p"]),
    )
    chips = _collect_chips(s)
    # Mode → session → provider → tokens → ctx → insights → busy → queue
    assert chips[0] == "[planning]"
    assert chips[1] == "session s1"
    assert chips[2].startswith("openai/")
    assert chips[3].startswith("tok ")
    assert chips[4].startswith("ctx ")
    assert "insight(s)" in chips[5]
    assert chips[6] == "[bold]busy[/bold]"
    assert chips[7] == "queue 1"

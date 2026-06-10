"""Display tiers (M74) — per-platform formatting capabilities.

Different channels have different message-edit budgets and max lengths:

- HIGH (Telegram, Discord): supports message edits, ~4000 chars per message,
  cheap to flush partial deltas during streaming.
- MEDIUM (Slack, Feishu): edits supported but rate-limited, ~3000 chars,
  fewer flushes per turn.
- LOW (Signal, Matrix): edits expensive/unsupported, ~2000 chars, flush
  only on terminal events.
- MINIMAL (Email, SMS): no edits, no streaming, send one consolidated
  message after `completed`.

Channels read tier constants instead of hardcoding numbers in their loop
body. Tier replaces the M52 `_TELEGRAM_MAX_MSG` / `_EDIT_COOLDOWN_SEC` /
`_EDIT_CHAR_THRESHOLD` literals so a new platform can pick a tier instead
of copy-pasting numbers.

Deliberately not a 60-flag config schema — five values per tier, four tiers.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class DisplayTier(Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    MINIMAL = "minimal"


@dataclass(slots=True, frozen=True)
class DisplaySettings:
    """Concrete formatting limits for one tier.

    - `max_message_chars`: hard truncation cap (with `truncation_suffix`).
    - `edit_cooldown_sec`: minimum gap between successive `editMessage`-style
      flushes during streaming.
    - `edit_char_threshold`: also flush when buffered delta hits this many
      chars (whichever comes first).
    - `supports_edits`: false → never flush deltas; only send one final.
    - `truncation_suffix`: appended when truncating long messages.
    """

    max_message_chars: int
    edit_cooldown_sec: float
    edit_char_threshold: int
    supports_edits: bool
    truncation_suffix: str = "..."


_TIER_SETTINGS: dict[DisplayTier, DisplaySettings] = {
    DisplayTier.HIGH: DisplaySettings(
        max_message_chars=4000,
        edit_cooldown_sec=0.5,
        edit_char_threshold=200,
        supports_edits=True,
    ),
    DisplayTier.MEDIUM: DisplaySettings(
        max_message_chars=3000,
        edit_cooldown_sec=1.5,
        edit_char_threshold=400,
        supports_edits=True,
    ),
    DisplayTier.LOW: DisplaySettings(
        max_message_chars=2000,
        edit_cooldown_sec=5.0,
        edit_char_threshold=1000,
        supports_edits=True,
    ),
    DisplayTier.MINIMAL: DisplaySettings(
        max_message_chars=1600,
        edit_cooldown_sec=0.0,
        edit_char_threshold=10_000,
        supports_edits=False,
    ),
}


def settings_for(tier: DisplayTier) -> DisplaySettings:
    return _TIER_SETTINGS[tier]


def truncate_for_tier(text: str, tier: DisplayTier) -> str:
    """Truncate `text` to fit `tier.max_message_chars`, suffixing on overflow."""
    s = settings_for(tier)
    if len(text) <= s.max_message_chars:
        return text
    cap = s.max_message_chars - len(s.truncation_suffix)
    cap = max(cap, 0)
    return text[:cap] + s.truncation_suffix


__all__ = [
    "DisplaySettings",
    "DisplayTier",
    "settings_for",
    "truncate_for_tier",
]

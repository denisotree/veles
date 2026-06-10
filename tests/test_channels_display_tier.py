"""M74 — DisplayTier settings + truncation."""

from __future__ import annotations

from veles.channels.display import DisplayTier, settings_for, truncate_for_tier


def test_high_tier_settings():
    s = settings_for(DisplayTier.HIGH)
    assert s.supports_edits is True
    assert s.max_message_chars == 4000
    assert 0 < s.edit_cooldown_sec < 5
    assert s.edit_char_threshold > 0


def test_minimal_tier_disables_edits():
    s = settings_for(DisplayTier.MINIMAL)
    assert s.supports_edits is False


def test_truncate_short_text_passes_through():
    assert truncate_for_tier("hello", DisplayTier.HIGH) == "hello"


def test_truncate_long_text_capped_with_suffix():
    long = "x" * 5000
    out = truncate_for_tier(long, DisplayTier.HIGH)
    s = settings_for(DisplayTier.HIGH)
    assert len(out) == s.max_message_chars
    assert out.endswith(s.truncation_suffix)


def test_low_tier_truncates_at_lower_cap():
    long = "x" * 5000
    out = truncate_for_tier(long, DisplayTier.LOW)
    assert len(out) == settings_for(DisplayTier.LOW).max_message_chars


def test_all_tiers_distinct_caps():
    caps = {tier: settings_for(tier).max_message_chars for tier in DisplayTier}
    assert caps[DisplayTier.HIGH] > caps[DisplayTier.MEDIUM]
    assert caps[DisplayTier.MEDIUM] > caps[DisplayTier.LOW]
    assert caps[DisplayTier.LOW] > caps[DisplayTier.MINIMAL]

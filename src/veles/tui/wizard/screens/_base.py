"""Shared CSS + helpers for wizard modal screens.

Visual style mirrors the daemon picker's modal chrome so the wizard
feels native — same border, padding, centred panel."""

from __future__ import annotations

WIZARD_CSS = """
$wizard-bg: $surface;

/* Flat panel: thin rounded border, no chunky 3D `tall` block; padding
   kept tight so vertical real estate isn't wasted on chrome. */
.wizard-panel {
    background: $surface;
    border: round $primary;
    padding: 1 2;
    width: 80%;
    max-width: 100;
    height: auto;
    max-height: 30;
}

/* All child Labels claim the panel's full inner width so long prompts
   wrap naturally instead of overflowing into the border. Without an
   explicit `width: 1fr` the Label's default `width: auto` would size
   it to the longest single line. */
.wizard-title,
.wizard-subtitle,
.wizard-body,
.wizard-hint {
    width: 1fr;
    height: auto;
}

.wizard-title {
    color: $accent;
    text-style: bold;
    margin-bottom: 1;
}

.wizard-subtitle {
    color: $text-muted;
    margin-bottom: 1;
}

.wizard-hint {
    color: $text-muted;
    margin-top: 1;
}

/* Flatten inputs / buttons that ship with a default `tall` Textual border. */
.wizard-panel Input {
    border: round $primary;
    background: $surface;
}
"""

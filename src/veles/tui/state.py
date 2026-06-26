"""Per-app state container. Owned by `TuiApp`, mutated through dispatcher
methods only. Widgets read; bridge writes.

Kept as a plain dataclass on purpose: Textual already has its own
reactive-state mechanism, but coupling our domain state to widget
lifecycle (mount/unmount) makes it harder to reason about across the
worker-thread boundary. A plain dataclass lives outside the widget tree
and survives screen pushes.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Literal

ModeName = Literal["auto", "planning", "writing", "goal"]


@dataclass(slots=True)
class AppState:
    session_id: str | None
    provider_name: str
    model: str
    theme_name: str = "everforest"
    busy: bool = False
    inspector_visible: bool = False
    # Per-turn execution mode (auto / planning / writing / goal). Cycled
    # via Shift+Tab; set via `/mode <name>`. Persisted to
    # `<project>/.veles/tui_state.json` (Phase 2). In Phase 1 all four
    # names dispatch to WritingMode, so the field is inert behaviourally
    # but already present for the bridge and slash commands to read.
    mode: ModeName = "auto"
    # Which mode last drove a turn in this session, used to detect mid-
    # session mode changes that need a system-prompt observation injected
    # into the next user prompt (PlanningMode etc. — Phase 3+).
    last_mode_in_session: ModeName | None = None
    # Active Goal artifact id when GoalMode is mid-FSM (Phase 5+).
    active_goal_id: str | None = None
    # Pending prompts entered while the agent was busy. Drained FIFO when
    # the current turn finishes. Phase 6 hooks Up/Down navigation into it;
    # Phase 1 leaves it inert (no UI), present here so the bridge can append
    # without conditional imports.
    queue: deque[str] = field(default_factory=deque)
    # Last completed assistant turn's text. Used by `/save <slug>` to
    # persist a reply into `wiki/queries/<slug>.md`. Reset on `/clear`.
    last_assistant_text: str | None = None
    # Default limits for `/history`, `/show`, and `/wiki search`. Carried
    # on state (not module constants) so a future `/set` command can let
    # users tweak them without restarting the TUI.
    history_limit: int = 20
    show_limit: int = 10
    wiki_search_limit: int = 5
    search_turn_limit: int = 8
    # M79: cumulative token totals for the active TUI session. Updated by
    # TuiApp.on_turn_done from RunResult.usage; rendered in the status bar.
    tokens_in: int = 0
    tokens_out: int = 0
    last_turn_total_tokens: int = 0
    # M177: prompt-token count of the most recent request — the live context
    # occupancy the `ctx` chip renders against the model window (so it stays
    # <= ~100% instead of conflating cumulative run usage with window size).
    last_prompt_tokens: int = 0
    # M87: batch insight extractor candidates awaiting `/save` confirmation.
    # Each entry is a tuple (slug, title, body). Populated by the periodic
    # extractor; consumed (and cleared per slug) by `/save <slug>`.
    insight_candidates: list[tuple[str, str, str]] = field(default_factory=list)
    turns_since_insight_scan: int = 0
    # M115.3: select_mode removed — native terminal text-selection is
    # always on (Textual mouse capture is permanently disabled on
    # mount). VISION §7.2 forbids a mode toggle for selection.

"""One-time setup-hint notice for missing embedding backend.

VISION §5.1 / §7 contract: Veles never crashes on a missing optional
capability — it falls back gracefully and tells the user **once**
how to upgrade. This module owns that contract for the embedding
backend specifically.

The hint surfaces as a single `insights` row with category
`setup-hint` and title `Embedding backend not configured`. The TUI
insights panel, `/save` slash, and Telegram `/status` already read
this table, so the user discovers the hint through whichever
surface they happen to look at. After it's surfaced once, the
dedup check (same title + category) prevents it from re-appearing
on every curator pass.

Call site: `cli/_runtime.py` runs `maybe_surface_embedding_setup_hint`
after `autodetect_embedding_adapter` returns None. Safe to call
repeatedly — idempotent on the insights row.
"""

from __future__ import annotations

import contextlib
import logging
import sqlite3
import time

from veles.core.project import Project

logger = logging.getLogger(__name__)


SETUP_HINT_CATEGORY = "setup-hint"
SETUP_HINT_TITLE = "Embedding backend not configured"

_BODY = """\
Veles is running with **token-based ranking** for paths and skill
patterns. That works, but embeddings give noticeably better recall
on larger projects (50+ files, 100+ sessions). Three ways to
enable, easiest first:

1. **Install Ollama and pull a small embedding model.**
   - macOS: `brew install ollama && ollama serve`
   - Linux: `curl -fsSL https://ollama.com/install.sh | sh`
   - Then: `ollama pull nomic-embed-text` (274 MB, 768-dim,
     multilingual). Veles auto-detects Ollama on next start.

2. **Set `OPENROUTER_API_KEY` (or `OPENAI_API_KEY`).** The same
   key Veles uses for chat completions also powers embeddings via
   `text-embedding-3-small` (~$0.02 per million tokens — essentially
   free for personal use).

3. **Stay on token-based ranking.** It's the default and works for
   small / medium projects. Re-visit when ranking quality matters.

This notice surfaces once per project; dismiss it from the insights
panel after you've decided.
"""


def maybe_surface_embedding_setup_hint(project: Project, *, now: float | None = None) -> bool:
    """Write the setup hint to `insights` if not already present.
    Returns True iff a fresh row was inserted (False = already there).
    Never raises — a sqlite hiccup just skips the notice."""
    wall = time.time() if now is None else now
    try:
        from veles.core.memory import SessionStore

        store = SessionStore(project.memory_db_path)
        conn = store._conn
    except sqlite3.Error as exc:
        logger.info("setup-hint: cannot open db: %s", exc)
        return False
    try:
        existing = conn.execute(
            "SELECT 1 FROM insights WHERE title = ? AND category = ? LIMIT 1",
            (SETUP_HINT_TITLE, SETUP_HINT_CATEGORY),
        ).fetchone()
        if existing is not None:
            return False
        conn.execute(
            "INSERT INTO insights(title, body, category, created_at) VALUES (?, ?, ?, ?)",
            (SETUP_HINT_TITLE, _BODY, SETUP_HINT_CATEGORY, wall),
        )
        return True
    except sqlite3.Error as exc:
        logger.info("setup-hint: write failed: %s", exc)
        return False
    finally:
        with contextlib.suppress(Exception):
            conn.close()


__all__ = [
    "SETUP_HINT_CATEGORY",
    "SETUP_HINT_TITLE",
    "maybe_surface_embedding_setup_hint",
]

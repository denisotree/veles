"""One-time setup-hint notice when semantic insight recall is unavailable.

VISION §5.1 / §7 contract: Veles never crashes on a missing optional
capability — it falls back gracefully and tells the user **once**
how to upgrade. This module owns that contract for the embedding
backend specifically.

The hint surfaces as a single `insights` row with category
`setup-hint`. The TUI insights panel, `/save` slash, and Telegram
`/status` already read this table, so the user discovers the hint
through whichever surface they happen to look at. After it's surfaced
once, the dedup check (same title + category) prevents it from
re-appearing on every curator pass.

Call site: `cli/_curator.py` runs `maybe_surface_embedding_setup_hint`
when `get_local_embedding_adapter()` returns None. Safe to call
repeatedly — idempotent on the insights row.

M231: the gate is the **local** adapter, not "any adapter". M192 sends
neither the recall query nor insight bodies to a cloud embedder, so a
cloud adapter leaves insight recall keyword-only — and it used to
silence this hint in exactly that setup. The body says so explicitly
rather than offering an API key as a fix that would not fix it.
"""

from __future__ import annotations

import contextlib
import logging
import sqlite3
import time

from veles.core.project import Project

logger = logging.getLogger(__name__)


SETUP_HINT_CATEGORY = "setup-hint"
SETUP_HINT_TITLE = "Semantic recall needs a local embedder"

_BODY = """\
Insight recall is running **keyword-only**, and no insight embeddings
are being written. Both go through an **on-device** embedder by
design: the recall query and your insight bodies must never be sent
to a cloud embedding service, so an API key does not enable them.

**To turn semantic recall on — install Ollama and pull a small model:**
  - macOS: `brew install ollama && ollama serve`
  - Linux: `curl -fsSL https://ollama.com/install.sh | sh`
  - Then: `ollama pull nomic-embed-text` (274 MB, 768-dim,
    multilingual). Veles auto-detects it on next start.
  - Override the model with `VELES_OLLAMA_EMBED_MODEL`.

Existing insights are embedded by `veles dream --include-consolidation`
(the flag matters — backfill and dedup run only under it).

A cloud key (`OPENROUTER_API_KEY` / `OPENAI_API_KEY`) is still used
for the ranking that does not involve your project's text — file-path
relevance and skill-pattern clustering — so it is worth having either
way; it just does not cover insight recall.

Staying keyword-only is a fine choice for a small project. Recall
still works; it just needs the query to share literal words with what
was stored.

`veles doctor` reports which backend is active. This notice surfaces
once per project; dismiss it from the insights panel once you've decided.
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

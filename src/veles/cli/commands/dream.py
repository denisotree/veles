"""`veles dream` (M76) — synchronous one-shot dream cycle.

Mirrors what the daemon's `DreamRunner` does at idle, but blocks until done.
Useful when a user wants explicit control over consolidation timing, or for
testing.
"""

from __future__ import annotations

import argparse
import sys

from veles.core.dreaming import dream_cycle


def cmd_dream(args: argparse.Namespace, project) -> int:
    include_consolidation = bool(getattr(args, "include_consolidation", False))
    dry_run = bool(getattr(args, "dry_run", False))
    skip_insights = bool(getattr(args, "skip_insights", False))
    skip_dedup = bool(getattr(args, "skip_dedup", False))
    skip_promote = bool(getattr(args, "skip_promote", False))
    skip_lint = bool(getattr(args, "skip_lint", False))

    provider = None
    history_loader = None
    consolidation_model = getattr(args, "consolidation_model", None)
    if include_consolidation:
        from veles.cli import _make_provider

        # Resolve the consolidation provider+model through routing (M125) so
        # they stay consistent. A bare `veles dream --include-consolidation`
        # on a fully-local project (`[provider]=ollama`) must not ask that
        # backend for the hardcoded `anthropic/claude-haiku-4.5` slug → 404.
        # An explicit `--provider` still wins; the routed model is adopted
        # only when it belongs to that same provider.
        from veles.core.model_resolver import ConfigurationError
        from veles.core.routing.ensemble import route

        try:
            routed_provider, routed_model = route("insights", project)
        except ConfigurationError:
            # Unconfigured + no explicit --provider → empty routed spec makes
            # `_make_provider("")` fail below and consolidation is skipped.
            routed_provider, routed_model = "", ""
        provider_name = getattr(args, "provider", None) or routed_provider
        if consolidation_model is None and provider_name == routed_provider:
            consolidation_model = routed_model
        try:
            provider = _make_provider(provider_name)
        except Exception as exc:
            print(f"warning: provider unavailable, consolidation skipped: {exc}", file=sys.stderr)
            include_consolidation = False
    # Build insight history loader only if not skipping insights AND we have a provider.
    if not skip_insights and provider is not None:
        history_loader = _build_history_loader(project)

    result = dream_cycle(
        project,
        include_consolidation=include_consolidation,
        skip_insights=skip_insights,
        skip_dedup=skip_dedup,
        skip_promote=skip_promote,
        skip_lint=skip_lint,
        dry_run=dry_run,
        provider=provider,
        consolidation_model=consolidation_model,
        insight_history_loader=history_loader,
    )
    print(result.summary())
    for note in result.notes:
        print(f"  note: {note}", file=sys.stderr)
    return 0


def _build_history_loader(project):
    """Return a callable that yields (session_id, history) for sessions
    newer than the curator cursor."""
    from veles.core.curator_state import load
    from veles.core.memory import SessionStore

    def loader():
        state = load(project.state_dir / "curator.state.json")
        store = SessionStore(project.memory_db_path)
        try:
            sessions = store.list_sessions_since(state.last_curated_at, limit=20)
            for s in sessions:
                history = store.load_messages(s.id)
                yield s.id, history
        finally:
            store.close()

    return loader

from veles.core.knowledge.notes import Note
from veles.core.knowledge.skeleton import SkeletonEntry
from veles.core.knowledge.store import (
    KnowledgeStore,
    get_default_store,
)


def _store() -> KnowledgeStore:
    notes = [
        Note(
            slug="run-session",
            title="Run an interactive agent session",
            body='Use `veles run "prompt"` to start a session in the current project.',
            topics=["run", "session", "prompt", "interactive"],
            related=["cmd:run"],
        ),
        Note(
            slug="add-source",
            title="Add a source file to the wiki",
            body="`veles add <file>` reads a source and writes a wiki page.",
            topics=["add", "ingest", "wiki", "source"],
            related=["cmd:add"],
        ),
    ]
    skeleton = [
        SkeletonEntry(kind="cmd", name="run", summary="interactive agent run"),
        SkeletonEntry(kind="cmd", name="add", summary="read a source into a wiki page"),
    ]
    return KnowledgeStore(notes, skeleton)


def test_search_surfaces_relevant_note_first():
    hits = _store().search("how do I run a session")
    assert hits, "expected at least one hit"
    assert hits[0].source == "note"
    assert hits[0].ref == "run-session"


def test_search_gates_out_non_veles_queries():
    # A generic coding query mentioning none of the notes' terms → no hits.
    assert _store().search("refactor this failing unit test suite") == []


def test_search_orders_by_score():
    hits = _store().search("add a source to the wiki")
    assert hits[0].ref == "add-source"


def test_get_by_slug_and_ref():
    st = _store()
    assert st.get("run-session").title == "Run an interactive agent session"
    assert st.get("cmd:add").source == "skeleton"
    assert st.get("nonexistent") is None


def test_default_store_builds_from_package():
    st = get_default_store()
    # Skeleton always yields entries even before notes are seeded.
    assert st.search("run") != [] or st.get("cmd:run") is not None

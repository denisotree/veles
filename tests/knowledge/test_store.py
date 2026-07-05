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


def test_search_gates_single_common_verb_run():
    # "run" is a note title AND a common English verb — a lone match must not pass.
    assert _store().search("run the tests") == []


def test_search_gates_single_common_verb_add():
    assert _store().search("add error handling to this function") == []


def test_search_requires_two_distinct_tokens():
    # One distinct Veles token ("session") alone should not clear the gate.
    assert _store().search("session") == []


def test_get_by_slug_and_ref():
    st = _store()
    assert st.get("run-session").title == "Run an interactive agent session"
    assert st.get("cmd:add").source == "skeleton"
    assert st.get("nonexistent") is None


def test_default_store_builds_from_package():
    st = get_default_store()
    # Skeleton always yields entries even before notes are seeded.
    assert st.search("run") != [] or st.get("cmd:run") is not None


def test_default_store_gates_generic_coding_queries():
    # M186 review: ordinary coding turns must not leak Veles docs into recall.
    # These clear the ≥2-token count only via ambient CLI/coding verbs or via
    # incidental verbs in note *bodies* — both must be gated out.
    st = get_default_store()
    for q in [
        "list the files and show the diff",
        "add a new module and remove the old one",
        "init the database and add a migration",
        "add error handling and run tests",
        "remove the unused import and run linter",
        "switch to the feature branch and run build",
        "null pointer dereference in the parser loop",
        "refactor this failing unit test suite",
    ]:
        assert st.search(q) == [], f"leaked on {q!r} -> {[h.ref for h in st.search(q)]}"


def test_default_store_still_surfaces_real_howto():
    st = get_default_store()
    cases = [
        ("how do I run an interactive session in veles", "run-a-session"),
        ("how do I add a source to the wiki", "add-a-source"),
        ("how do I curate memory", "curate-memory"),
        ("how do I connect an mcp server", "mcp-servers"),
        ("how do I use manager mode for orchestration", "manager-mode"),
        ("how do I initialise a new project", "init-a-project"),
    ]
    for q, expected in cases:
        assert any(h.ref == expected for h in st.search(q)[:3]), (
            f"{q!r} did not surface {expected}: {[h.ref for h in st.search(q)[:3]]}"
        )


def test_gate_uses_title_topics_not_body():
    # The gate counts distinct matches against title+topics only; a query that
    # matches solely on body prose must not clear it (else incidental verbs leak).
    notes = [
        Note(
            slug="demo",
            title="Curate memory",
            body="Run and add and list and remove things in the project.",
            topics=["curate", "memory", "compaction"],
            related=[],
        )
    ]
    st = KnowledgeStore(notes, [])
    # "run"+"add" appear only in the body → gated (0 title/topic matches).
    assert st.search("run and add") == []
    # Two topic tokens → clears the gate.
    assert st.search("curate the memory") != []

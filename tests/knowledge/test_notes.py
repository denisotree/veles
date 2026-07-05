from pathlib import Path

from veles.core.knowledge.notes import Note, load_notes, parse_note


def _write(tmp_path: Path, name: str, text: str) -> Path:
    p = tmp_path / name
    p.write_text(text, encoding="utf-8")
    return p


def test_parse_note_reads_frontmatter_and_body(tmp_path):
    p = _write(
        tmp_path,
        "run-a-session.md",
        "---\n"
        "title: Run an interactive agent session\n"
        "topics: [run, session, prompt]\n"
        'related: ["cmd:run", "flag:run:--manager"]\n'
        "---\n"
        'Use `veles run "your prompt"` to start a session.\n',
    )
    note = parse_note(p)
    assert isinstance(note, Note)
    assert note.slug == "run-a-session"
    assert note.title == "Run an interactive agent session"
    assert note.topics == ["run", "session", "prompt"]
    assert note.related == ["cmd:run", "flag:run:--manager"]
    assert "veles run" in note.body


def test_load_notes_sorted_by_slug(tmp_path):
    _write(tmp_path, "b.md", "---\ntitle: B\n---\nbody b\n")
    _write(tmp_path, "a.md", "---\ntitle: A\n---\nbody a\n")
    notes = load_notes(tmp_path)
    assert [n.slug for n in notes] == ["a", "b"]


def test_load_default_notes_ship_in_package():
    # The real seeded notes must be discoverable with no argument.
    notes = load_notes()
    assert len(notes) >= 1
    assert all(n.title for n in notes)

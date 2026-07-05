from veles.core.knowledge.notes import load_notes
from veles.core.knowledge.skeleton import build_skeleton, skeleton_ref_index


def test_every_note_related_ref_exists_in_skeleton():
    idx = skeleton_ref_index(build_skeleton())
    dangling: list[str] = []
    for note in load_notes():
        for ref in note.related:
            if ref not in idx:
                dangling.append(f"{note.slug}: {ref}")
    assert not dangling, (
        "curated notes reference commands/flags/skills that no longer exist — "
        "update the note(s):\n  " + "\n  ".join(dangling)
    )


def test_notes_have_titles_and_bodies():
    for note in load_notes():
        assert note.title, f"{note.slug}: missing title"
        assert note.body.strip(), f"{note.slug}: empty body"

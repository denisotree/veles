from veles.core.memory.router import MemoryRouter


def _router(tmp_path):
    from veles.core.project import init_project

    project = init_project(tmp_path)
    # No SessionStore/extras: isolates the about-veles stream.
    return MemoryRouter(project)


def test_recall_surfaces_about_veles_on_howto_query(tmp_path):
    hits = _router(tmp_path).recall("how do I run an interactive session in veles")
    refs = [h.rel_path for h in hits]
    assert any(r.startswith("about-veles:") for r in refs), refs


def test_recall_silent_on_plain_coding_query(tmp_path):
    hits = _router(tmp_path).recall("null pointer dereference in the parser loop")
    assert not any(h.rel_path.startswith("about-veles:") for h in hits)

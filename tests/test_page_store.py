"""`page_store` — a module that keeps pages takes self-doc and `/save`; without
one, self-doc goes to `.veles/memory/self-doc.md` and `/save` to a memory insight."""

from __future__ import annotations

from pathlib import Path

import pytest

from veles.core.contributions import PageStore
from veles.core.modules import ModuleAPI, ModuleRegistry, reset_module_registry, set_module_registry
from veles.core.project import init_project


@pytest.fixture()
def home(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("VELES_USER_HOME", str(tmp_path / "home"))
    return tmp_path


class _Store:
    def __init__(self) -> None:
        self.pages: dict[tuple[str, str], str] = {}

    def write(self, project, category: str, slug: str, title: str, content: str) -> str:
        self.pages[(category, slug)] = content
        return f"store/{category}/{slug}.md"

    def read(self, project, category: str, slug: str) -> str | None:
        return self.pages.get((category, slug))


def _with(obj: object):
    scratch, reg = ModuleRegistry(), ModuleRegistry()
    ModuleAPI(scratch, "m").contribute("page_store", "fake", obj)
    reg.merge_from(scratch, "m")
    return set_module_registry(reg)


def test_page_store_takes_the_self_doc(home) -> None:
    from veles.core.self_doc import refresh_self_doc

    project = init_project(home / "b", name="b", layout="bare")
    store = _Store()
    token = _with(PageStore(write=store.write, read=store.read))
    try:
        rel = refresh_self_doc(project)
    finally:
        reset_module_registry(token)
    assert rel == "store/self-doc/overview.md"
    assert "self-doc" in {c for c, _ in store.pages}


def test_self_doc_falls_back_to_memory_without_an_active_store(home) -> None:
    from veles.core.self_doc import refresh_self_doc

    project = init_project(home / "b", name="b", layout="bare")
    store = _Store()
    # The store's engine isn't on in a bare project → not active.
    token = _with(PageStore(write=store.write, read=store.read, engine="fake"))
    try:
        rel = refresh_self_doc(project)
    finally:
        reset_module_registry(token)
    assert rel == ".veles/memory/self-doc.md" and not store.pages


def test_self_doc_show_reads_the_store_or_memory(home, capsys) -> None:
    from veles.cli.commands.self_doc import _show

    project = init_project(home / "b", name="b", layout="bare")
    project.memory_dir.mkdir(parents=True, exist_ok=True)
    (project.memory_dir / "self-doc.md").write_text("# from memory", encoding="utf-8")
    assert _show(project) == 0
    assert "# from memory" in capsys.readouterr().out

    store = _Store()
    store.pages[("self-doc", "overview")] = "# from the store"
    token = _with(PageStore(write=store.write, read=store.read))
    try:
        _show(project)
    finally:
        reset_module_registry(token)
    assert "# from the store" in capsys.readouterr().out


def test_save_writes_through_the_store(home) -> None:
    from veles.cli.repl.slash import build_default_registry
    from veles.cli.repl.slash.registry import SlashContext
    from veles.core.memory import SessionStore
    from veles.core.session_state import AppState

    project = init_project(home / "b", name="b", layout="bare")
    state = AppState(session_id=None, provider_name="stub", model="m")
    state.last_assistant_text = "# Answer\n\nbody"
    ctx = SlashContext(state=state, project=project, store=SessionStore(project.memory_db_path))
    store = _Store()
    token = _with(PageStore(write=store.write, read=store.read))
    try:
        res = build_default_registry(project).dispatch("/save my-note", ctx)
    finally:
        reset_module_registry(token)
    assert res is not None and not res.is_error
    assert "store/queries/my-note.md" in res.text
    assert store.pages[("queries", "my-note")].endswith("body")

"""M41 — vertical subprojects: registry, init, parent lookup, recall."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from veles.core.memory.router import MemoryRouter
from veles.core.project import (
    Project,
    ProjectAlreadyExists,
    init_project,
)
from veles.core.subproject import (
    Subproject,
    find_parent_project,
    init_subproject,
    load_subprojects,
    register_subproject,
    resolve_subproject_path,
    subprojects_path,
    unregister_subproject,
)
from veles.core.wiki import Wiki


def _make_root(tmp_path: Path, *, name: str = "root") -> Project:
    return init_project(tmp_path / name, name=name)


# ---------- registry I/O ----------


def test_load_empty_returns_empty(tmp_path: Path) -> None:
    project = _make_root(tmp_path)
    assert load_subprojects(project) == []


def test_load_corrupt_json_returns_empty(tmp_path: Path) -> None:
    project = _make_root(tmp_path)
    subprojects_path(project).write_text("{not json", encoding="utf-8")
    assert load_subprojects(project) == []


def test_load_non_dict_root_returns_empty(tmp_path: Path) -> None:
    project = _make_root(tmp_path)
    subprojects_path(project).write_text("[]", encoding="utf-8")
    assert load_subprojects(project) == []


def test_load_skips_malformed_entries(tmp_path: Path) -> None:
    project = _make_root(tmp_path)
    subprojects_path(project).write_text(
        json.dumps(
            {
                "subprojects": [
                    {"slug": "good", "path": "./g", "description": "x"},
                    {"slug": "no-path"},
                    {"path": "./onlypath"},
                    "string-not-dict",
                ]
            }
        ),
        encoding="utf-8",
    )
    subs = load_subprojects(project)
    assert [s.slug for s in subs] == ["good"]


def test_register_appends_new(tmp_path: Path) -> None:
    project = _make_root(tmp_path)
    register_subproject(project, Subproject(slug="frontend", path="./frontend", description="UI"))
    subs = load_subprojects(project)
    assert len(subs) == 1
    assert subs[0].slug == "frontend"


def test_register_overwrites_same_slug(tmp_path: Path) -> None:
    project = _make_root(tmp_path)
    register_subproject(project, Subproject(slug="frontend", path="./old", description="v1"))
    register_subproject(project, Subproject(slug="frontend", path="./new", description="v2"))
    subs = load_subprojects(project)
    assert len(subs) == 1
    assert subs[0].path == "./new"
    assert subs[0].description == "v2"


def test_register_keeps_alphabetical_order(tmp_path: Path) -> None:
    project = _make_root(tmp_path)
    register_subproject(project, Subproject(slug="zeta", path="./z"))
    register_subproject(project, Subproject(slug="alpha", path="./a"))
    register_subproject(project, Subproject(slug="mid", path="./m"))
    slugs = [s.slug for s in load_subprojects(project)]
    assert slugs == ["alpha", "mid", "zeta"]


def test_unregister_removes_entry(tmp_path: Path) -> None:
    project = _make_root(tmp_path)
    register_subproject(project, Subproject(slug="frontend", path="./f"))
    register_subproject(project, Subproject(slug="backend", path="./b"))
    assert unregister_subproject(project, "frontend") is True
    slugs = [s.slug for s in load_subprojects(project)]
    assert slugs == ["backend"]


def test_unregister_unknown_returns_false(tmp_path: Path) -> None:
    project = _make_root(tmp_path)
    assert unregister_subproject(project, "ghost") is False


# ---------- find_parent_project ----------


def test_find_parent_returns_ancestor_project(tmp_path: Path) -> None:
    parent = _make_root(tmp_path, name="myorg")
    child = init_project(parent.root / "frontend", name="frontend")
    found = find_parent_project(child)
    assert found is not None
    assert found.root == parent.root


def test_find_parent_returns_none_for_top_level(tmp_path: Path) -> None:
    parent = _make_root(tmp_path)
    assert find_parent_project(parent) is None


def test_find_parent_skips_non_veles_intermediate(tmp_path: Path) -> None:
    """Non-Veles directories between child and ancestor are skipped."""
    parent = init_project(tmp_path / "myorg", name="myorg")
    intermediate = parent.root / "services" / "api"
    intermediate.mkdir(parents=True)
    child = init_project(intermediate / "auth", name="auth")
    found = find_parent_project(child)
    assert found is not None
    assert found.root == parent.root


# ---------- init_subproject ----------


def test_init_creates_subproject_and_registers(tmp_path: Path) -> None:
    parent = _make_root(tmp_path)
    sub = init_subproject(parent, "frontend", description="UI bits")
    assert (sub.root / ".veles" / "project.toml").is_file()
    registered = load_subprojects(parent)
    assert len(registered) == 1
    assert registered[0].slug == sub.name
    assert registered[0].path == "./frontend"
    assert registered[0].description == "UI bits"


def test_init_with_nested_subdir_uses_relative_path(tmp_path: Path) -> None:
    parent = _make_root(tmp_path)
    sub = init_subproject(parent, "services/api")
    registered = load_subprojects(parent)
    assert registered[0].path == "./services/api"
    assert sub.root == (parent.root / "services" / "api").resolve()


def test_init_refuses_dotdot_path(tmp_path: Path) -> None:
    parent = _make_root(tmp_path)
    with pytest.raises(ValueError, match="invalid subdir"):
        init_subproject(parent, "../escape")


def test_init_refuses_absolute_path(tmp_path: Path) -> None:
    parent = _make_root(tmp_path)
    with pytest.raises(ValueError, match="invalid subdir"):
        init_subproject(parent, "/etc/hostname")


def test_init_refuses_when_subdir_equals_root(tmp_path: Path) -> None:
    parent = _make_root(tmp_path)
    with pytest.raises(ValueError, match="cannot equal"):
        init_subproject(parent, ".")


def test_init_refuses_already_initialised(tmp_path: Path) -> None:
    parent = _make_root(tmp_path)
    init_subproject(parent, "frontend")
    with pytest.raises(ProjectAlreadyExists):
        init_subproject(parent, "frontend")


# ---------- MemoryRouter recall integration ----------


def test_recall_includes_subproject_hits(tmp_path: Path) -> None:
    parent = _make_root(tmp_path)
    child = init_subproject(parent, "frontend")
    # Seed pages: parent has nothing matching, child has a page on "auth".
    Wiki(child.wiki_root).write_page(
        slug="auth", title="Auth flow", category="concepts", content="OAuth pkce details"
    )
    router = MemoryRouter(parent)
    hits = router.recall("OAuth pkce")
    assert any(h.rel_path.startswith("frontend:") for h in hits)
    sub_hit = next(h for h in hits if h.rel_path.startswith("frontend:"))
    assert sub_hit.title.startswith("[frontend]")


def test_recall_skips_subprojects_without_initialised_wiki(tmp_path: Path) -> None:
    """Registered subproject whose .veles/ has been deleted is skipped silently."""
    parent = _make_root(tmp_path)
    register_subproject(parent, Subproject(slug="ghost", path="./ghost", description=""))
    router = MemoryRouter(parent)
    # Should not crash; falls back to empty hit list (parent wiki has nothing).
    hits = router.recall("anything")
    assert hits == []


def test_recall_caps_total_hits(tmp_path: Path) -> None:
    parent = _make_root(tmp_path)
    child = init_subproject(parent, "frontend")
    parent_wiki = Wiki(parent.wiki_root)
    child_wiki = Wiki(child.wiki_root)
    for i in range(5):
        parent_wiki.write_page(
            slug=f"p{i}", title=f"Parent {i}", category="concepts", content="auth flow"
        )
        child_wiki.write_page(
            slug=f"c{i}", title=f"Child {i}", category="concepts", content="auth flow"
        )
    router = MemoryRouter(parent)
    hits = router.recall("auth flow", limit=5)
    assert len(hits) <= 5


def test_recall_returns_empty_for_blank_query(tmp_path: Path) -> None:
    parent = _make_root(tmp_path)
    init_subproject(parent, "frontend")
    router = MemoryRouter(parent)
    assert router.recall("   ") == []


def test_resolve_subproject_path_is_absolute(tmp_path: Path) -> None:
    parent = _make_root(tmp_path)
    sub = Subproject(slug="x", path="./services/x", description="")
    resolved = resolve_subproject_path(parent, sub)
    assert resolved.is_absolute()
    assert resolved == (parent.root / "services" / "x").resolve()

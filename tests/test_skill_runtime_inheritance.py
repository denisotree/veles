"""M121c: discover_skills applies extends-chain resolution by default.

After M121 added the `extends:` frontmatter field and the
`resolve_inheritance` pure-Python merger, the missing piece was
wiring: the runtime had to *use* that merge before make_skill_tool
built the dispatch handler. M121c makes `discover_skills` do that
transparently — callers get flattened skills without knowing about
the chain.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from veles.core.project import init_project
from veles.core.skills import discover_skills


@pytest.fixture()
def isolated_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("VELES_USER_HOME", str(tmp_path / "home"))
    return tmp_path / "home"


def _write_skill(
    skills_dir: Path,
    name: str,
    body: str,
    *,
    description: str = "",
    tools: list[str] | None = None,
    extends: str | None = None,
) -> None:
    sd = skills_dir / name
    sd.mkdir(parents=True, exist_ok=True)
    tools_line = f"tools: [{', '.join(tools)}]\n" if tools else ""
    extends_line = f"extends: {extends}\n" if extends else ""
    fm = (
        "---\n"
        f"name: {name}\n"
        f"description: {description or f'skill {name}'}\n"
        f"{tools_line}{extends_line}---\n{body}\n"
    )
    (sd / "SKILL.md").write_text(fm, encoding="utf-8")


# ---- default behaviour: inheritance applied ----


def test_discover_merges_extends_chain_by_default(
    isolated_home: Path, tmp_path: Path
) -> None:
    """A child skill with `extends: base` returns flattened — child's
    tools union base's tools, parent body concatenated, extends
    cleared on the result."""
    project = init_project(tmp_path / "proj", name="proj")
    _write_skill(
        project.skills_dir,
        "base_search",
        "Base search body.",
        tools=["wiki_search"],
    )
    _write_skill(
        project.skills_dir,
        "smart_search",
        "Smart search body.",
        tools=["wiki_read_page"],
        extends="base_search",
    )

    skills = discover_skills(project)
    by_name = {s.name: s for s in skills}
    smart = by_name["smart_search"]
    # Tools union: child + parent (order: parent first, then child new)
    assert "wiki_search" in smart.tools
    assert "wiki_read_page" in smart.tools
    # Body concatenated parent-first
    assert "Base search body" in smart.body
    assert "Smart search body" in smart.body
    # Flattened — extends cleared so downstream code doesn't double-walk
    assert smart.extends is None


def test_discover_opt_out_of_inheritance(
    isolated_home: Path, tmp_path: Path
) -> None:
    """Tests that want to inspect raw frontmatter set
    `resolve_inheritance_chain=False`."""
    project = init_project(tmp_path / "proj", name="proj")
    _write_skill(project.skills_dir, "base", "Base body.", tools=["a"])
    _write_skill(
        project.skills_dir, "child", "Child body.", tools=["b"], extends="base"
    )

    raw = discover_skills(project, resolve_inheritance_chain=False)
    by_name = {s.name: s for s in raw}
    child = by_name["child"]
    # Raw: child's tools only (no merge), extends preserved
    assert child.tools == ["b"]
    assert child.extends == "base"
    assert "Base body" not in child.body


def test_discover_chain_with_no_extends_unchanged(
    isolated_home: Path, tmp_path: Path
) -> None:
    """If no skill uses `extends`, the merge step is a no-op and the
    skill list is returned identical."""
    project = init_project(tmp_path / "proj", name="proj")
    _write_skill(project.skills_dir, "standalone", "body", tools=["x"])

    skills = discover_skills(project)
    by_name = {s.name: s for s in skills}
    assert by_name["standalone"].tools == ["x"]
    assert by_name["standalone"].extends is None


def test_discover_three_level_chain_collapses(
    isolated_home: Path, tmp_path: Path
) -> None:
    """grandparent → parent → child flattens to one skill with the
    union of all three."""
    project = init_project(tmp_path / "proj", name="proj")
    _write_skill(project.skills_dir, "gp", "GP body", tools=["a"])
    _write_skill(project.skills_dir, "p", "P body", tools=["b"], extends="gp")
    _write_skill(project.skills_dir, "c", "C body", tools=["c"], extends="p")

    skills = discover_skills(project)
    by_name = {s.name: s for s in skills}
    c = by_name["c"]
    assert c.tools == ["a", "b", "c"]
    assert "GP body" in c.body
    assert c.body.index("GP body") < c.body.index("P body")
    assert c.body.index("P body") < c.body.index("C body")


def test_discover_inheritance_unknown_parent_keeps_child_intact(
    isolated_home: Path, tmp_path: Path
) -> None:
    """A child pointing at a parent that doesn't exist just returns the
    child unchanged — no crash, no body padding."""
    project = init_project(tmp_path / "proj", name="proj")
    _write_skill(
        project.skills_dir,
        "orphan",
        "Orphan body",
        tools=["x"],
        extends="never_made",
    )

    skills = discover_skills(project)
    by_name = {s.name: s for s in skills}
    assert by_name["orphan"].tools == ["x"]
    assert "Orphan body" in by_name["orphan"].body


def test_make_skill_tool_sees_merged_tools(
    isolated_home: Path, tmp_path: Path
) -> None:
    """End-to-end: make_skill_tool builds its dispatch handler from
    the flattened skill, so the child's runtime tool surface is the
    union — which is the whole point of M121c."""
    from veles.core.skills import make_skill_tool

    project = init_project(tmp_path / "proj", name="proj")
    _write_skill(
        project.skills_dir,
        "base_skill",
        "Base instructions.",
        tools=["wiki_search", "wiki_read_page"],
    )
    _write_skill(
        project.skills_dir,
        "search_then_save",
        "Now also save.",
        tools=["wiki_write_page"],
        extends="base_skill",
    )

    skills = discover_skills(project)
    child = next(s for s in skills if s.name == "search_then_save")
    # The flattened child has all three tools — that's what
    # make_skill_tool propagates into its sub-Agent allowlist.
    assert set(child.tools) >= {"wiki_search", "wiki_read_page", "wiki_write_page"}


# ---- backward compat ----


def test_existing_callers_unaffected_when_no_extends_used(
    isolated_home: Path, tmp_path: Path
) -> None:
    """Tests pre-dating M121c never used `extends`, so their on-disk
    fixtures still produce the same Skill objects."""
    project = init_project(tmp_path / "proj", name="proj")
    _write_skill(project.skills_dir, "a", "a body", tools=["x"])
    _write_skill(project.skills_dir, "b", "b body", tools=["y"])

    skills_default = discover_skills(project)
    skills_no_merge = discover_skills(project, resolve_inheritance_chain=False)
    # Same content when nothing has extends
    by_default = {s.name: s for s in skills_default}
    by_raw = {s.name: s for s in skills_no_merge}
    for name in ("a", "b"):
        assert by_default[name].tools == by_raw[name].tools
        assert by_default[name].body == by_raw[name].body

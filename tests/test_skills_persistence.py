"""M121.1 + M121.2: skill catalogue + inheritance resolver."""

from __future__ import annotations

from pathlib import Path

import pytest

from veles.core.memory import SessionStore
from veles.core.skills import Skill
from veles.core.skills_persistence import (
    get_skill,
    inheritance_chain,
    list_skills,
    record_skill_use,
    resolve_inheritance,
    skill_telemetry,
    upsert_skill,
)


# ---- helpers ----


def _skill(
    name: str,
    *,
    description: str = "",
    body: str = "",
    tools: list[str] | None = None,
    parameters: list[dict] | None = None,
    extends: str | None = None,
    scope: str = "project",
    max_iterations: int = 3,
) -> Skill:
    return Skill(
        name=name,
        description=description or f"skill {name}",
        body=body or f"body of {name}",
        path=Path(f"/fake/{name}/SKILL.md"),
        tools=list(tools or []),
        parameters=list(parameters or []),
        scope=scope,
        extends=extends,
        max_iterations=max_iterations,
    )


@pytest.fixture()
def conn(tmp_path: Path):
    store = SessionStore(tmp_path / "memory.db")
    yield store._conn
    store._conn.close()


# ---- upsert_skill ----


def test_upsert_creates_row(conn) -> None:
    sid = upsert_skill(conn, _skill("alpha"))
    assert sid > 0
    rec = get_skill(conn, "alpha")
    assert rec is not None
    assert rec.name == "alpha"
    assert rec.scope == "project"
    assert rec.base_skill_id is None


def test_upsert_is_idempotent_on_name(conn) -> None:
    sid1 = upsert_skill(conn, _skill("alpha"))
    sid2 = upsert_skill(conn, _skill("alpha", description="updated"))
    assert sid1 == sid2
    rec = get_skill(conn, "alpha")
    assert rec is not None and rec.description == "updated"


def test_upsert_resolves_extends_to_id(conn) -> None:
    upsert_skill(conn, _skill("base"))
    upsert_skill(conn, _skill("child", extends="base"))
    base = get_skill(conn, "base")
    child = get_skill(conn, "child")
    assert child is not None and base is not None
    assert child.base_skill_id == base.id


def test_upsert_unknown_extends_stays_null(conn) -> None:
    upsert_skill(conn, _skill("orphan", extends="does_not_exist"))
    rec = get_skill(conn, "orphan")
    assert rec is not None
    assert rec.base_skill_id is None


def test_upsert_serialises_frontmatter(conn) -> None:
    upsert_skill(
        conn,
        _skill(
            "complex",
            tools=["read_file", "write_file"],
            parameters=[{"name": "path", "type": "string"}],
            max_iterations=7,
        ),
    )
    import json

    rec = conn.execute(
        "SELECT frontmatter_json FROM skills WHERE name = ?", ("complex",)
    ).fetchone()
    payload = json.loads(rec["frontmatter_json"])
    assert payload["tools"] == ["read_file", "write_file"]
    assert payload["max_iterations"] == 7
    assert payload["parameters"] == [{"name": "path", "type": "string"}]


# ---- list_skills ----


def test_list_sorted_and_filtered(conn) -> None:
    upsert_skill(conn, _skill("z_user", scope="user"))
    upsert_skill(conn, _skill("a_proj", scope="project"))
    names = [s.name for s in list_skills(conn)]
    assert names == ["a_proj", "z_user"]
    proj_only = [s.name for s in list_skills(conn, scope="project")]
    assert proj_only == ["a_proj"]


# ---- skill_uses ----


def test_record_skill_use_aggregates(conn) -> None:
    upsert_skill(conn, _skill("alpha"))
    record_skill_use(conn, skill_name="alpha", ok=True, latency_ms=10, now=100.0)
    record_skill_use(conn, skill_name="alpha", ok=True, latency_ms=20, now=200.0)
    record_skill_use(conn, skill_name="alpha", ok=False, latency_ms=15, now=300.0)
    t = skill_telemetry(conn, "alpha")
    assert t.use_count == 3
    assert t.success_count == 2
    assert t.error_count == 1
    assert t.success_rate == pytest.approx(2 / 3)
    assert t.last_used_at == 300.0


def test_record_use_on_unknown_skill_is_noop(conn) -> None:
    uid = record_skill_use(conn, skill_name="never_made", ok=True)
    assert uid == 0


def test_telemetry_zero_when_never_used(conn) -> None:
    upsert_skill(conn, _skill("alpha"))
    t = skill_telemetry(conn, "alpha")
    assert t.use_count == 0
    assert t.success_rate == 0.0


# ---- inheritance_chain ----


def test_chain_returns_three_levels(conn) -> None:
    upsert_skill(conn, _skill("root"))
    upsert_skill(conn, _skill("mid", extends="root"))
    upsert_skill(conn, _skill("leaf", extends="mid"))
    chain = inheritance_chain(conn, "leaf")
    assert [r.name for r in chain] == ["leaf", "mid", "root"]


def test_chain_unknown_name_empty(conn) -> None:
    assert inheritance_chain(conn, "ghost") == []


def test_chain_single_node_when_no_parent(conn) -> None:
    upsert_skill(conn, _skill("solo"))
    chain = inheritance_chain(conn, "solo")
    assert [r.name for r in chain] == ["solo"]


# ---- resolve_inheritance (pure Python) ----


def test_resolve_no_parent_returns_original() -> None:
    s = _skill("solo", tools=["a"])
    merged = resolve_inheritance(s, by_name={"solo": s})
    assert merged is s  # identity, no copy when no chain


def test_resolve_merges_tools_union() -> None:
    base = _skill("base", tools=["a", "b"])
    child = _skill("child", tools=["b", "c"], extends="base")
    merged = resolve_inheritance(child, by_name={"base": base, "child": child})
    assert merged.tools == ["a", "b", "c"]


def test_resolve_concatenates_body_parent_first() -> None:
    base = _skill("base", body="parent steps")
    child = _skill("child", body="child steps", extends="base")
    merged = resolve_inheritance(child, by_name={"base": base, "child": child})
    assert merged.body.startswith("parent steps")
    assert "child steps" in merged.body


def test_resolve_child_description_wins() -> None:
    base = _skill("base", description="base desc")
    child = _skill("child", description="child desc", extends="base")
    merged = resolve_inheritance(child, by_name={"base": base, "child": child})
    assert merged.description == "child desc"


def test_resolve_parameters_override_by_name() -> None:
    base = _skill(
        "base",
        parameters=[
            {"name": "path", "type": "string"},
            {"name": "max", "type": "int", "default": 10},
        ],
    )
    child = _skill(
        "child",
        parameters=[
            {"name": "max", "type": "int", "default": 100},  # overrides base
            {"name": "verbose", "type": "bool"},  # new
        ],
        extends="base",
    )
    merged = resolve_inheritance(child, by_name={"base": base, "child": child})
    params_by_name = {p["name"]: p for p in merged.parameters}
    assert params_by_name["path"]["type"] == "string"
    assert params_by_name["max"]["default"] == 100  # child override
    assert "verbose" in params_by_name


def test_resolve_clears_extends_on_flattened() -> None:
    base = _skill("base")
    child = _skill("child", extends="base")
    merged = resolve_inheritance(child, by_name={"base": base, "child": child})
    assert merged.extends is None


def test_resolve_chain_three_deep() -> None:
    root = _skill("root", tools=["r"], body="root body")
    mid = _skill("mid", tools=["m"], body="mid body", extends="root")
    leaf = _skill("leaf", tools=["l"], body="leaf body", extends="mid")
    merged = resolve_inheritance(
        leaf, by_name={"root": root, "mid": mid, "leaf": leaf}
    )
    # Tools accumulate root → mid → leaf order
    assert merged.tools == ["r", "m", "l"]
    # Body flows root → mid → leaf
    assert "root body" in merged.body
    assert merged.body.index("root body") < merged.body.index("mid body")
    assert merged.body.index("mid body") < merged.body.index("leaf body")


def test_resolve_handles_cycle_silently() -> None:
    """A → B → A — should stop walking instead of infinite-looping."""
    a = _skill("a", extends="b")
    b = _skill("b", extends="a")
    merged = resolve_inheritance(a, by_name={"a": a, "b": b})
    # Either flattens to a 2-node chain or stays at original — neither
    # is a hang, which is the contract.
    assert merged.name == "a"


def test_resolve_unknown_parent_stops_chain() -> None:
    child = _skill("child", tools=["c"], extends="missing_parent")
    merged = resolve_inheritance(child, by_name={"child": child})
    assert merged.tools == ["c"]


# ---- end-to-end via discover_skills ----


# ---- skill_tool_refs sync ----


def test_upsert_creates_tool_refs_for_known_tools(conn) -> None:
    """Tools that exist in the catalogue get linked via skill_tool_refs."""
    from veles.core.skills_persistence import get_skill_tool_refs
    from veles.core.tools.persistence import upsert_tool
    from veles.core.tools.registry import ToolEntry

    upsert_tool(
        conn,
        ToolEntry(
            name="read_file",
            description="d",
            parameter_schema={"type": "object", "properties": {}, "required": []},
            handler=lambda **_kw: "",
            is_async=False,
        ),
    )
    upsert_skill(conn, _skill("alpha", tools=["read_file"]))
    assert get_skill_tool_refs(conn, "alpha") == ["read_file"]


def test_upsert_silently_skips_unknown_tools(conn) -> None:
    """A tool that isn't in the catalogue (in-memory builtin only) is
    skipped — the skill's frontmatter list still drives runtime."""
    from veles.core.skills_persistence import get_skill_tool_refs

    upsert_skill(conn, _skill("alpha", tools=["never_made_tool"]))
    assert get_skill_tool_refs(conn, "alpha") == []


def test_upsert_re_syncs_refs_on_update(conn) -> None:
    """Removing a tool from the skill's list drops the edge."""
    from veles.core.skills_persistence import get_skill_tool_refs
    from veles.core.tools.persistence import upsert_tool
    from veles.core.tools.registry import ToolEntry

    for name in ("read_file", "write_file"):
        upsert_tool(
            conn,
            ToolEntry(
                name=name,
                description=name,
                parameter_schema={"type": "object", "properties": {}, "required": []},
                handler=lambda **_kw: "",
                is_async=False,
            ),
        )
    upsert_skill(conn, _skill("alpha", tools=["read_file", "write_file"]))
    assert set(get_skill_tool_refs(conn, "alpha")) == {"read_file", "write_file"}
    # Drop write_file from the skill — refs should follow.
    upsert_skill(conn, _skill("alpha", tools=["read_file"]))
    assert get_skill_tool_refs(conn, "alpha") == ["read_file"]


def test_discover_reads_extends_from_frontmatter(tmp_path: Path) -> None:
    """discover_skills picks up the new `extends` frontmatter field."""
    from veles.core.skills import discover_skills

    # Build a fake project with two skills
    proj_dir = tmp_path / "proj"
    proj_dir.mkdir()
    skills_root = proj_dir / ".veles" / "skills"
    base_dir = skills_root / "base"
    child_dir = skills_root / "child"
    base_dir.mkdir(parents=True)
    child_dir.mkdir(parents=True)
    (base_dir / "SKILL.md").write_text(
        "---\nname: base\ndescription: base skill\n---\nbase body\n",
        encoding="utf-8",
    )
    (child_dir / "SKILL.md").write_text(
        "---\nname: child\ndescription: child skill\nextends: base\n---\nchild body\n",
        encoding="utf-8",
    )
    # Minimal project shim — `discover_skills` only uses project.skills_dir
    # and the user_home() default — provide a Project-like object.
    from veles.core.project import init_project

    project = init_project(proj_dir, name="proj", force=True)
    # init_project recreates .veles, so re-write the skills now.
    (project.skills_dir / "base").mkdir(parents=True, exist_ok=True)
    (project.skills_dir / "child").mkdir(parents=True, exist_ok=True)
    (project.skills_dir / "base" / "SKILL.md").write_text(
        "---\nname: base\ndescription: base skill\n---\nbase body\n",
        encoding="utf-8",
    )
    (project.skills_dir / "child" / "SKILL.md").write_text(
        "---\nname: child\ndescription: child skill\nextends: base\n---\nchild body\n",
        encoding="utf-8",
    )

    # M121c: discover_skills resolves the chain by default. To inspect
    # the raw on-disk extends field, opt out of the merge.
    skills = discover_skills(project, resolve_inheritance_chain=False)
    by_name = {s.name: s for s in skills}
    assert by_name["child"].extends == "base"
    assert by_name["base"].extends is None

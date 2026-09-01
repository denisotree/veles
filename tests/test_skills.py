"""Unit tests for veles.core.skills — frontmatter, discovery, telemetry, tool wiring."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.conftest import StubProvider
from veles.core.context import reset_active_project, set_active_project
from veles.core.project import init_project
from veles.core.provider import ProviderResponse, TokenUsage
from veles.core.skills import (
    bump_telemetry,
    discover_skills,
    make_skill_tool,
    parse_frontmatter,
    render_frontmatter,
)
from veles.core.tools.registry import Registry, ToolEntry


def test_parse_frontmatter_basic() -> None:
    text = (
        "---\n"
        "name: my-skill\n"
        "description: Does a thing.\n"
        "max_iterations: 5\n"
        "use_count: 12\n"
        "---\n"
        "Body text here.\n"
    )
    fm, body = parse_frontmatter(text)
    assert fm == {
        "name": "my-skill",
        "description": "Does a thing.",
        "max_iterations": 5,
        "use_count": 12,
    }
    assert body == "Body text here.\n"


def test_parse_frontmatter_handles_lists() -> None:
    text = "---\ntools: [run_shell, read_file]\n---\n"
    fm, _ = parse_frontmatter(text)
    assert fm == {"tools": ["run_shell", "read_file"]}


def test_parse_frontmatter_handles_bool_int_null() -> None:
    text = "---\nflag: true\nother: false\nn: 42\nlast_used: null\n---\n"
    fm, _ = parse_frontmatter(text)
    assert fm == {"flag": True, "other": False, "n": 42, "last_used": None}


def test_parse_frontmatter_no_frontmatter() -> None:
    text = "Just markdown, no frontmatter.\n"
    fm, body = parse_frontmatter(text)
    assert fm == {}
    assert body == text


def test_render_frontmatter_round_trip() -> None:
    original_fm = {
        "name": "demo",
        "description": "A demo skill.",
        "tools": ["run_shell", "read_file"],
        "max_iterations": 5,
        "use_count": 0,
        "last_used": None,
    }
    body = "Body content here."
    rendered = render_frontmatter(original_fm, body)
    fm2, body2 = parse_frontmatter(rendered)
    assert fm2 == original_fm
    assert body2.strip() == body.strip()


def test_discover_skills_empty_project(tmp_path: Path) -> None:
    project = init_project(tmp_path, name="t")
    assert discover_skills(project) == []


def test_discover_skills_finds_one(tmp_path: Path) -> None:
    project = init_project(tmp_path, name="t")
    skill_dir = project.skills_dir / "echo"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\nname: echo\ndescription: Echoes the input.\ntools: []\n---\nYou are an echo bot.",
        encoding="utf-8",
    )
    skills = discover_skills(project)
    assert len(skills) == 1
    assert skills[0].name == "echo"
    assert skills[0].description == "Echoes the input."
    assert skills[0].tools == []
    assert "echo bot" in skills[0].body


def test_discover_skills_skips_invalid_frontmatter(tmp_path: Path, caplog) -> None:
    import logging

    project = init_project(tmp_path, name="t")
    bad_dir = project.skills_dir / "broken"
    bad_dir.mkdir(parents=True)
    (bad_dir / "SKILL.md").write_text(
        "---\nname:\ndescription:\n---\nbody",
        encoding="utf-8",
    )
    # M-R2.8: warning goes through the logger now so daemon log captures
    # it; assert via caplog instead of stderr.
    with caplog.at_level(logging.WARNING, logger="veles.core.skills"):
        skills = discover_skills(project)
    assert skills == []
    assert any("skipping skill" in r.message for r in caplog.records)


def test_discover_skills_skips_missing_skill_md(tmp_path: Path) -> None:
    project = init_project(tmp_path, name="t")
    (project.skills_dir / "empty-dir").mkdir()
    assert discover_skills(project) == []


def test_bump_telemetry_success_increments_use_and_success(tmp_path: Path) -> None:
    """M244: counters live in memory.db now, and `discover_skills` overlays them
    back onto the loaded Skill so every reader keeps working unchanged."""
    project = init_project(tmp_path, name="t")
    skill_dir = project.skills_dir / "echo"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\nname: echo\ndescription: e\n---\nbody", encoding="utf-8"
    )
    token = set_active_project(project)
    try:
        skill = discover_skills(project)[0]
        assert skill.use_count == 0
        bump_telemetry(skill, success=True)
        # In-place update for the caller that just ran it.
        assert skill.use_count == 1
        assert skill.success_count == 1

        skills_after = discover_skills(project)
        assert skills_after[0].use_count == 1
        assert skills_after[0].success_count == 1
        assert skills_after[0].error_count == 0
        assert skills_after[0].last_used is not None
        assert skills_after[0].last_used.endswith("Z")
    finally:
        reset_active_project(token)


def test_bump_telemetry_failure_increments_use_and_error(tmp_path: Path) -> None:
    project = init_project(tmp_path, name="t")
    skill_dir = project.skills_dir / "echo"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\nname: echo\ndescription: e\n---\nbody", encoding="utf-8"
    )
    token = set_active_project(project)
    try:
        skill = discover_skills(project)[0]
        bump_telemetry(skill, success=True)
        bump_telemetry(skill, success=False)
        s = discover_skills(project)[0]
        assert s.use_count == 2
        assert s.success_count == 1
        assert s.error_count == 1
    finally:
        reset_active_project(token)


def test_bump_telemetry_never_writes_to_the_skill_file(tmp_path: Path) -> None:
    """The defect M244 fixes: `builtin` and layout skills live inside the
    installed package, so rewriting frontmatter mutated the distribution —
    site-packages on a pip install, a dirty tree on a checkout. Observed live
    2026-09-01 when a sandbox run modified two SKILL.md files in the repo.
    """
    project = init_project(tmp_path, name="t")
    skill_dir = project.skills_dir / "echo"
    skill_dir.mkdir(parents=True)
    path = skill_dir / "SKILL.md"
    original = "---\nname: echo\ndescription: e\n---\nMulti-line\nbody\nwith content."
    path.write_text(original, encoding="utf-8")

    token = set_active_project(project)
    try:
        bump_telemetry(discover_skills(project)[0], success=True)
    finally:
        reset_active_project(token)

    assert path.read_text(encoding="utf-8") == original, "the source file is untouched"
    assert not (skill_dir / "SKILL.md.lock").exists(), "no lock sidecar either"
    assert not (skill_dir / "SKILL.md.tmp").exists()


def test_builtin_skill_telemetry_does_not_touch_the_package(tmp_path: Path) -> None:
    """A `builtin`-scope skill is inside the veles package; its file must never
    be written, and telemetry must still be recorded."""
    from veles.core.skills import mount_builtin_skills

    project = init_project(tmp_path, name="t")
    builtin = mount_builtin_skills()
    assert builtin, "expected builtin skills to mount"
    skill = builtin[0]
    before = skill.path.read_text(encoding="utf-8")

    token = set_active_project(project)
    try:
        bump_telemetry(skill, success=True)
    finally:
        reset_active_project(token)

    assert skill.path.read_text(encoding="utf-8") == before
    assert not skill.path.with_suffix(skill.path.suffix + ".lock").exists()


def test_bump_telemetry_leaves_body_and_frontmatter_alone(tmp_path: Path) -> None:
    """Superseded by M244: the file is no longer the telemetry store, so the
    whole file — body and frontmatter — must survive a bump untouched."""
    project = init_project(tmp_path, name="t")
    skill_dir = project.skills_dir / "echo"
    skill_dir.mkdir(parents=True)
    original = "---\nname: echo\ndescription: e\n---\nMulti-line\nbody\nwith content."
    (skill_dir / "SKILL.md").write_text(original, encoding="utf-8")

    token = set_active_project(project)
    try:
        bump_telemetry(discover_skills(project)[0], success=True)
    finally:
        reset_active_project(token)

    assert (skill_dir / "SKILL.md").read_text(encoding="utf-8") == original


def test_load_skill_parses_telemetry_fields(tmp_path: Path) -> None:
    project = init_project(tmp_path, name="t")
    skill_dir = project.skills_dir / "echo"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\n"
        "name: echo\n"
        "description: e\n"
        "use_count: 50\n"
        "success_count: 47\n"
        "error_count: 3\n"
        "last_used: 2026-05-10T12:00:00Z\n"
        "last_error_at: 2026-05-09T08:30:00Z\n"
        "---\nbody",
        encoding="utf-8",
    )
    s = discover_skills(project)[0]
    assert s.use_count == 50
    assert s.success_count == 47
    assert s.error_count == 3
    assert s.last_used == "2026-05-10T12:00:00Z"
    assert s.last_error_at == "2026-05-09T08:30:00Z"


def test_bump_telemetry_concurrent_threads_serialize_no_lost_updates(
    tmp_path: Path,
) -> None:
    """No lost updates under concurrency.

    Pre-M244 this guarded a read-modify-write on SKILL.md behind a `file_lock`.
    Now every bump is an append-only INSERT into `skill_uses`, so the race the
    lock existed for is gone by construction — but the invariant is the same and
    still worth holding: N bumps must count as N.
    """
    import threading

    project = init_project(tmp_path, name="t")
    skill_dir = project.skills_dir / "echo"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\nname: echo\ndescription: e\n---\nbody", encoding="utf-8"
    )
    workers = 4
    iterations = 10

    def worker() -> None:
        token = set_active_project(project)
        try:
            for _ in range(iterations):
                # Re-discover per call so each thread holds its own Skill
                # dataclass — a shared object would make the in-memory counters
                # coincide and we'd be testing the wrong thing.
                bump_telemetry(discover_skills(project)[0], success=True)
        finally:
            reset_active_project(token)

    threads = [threading.Thread(target=worker) for _ in range(workers)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    token = set_active_project(project)
    try:
        final = discover_skills(project)[0]
    finally:
        reset_active_project(token)
    assert final.use_count == workers * iterations
    assert final.success_count == workers * iterations
    assert final.error_count == 0


def test_make_skill_tool_returns_tool_entry(tmp_path: Path) -> None:
    project = init_project(tmp_path, name="t")
    _write_simple_skill(project)
    skill = discover_skills(project)[0]
    entry = make_skill_tool(
        skill,
        provider=_StubProvider(),
        model="test-model",
        base_registry=Registry(),
    )
    assert isinstance(entry, ToolEntry)
    assert entry.name == skill.name
    assert entry.description == skill.description
    schema = entry.parameter_schema
    assert schema["properties"]["input"]["type"] == "string"


def test_skill_handler_invokes_subagent_and_bumps_telemetry_success(tmp_path: Path) -> None:
    project = init_project(tmp_path, name="t")
    _write_simple_skill(project)
    skill = discover_skills(project)[0]
    provider = _StubProvider(reply="hello-from-skill")
    base_registry = Registry()
    entry = make_skill_tool(
        skill, provider=provider, model="test-model", base_registry=base_registry
    )
    token = set_active_project(project)
    try:
        out = entry.handler(input="ignored")
        # System prompt should match skill body
        assert provider.last_system == skill.body
        skills_after = discover_skills(project)
    finally:
        reset_active_project(token)
    assert out == "hello-from-skill"
    # M244: counters come from `skill_uses` in memory.db, keyed off the active
    # project — the handler records nothing when it runs outside one.
    assert skills_after[0].use_count == 1
    assert skills_after[0].success_count == 1
    assert skills_after[0].error_count == 0


def test_skill_handler_records_error_on_max_iterations(tmp_path: Path) -> None:
    project = init_project(tmp_path, name="t")
    _write_simple_skill(project)
    skill = discover_skills(project)[0]
    # _StubProvider returns an empty text reply with no tool calls — but stopped
    # reason for empty text is "empty", not "completed". To reliably exercise
    # the error path, force max_iterations by having the provider return
    # tool_calls referencing a non-existent tool indefinitely.
    provider = _StubProvider(reply="")  # empty → stopped_reason="empty"
    entry = make_skill_tool(skill, provider=provider, model="test-model", base_registry=Registry())
    token = set_active_project(project)
    try:
        out = entry.handler(input="ignored")
        s = discover_skills(project)[0]
    finally:
        reset_active_project(token)
    # Empty reply still flows back; telemetry records it as error.
    assert out == ""
    assert s.use_count == 1
    assert s.success_count == 0
    assert s.error_count == 1


def _write_simple_skill(project) -> None:
    skill_dir = project.skills_dir / "echo"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\n"
        "name: echo\n"
        "description: stub\n"
        "tools: []\n"
        "max_iterations: 2\n"
        "use_count: 0\n"
        "---\n"
        "Skill body — system prompt for the sub-agent.",
        encoding="utf-8",
    )


class _StubProvider(StubProvider):
    """Fixed-reply provider; exposes the last system message it saw."""

    def __init__(self, reply: str = "ok") -> None:
        super().__init__(
            [ProviderResponse(text=reply, tool_calls=[], usage=TokenUsage(), finish_reason="stop")],
            repeat_last=True,
        )

    @property
    def last_system(self) -> str | None:
        for call in reversed(self.calls):
            for m in call["messages"]:
                if m.role == "system":
                    return m.content
        return None


@pytest.fixture(autouse=False)
def silence_tool_warnings(capsys):
    """Helper if needed; not used by all tests but keeps capsys available."""
    return capsys


# ---------- M7: cross-skill composition ----------


def _write_named_skill(project, *, name: str, tools: list[str], body: str) -> None:
    skill_dir = project.skills_dir / name
    skill_dir.mkdir(parents=True, exist_ok=True)
    tools_repr = "[" + ", ".join(tools) + "]"
    (skill_dir / "SKILL.md").write_text(
        f"---\n"
        f"name: {name}\n"
        f"description: stub for {name}\n"
        f"tools: {tools_repr}\n"
        f"max_iterations: 2\n"
        f"use_count: 0\n"
        f"---\n"
        f"{body}",
        encoding="utf-8",
    )


def test_cross_skill_sub_registry_includes_listed_skill(tmp_path: Path) -> None:
    project = init_project(tmp_path, name="t")
    _write_named_skill(project, name="inner", tools=[], body="inner body")
    _write_named_skill(project, name="outer", tools=["inner"], body="outer body")
    skills = {s.name: s for s in discover_skills(project)}
    provider = _StubProvider(reply="ok")
    base = Registry()
    inner_entry = make_skill_tool(skills["inner"], provider=provider, model="m", base_registry=base)
    outer_entry = make_skill_tool(skills["outer"], provider=provider, model="m", base_registry=base)
    base.register(inner_entry)
    base.register(outer_entry)
    outer_entry.handler(input="x")
    # The sub-agent for `outer` should have seen `inner` among its tools.
    seen_tools = provider.calls[0]["tools"] or []
    seen_tool_names = {t["function"]["name"] for t in seen_tools}
    assert "inner" in seen_tool_names


def test_skill_cycle_returns_error(tmp_path: Path) -> None:
    from veles.core.context import push_skill_stack, reset_skill_stack

    project = init_project(tmp_path, name="t")
    _write_named_skill(project, name="self_caller", tools=[], body="b")
    skills = {s.name: s for s in discover_skills(project)}
    entry = make_skill_tool(
        skills["self_caller"],
        provider=_StubProvider(),
        model="m",
        base_registry=Registry(),
    )
    token = push_skill_stack("self_caller")
    try:
        out = entry.handler(input="x")
    finally:
        reset_skill_stack(token)
    assert "skill cycle detected" in out
    assert "self_caller" in out


def test_skill_depth_limit_exceeded(tmp_path: Path) -> None:
    from veles.core.context import push_skill_stack, reset_skill_stack

    project = init_project(tmp_path, name="t")
    _write_named_skill(project, name="leaf", tools=[], body="b")
    skills = {s.name: s for s in discover_skills(project)}
    entry = make_skill_tool(
        skills["leaf"],
        provider=_StubProvider(),
        model="m",
        base_registry=Registry(),
    )
    tokens = [push_skill_stack(n) for n in ("a", "b", "c", "d", "e")]
    try:
        out = entry.handler(input="x")
    finally:
        for tok in reversed(tokens):
            reset_skill_stack(tok)
    assert "skill depth limit" in out


def test_skill_stack_pops_on_success(tmp_path: Path) -> None:
    from veles.core.context import current_skill_stack

    project = init_project(tmp_path, name="t")
    _write_named_skill(project, name="solo", tools=[], body="b")
    skills = {s.name: s for s in discover_skills(project)}
    entry = make_skill_tool(
        skills["solo"],
        provider=_StubProvider(reply="done"),
        model="m",
        base_registry=Registry(),
    )
    assert current_skill_stack() == ()
    out = entry.handler(input="x")
    assert out == "done"
    assert current_skill_stack() == ()


# ---------- M8: custom parameters schemas ----------

import json as _json  # noqa: E402

from veles.core.skills import _build_param_schema, _yaml_type_to_json  # noqa: E402


def test_parse_frontmatter_with_parameters_list() -> None:
    text = (
        "---\n"
        "name: demo\n"
        "description: d\n"
        "parameters:\n"
        "  - name: scope\n"
        "    type: string\n"
        "    description: optional scope\n"
        "    required: false\n"
        "  - name: dry_run\n"
        "    type: bool\n"
        "    default: false\n"
        "---\n"
        "Body.\n"
    )
    fm, body = parse_frontmatter(text)
    assert fm["name"] == "demo"
    assert isinstance(fm["parameters"], list)
    assert len(fm["parameters"]) == 2
    p0 = fm["parameters"][0]
    assert p0 == {
        "name": "scope",
        "type": "string",
        "description": "optional scope",
        "required": False,
    }
    p1 = fm["parameters"][1]
    assert p1 == {"name": "dry_run", "type": "bool", "default": False}
    assert body == "Body.\n"


def test_parse_frontmatter_no_parameters_block_is_empty() -> None:
    text = "---\nname: x\ndescription: y\n---\nbody"
    fm, _ = parse_frontmatter(text)
    assert "parameters" not in fm


def test_render_frontmatter_round_trip_with_parameters() -> None:
    fm = {
        "name": "demo",
        "description": "d",
        "parameters": [
            {"name": "scope", "type": "string", "required": False},
            {"name": "dry_run", "type": "bool", "default": False},
        ],
    }
    rendered = render_frontmatter(fm, "body")
    fm2, body2 = parse_frontmatter(rendered)
    assert fm2 == fm
    assert body2.strip() == "body"


def test_yaml_type_to_json_mapping() -> None:
    assert _yaml_type_to_json("string") == "string"
    assert _yaml_type_to_json("str") == "string"
    assert _yaml_type_to_json("int") == "integer"
    assert _yaml_type_to_json("integer") == "integer"
    assert _yaml_type_to_json("bool") == "boolean"
    assert _yaml_type_to_json("boolean") == "boolean"
    assert _yaml_type_to_json("float") == "number"
    assert _yaml_type_to_json("UNKNOWN") == "string"


def test_build_param_schema_empty_falls_back_to_input() -> None:
    schema = _build_param_schema([])
    assert schema["type"] == "object"
    assert "input" in schema["properties"]
    assert schema["properties"]["input"]["type"] == "string"
    assert "required" not in schema  # input is optional


def test_build_param_schema_typed_args() -> None:
    schema = _build_param_schema(
        [
            {"name": "scope", "type": "string", "required": True},
            {"name": "dry_run", "type": "bool", "default": False},
            {"name": "count", "type": "int"},
        ]
    )
    props = schema["properties"]
    assert props["scope"] == {"type": "string"}
    assert props["dry_run"] == {"type": "boolean", "default": False}
    assert props["count"] == {"type": "integer"}
    assert set(schema["required"]) == {"scope", "count"}


def test_build_param_schema_default_makes_optional() -> None:
    schema = _build_param_schema([{"name": "x", "type": "string", "default": "hello"}])
    assert "required" not in schema
    assert schema["properties"]["x"]["default"] == "hello"


def test_make_skill_tool_uses_typed_schema(tmp_path: Path) -> None:
    project = init_project(tmp_path, name="t")
    skill_dir = project.skills_dir / "typed"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\n"
        "name: typed\n"
        "description: typed skill\n"
        "tools: []\n"
        "parameters:\n"
        "  - name: scope\n"
        "    type: string\n"
        "  - name: count\n"
        "    type: int\n"
        "    default: 1\n"
        "---\n"
        "Body.",
        encoding="utf-8",
    )
    skill = discover_skills(project)[0]
    assert skill.parameters
    entry = make_skill_tool(skill, provider=_StubProvider(), model="m", base_registry=Registry())
    schema = entry.parameter_schema
    assert "scope" in schema["properties"]
    assert "count" in schema["properties"]
    assert schema["required"] == ["scope"]


def test_skill_handler_substitutes_placeholders_in_body(tmp_path: Path) -> None:
    project = init_project(tmp_path, name="t")
    skill_dir = project.skills_dir / "echo_scope"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\n"
        "name: echo_scope\n"
        "description: e\n"
        "tools: []\n"
        "parameters:\n"
        "  - name: scope\n"
        "    type: string\n"
        "---\n"
        "Scope is {scope}.",
        encoding="utf-8",
    )
    skill = discover_skills(project)[0]
    provider = _StubProvider(reply="ok")
    entry = make_skill_tool(skill, provider=provider, model="m", base_registry=Registry())
    entry.handler(scope="auth")
    assert provider.last_system == "Scope is auth."


def test_skill_handler_leftover_args_become_json_user_message(tmp_path: Path) -> None:
    project = init_project(tmp_path, name="t")
    skill_dir = project.skills_dir / "json_args"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\n"
        "name: json_args\n"
        "description: e\n"
        "tools: []\n"
        "parameters:\n"
        "  - name: scope\n"
        "    type: string\n"
        "  - name: dry_run\n"
        "    type: bool\n"
        "---\n"
        "Body without placeholders.",
        encoding="utf-8",
    )
    skill = discover_skills(project)[0]
    provider = _StubProvider(reply="ok")
    entry = make_skill_tool(skill, provider=provider, model="m", base_registry=Registry())
    entry.handler(scope="auth", dry_run=True)
    user_messages = [m for call in provider.calls for m in call["messages"] if m.role == "user"]
    assert user_messages
    parsed = _json.loads(user_messages[0].content)
    assert parsed == {"scope": "auth", "dry_run": True}


def test_skill_handler_no_parameters_uses_input_legacy(tmp_path: Path) -> None:
    project = init_project(tmp_path, name="t")
    _write_named_skill(project, name="legacy", tools=[], body="Body.")
    skill = discover_skills(project)[0]
    provider = _StubProvider(reply="ok")
    entry = make_skill_tool(skill, provider=provider, model="m", base_registry=Registry())
    entry.handler(input="hello")
    user_messages = [m for call in provider.calls for m in call["messages"] if m.role == "user"]
    assert user_messages[0].content == "hello"

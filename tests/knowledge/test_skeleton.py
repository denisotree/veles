from veles.core.knowledge.skeleton import (
    build_skeleton,
    skeleton_ref_index,
)


def test_skeleton_includes_core_commands():
    entries = build_skeleton()
    cmds = {e.name for e in entries if e.kind == "cmd"}
    assert {"run", "init", "skill"} <= cmds


def test_skeleton_includes_a_known_flag():
    entries = build_skeleton()
    flags = {e.name for e in entries if e.kind == "flag"}
    # `veles run --manager` exists (VISION §5.3 / M122f).
    assert "run:--manager" in flags


def test_skeleton_includes_builtin_skills_and_tools():
    entries = build_skeleton()
    skills = {e.name for e in entries if e.kind == "skill"}
    tools = {e.name for e in entries if e.kind == "tool"}
    assert "tool_authoring" in skills
    assert "read_file" in tools


def test_ref_index_shape():
    idx = skeleton_ref_index(build_skeleton())
    assert "cmd:run" in idx
    assert "flag:run:--manager" in idx
    assert "skill:tool_authoring" in idx
    assert "tool:read_file" in idx


def test_skeleton_cmd_summary_is_populated():
    entries = build_skeleton()
    run_cmds = [e for e in entries if e.kind == "cmd" and e.name == "run"]
    assert run_cmds, "run command missing"
    assert all(e.summary for e in run_cmds), "run cmd summary should be non-empty"


def test_skeleton_has_no_duplicate_cmd_names():
    entries = build_skeleton()
    cmd_names = [e.name for e in entries if e.kind == "cmd"]
    assert len(cmd_names) == len(set(cmd_names)), "duplicate cmd entries"


def test_skeleton_excludes_help_flag():
    entries = build_skeleton()
    flags = {e.name for e in entries if e.kind == "flag"}
    assert "run:--help" not in flags

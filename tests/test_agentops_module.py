"""M204 Phase 3: agent-ops tools live in a MODULE, not in the core.

The user invariant: agent-callable command tools must not be baked into
`src/veles/core/` — they live in `src/veles/modules/` (like the wiki tools).
`job_add`/`job_list`/`job_remove` relocate to `modules/agentops/tools.py`;
`core/tools/builtin/job_tools.py` is deleted outright (no back-compat).
"""

from __future__ import annotations

from pathlib import Path

import veles


def test_job_tools_register_from_the_agentops_module() -> None:
    import veles.modules.agentops.tools  # noqa: F401 — @tool side effects
    from veles.core.tools.registry import registry

    names = set(registry.list_names())
    assert {"job_add", "job_list", "job_remove"} <= names


def test_core_job_tools_file_is_gone() -> None:
    core_dir = Path(veles.__file__).parent / "core"
    assert not (core_dir / "tools" / "builtin" / "job_tools.py").exists()


def test_no_command_tool_registers_from_core() -> None:
    """Import-graph teeth for the invariant: the agent-ops command tools'
    @tool definitions live under modules/, never under core/."""
    import ast

    core_dir = Path(veles.__file__).parent / "core"
    banned = {"job_add", "job_list", "job_remove", "wiki_add", "research"}
    offenders: list[str] = []
    for py in core_dir.rglob("*.py"):
        tree = ast.parse(py.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name in banned:
                # Only @tool-decorated definitions count.
                decos = {
                    getattr(d, "id", getattr(getattr(d, "func", None), "id", ""))
                    for d in node.decorator_list
                }
                if "tool" in decos:
                    offenders.append(f"{py}:{node.name}")
    assert offenders == []

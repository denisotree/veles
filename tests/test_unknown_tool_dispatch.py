"""Unknown-tool dispatch returns a recovery-oriented refusal, not a raw KeyError.

Regression for the failure where a model in writing/direct mode called
`create_plan` (a planning-only tool). The old path let `registry.dispatch`
raise `KeyError("unknown tool 'create_plan'")`, which surfaced to the model as
a cryptic `<error: KeyError: ...>` and led it to fabricate an explanation. The
guard in `_dispatch` now returns a helpful message instead, distinguishing a
tool that exists in another mode from one that doesn't exist at all.
"""

from __future__ import annotations

import veles.core.tools  # noqa: F401 -- registers builtins into the global registry
from veles.core.provider import ToolCall
from veles.core.tool_dispatch import _dispatch
from veles.core.tools.registry import Registry, ToolEntry


def _registry_with(name: str) -> Registry:
    reg = Registry()
    reg.register(
        ToolEntry(
            name=name,
            description="d",
            parameter_schema={"type": "object"},
            handler=lambda: "ok",
            is_async=False,
        )
    )
    return reg


def test_tool_gated_to_another_mode_yields_recovery_message() -> None:
    # `create_plan` is a real builtin but lives only in the planning toolset;
    # here the active registry exposes only `move_file`.
    reg = _registry_with("move_file")
    call = ToolCall(id="c1", name="create_plan", arguments={"objective": "x"})

    msg = _dispatch(reg, call, log=lambda *_a, **_k: None)
    content = msg.content or ""

    assert msg.role == "tool"
    assert msg.tool_call_id == "c1"
    assert "KeyError" not in content
    assert "create_plan" in content
    # It must point the model at what *is* available and away from a retry.
    assert "not enabled in the current mode" in content
    assert "move_file" in content


def test_nonexistent_tool_yields_no_such_tool_message() -> None:
    reg = _registry_with("move_file")
    call = ToolCall(id="c2", name="totally_made_up_tool", arguments={})

    msg = _dispatch(reg, call, log=lambda *_a, **_k: None)
    content = msg.content or ""

    assert "KeyError" not in content
    assert "no such tool" in content
    assert "move_file" in content


def test_unknown_tool_does_not_invoke_any_handler() -> None:
    # A handler that would explode if ever called — proves dispatch short-
    # circuits before touching the registry's invoke path.
    reg = Registry()
    reg.register(
        ToolEntry(
            name="real_tool",
            description="d",
            parameter_schema={"type": "object"},
            handler=lambda: (_ for _ in ()).throw(AssertionError("must not run")),
            is_async=False,
        )
    )
    call = ToolCall(id="c3", name="ghost_tool", arguments={})

    # Should return cleanly without raising the handler's AssertionError.
    msg = _dispatch(reg, call, log=lambda *_a, **_k: None)
    assert "ghost_tool" in (msg.content or "")

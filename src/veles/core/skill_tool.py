"""Turning a skill into a callable tool.

`make_skill_tool` wraps a `Skill` as a `ToolEntry`: its parameters become the
tool's JSON schema, and calling it runs the skill body as the system prompt of a
fresh sub-agent whose tools are the skill's whitelist.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from veles.core.skills import Skill, bump_telemetry
from veles.core.tools.registry import Registry, ToolEntry

if TYPE_CHECKING:
    from veles.core.provider import Provider

_MAX_SKILL_DEPTH = 5

_TYPE_MAP = {
    "string": "string",
    "str": "string",
    "int": "integer",
    "integer": "integer",
    "bool": "boolean",
    "boolean": "boolean",
    "float": "number",
    "number": "number",
}


def make_skill_tool(
    skill: Skill,
    *,
    provider: Provider,
    model: str,
    base_registry: Registry,
) -> ToolEntry:
    """Build a ToolEntry that, when invoked, runs the skill as a sub-agent.

    `base_registry` is the registry the skill's sub-agent will subset its tools
    from. Subset selection is deferred to invocation time so that cross-skill
    composition works: skills registered into the same `base_registry` later in
    the same load become available to skills whose `tools` whitelist names them.
    """
    return ToolEntry(
        name=skill.name,
        description=skill.description,
        parameter_schema=_build_param_schema(skill.parameters),
        handler=_make_skill_handler(
            skill=skill, provider=provider, model=model, base_registry=base_registry
        ),
        is_async=False,
    )


def _yaml_type_to_json(t: str) -> str:
    return _TYPE_MAP.get(t.lower(), "string")


def _build_param_schema(parameters: list[dict[str, Any]]) -> dict[str, Any]:
    """A JSON Schema (OpenAI tool params) from a skill's parameters list.

    No parameters → the `{input: string}` shape. Otherwise each parameter is a
    typed property, required when it says `required: true` or has no `default`.
    """
    if not parameters:
        return {
            "type": "object",
            "properties": {
                "input": {
                    "type": "string",
                    "description": (
                        "User input passed to the skill as the first user message."
                        " Optional — empty string means run the skill's default flow."
                    ),
                }
            },
        }
    properties: dict[str, Any] = {}
    required: list[str] = []
    for p in parameters:
        name = str(p.get("name") or "").strip()
        if not name:
            continue
        prop: dict[str, Any] = {"type": _yaml_type_to_json(str(p.get("type") or "string"))}
        if "description" in p:
            prop["description"] = str(p["description"])
        if "default" in p:
            prop["default"] = p["default"]
        properties[name] = prop
        is_required = p.get("required")
        if is_required is True or (is_required is not False and "default" not in p):
            required.append(name)
    schema: dict[str, Any] = {"type": "object", "properties": properties}
    if required:
        schema["required"] = required
    return schema


def _check_skill_recursion(skill_name: str, stack: tuple[str, ...]) -> str | None:
    """Return a `<error: ...>` string when the skill would recurse or exceed depth."""
    if skill_name in stack:
        return f"<error: skill cycle detected: {' -> '.join((*stack, skill_name))}>"
    if len(stack) >= _MAX_SKILL_DEPTH:
        chain = " -> ".join((*stack, skill_name))
        return f"<error: skill depth limit ({_MAX_SKILL_DEPTH}) exceeded: {chain}>"
    return None


def _resolve_skill_invocation(skill: Skill, kwargs: dict[str, Any]) -> tuple[str, str]:
    """Map the model's kwargs onto (system_prompt_body, user_message).

    - No `parameters` declared: the body stays as authored and the user message
      is the `input` kwarg verbatim.
    - Typed: every `{name}` placeholder in the body is substituted with its
      kwarg; the rest are JSON-serialised into the user message so the
      sub-agent still sees them.
    """
    if not skill.parameters:
        user_msg = str(kwargs["input"]) if kwargs.get("input") else "Run the workflow."
        return skill.body, user_msg

    body = skill.body
    leftover: dict[str, Any] = {}
    for name, value in kwargs.items():
        placeholder = "{" + name + "}"
        if placeholder in body:
            body = body.replace(placeholder, str(value))
        else:
            leftover[name] = value
    user_msg = json.dumps(leftover, ensure_ascii=False) if leftover else "Run the workflow."
    return body, user_msg


def _make_skill_handler(
    *,
    skill: Skill,
    provider: Provider,
    model: str,
    base_registry: Registry,
) -> Callable[..., str]:
    # Imported at call time: the agent module imports memory, which imports skills.
    from veles.core.agent import Agent
    from veles.core.context import (
        current_skill_stack,
        push_skill_stack,
        reset_skill_stack,
    )

    def handler(**kwargs: Any) -> str:
        recursion_error = _check_skill_recursion(skill.name, current_skill_stack())
        if recursion_error is not None:
            return recursion_error

        body, user_msg = _resolve_skill_invocation(skill, kwargs)

        # Subset at invocation: by now `base_registry` holds every skill
        # registered in the same load.
        sub_registry = base_registry.subset(skill.tools)
        token = push_skill_stack(skill.name)
        try:
            sub_agent = Agent(
                provider=provider,
                registry=sub_registry,
                model=model,
                max_iterations=skill.max_iterations,
                system_prompt=body,
            )
            try:
                result = sub_agent.run(user_msg)
            except Exception:
                bump_telemetry(skill, success=False)
                raise
            bump_telemetry(skill, success=result.stopped_reason == "completed")
            return result.text
        finally:
            reset_skill_stack(token)

    return handler


__all__ = ["make_skill_tool"]

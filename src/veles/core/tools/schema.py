"""Generate JSON Schema for a Python function's parameters via pydantic.create_model.

Why pydantic: it already handles Optional, list[T], default values, and gives us
JSON Schema as a side effect. M0 only supports primitive types and basic generics
— sufficient for the three builtin tools.
"""

from __future__ import annotations

import inspect
from collections.abc import Callable
from typing import Any

from pydantic import create_model


def python_function_to_schema(fn: Callable[..., Any]) -> dict[str, Any]:
    """Return JSON Schema describing fn's parameters (an `object` schema)."""
    sig = inspect.signature(fn)
    fields: dict[str, tuple[Any, Any]] = {}
    for name, param in sig.parameters.items():
        if name in ("self", "cls"):
            continue
        annotation = param.annotation if param.annotation is not inspect.Parameter.empty else Any
        default = param.default if param.default is not inspect.Parameter.empty else ...
        fields[name] = (annotation, default)
    if not fields:
        return {"type": "object", "properties": {}}
    model = create_model(fn.__name__, **fields)  # type: ignore[call-overload]
    schema = model.model_json_schema()
    schema.pop("title", None)
    for prop in schema.get("properties", {}).values():
        prop.pop("title", None)
    return schema

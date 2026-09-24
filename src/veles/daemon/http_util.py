"""Small request/response helpers shared by the daemon's HTTP route modules."""

from __future__ import annotations

import json
from typing import Any

from aiohttp import web


async def json_object(request: web.Request) -> dict[str, Any] | web.Response:
    """The request body as a JSON object, or the 400 response to return."""
    try:
        body = await request.json()
    except (json.JSONDecodeError, ValueError):
        return web.json_response({"error": "body must be JSON"}, status=400)
    if not isinstance(body, dict):
        return web.json_response({"error": "body must be a JSON object"}, status=400)
    return body


def runner_status(runner: Any) -> dict[str, Any] | None:
    """A background runner's `status()`, `{"enabled": True}` when it has none,
    None when the runner is not wired."""
    if runner is None:
        return None
    status_fn = getattr(runner, "status", None)
    return status_fn() if callable(status_fn) else {"enabled": True}

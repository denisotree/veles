"""DaemonClient — async HTTP/WS client against the M51 daemon.

Channels use this to submit runs and stream events. Every call carries
the `Authorization: Bearer <token>` header. WebSocket subscription
yields parsed JSON events until `completed` / `error` arrives.

The client is constructed with an optional `aiohttp.ClientSession` so
tests can inject a mocked session. Production usage:

    async with DaemonClient(url, token) as client:
        run = await client.submit_run("hello")
        async for event in client.stream_events(run["run_id"]):
            ...

Errors surface as `DaemonClientError` with the HTTP status + response
body when available — channels translate that into user-visible
messages.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from contextlib import suppress
from typing import Any

import aiohttp


class DaemonClientError(RuntimeError):
    def __init__(self, message: str, *, status: int | None = None, body: str | None = None):
        super().__init__(message)
        self.status = status
        self.body = body


class DaemonClient:
    def __init__(
        self,
        base_url: str,
        token: str,
        *,
        session: aiohttp.ClientSession | None = None,
    ) -> None:
        self._base = base_url.rstrip("/")
        self._token = token
        self._session = session
        self._owns_session = session is None

    async def __aenter__(self) -> DaemonClient:
        if self._session is None:
            self._session = aiohttp.ClientSession()
            self._owns_session = True
        return self

    async def __aexit__(self, *_exc) -> None:
        if self._owns_session and self._session is not None:
            await self._session.close()
            self._session = None

    @property
    def _auth(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._token}"}

    @property
    def session(self) -> aiohttp.ClientSession:
        if self._session is None:
            raise RuntimeError("DaemonClient used outside `async with`")
        return self._session

    async def health(self) -> dict[str, Any]:
        async with self.session.get(f"{self._base}/v1/health") as resp:
            return await _read_json(resp)

    async def submit_run(
        self, prompt: str, *, session_id: str | None = None, origin: str | None = None
    ) -> dict[str, Any]:
        body: dict[str, Any] = {"prompt": prompt}
        if session_id is not None:
            body["session_id"] = session_id
        if origin is not None:
            body["origin"] = origin
        async with self.session.post(
            f"{self._base}/v1/runs", json=body, headers=self._auth
        ) as resp:
            return await _read_json(resp)

    async def get_run(self, run_id: str) -> dict[str, Any]:
        async with self.session.get(f"{self._base}/v1/runs/{run_id}", headers=self._auth) as resp:
            return await _read_json(resp)

    async def submit_prompt_answer(
        self, run_id: str, prompt_id: str, choice: str
    ) -> dict[str, Any]:
        """Resolve an outstanding `trust_prompt` / `approval_prompt` by
        POSTing the user's choice. The daemon validates the key against
        the options it originally advertised; an unknown key returns
        409 (raises `DaemonClientError`)."""
        body = {"choice": choice}
        async with self.session.post(
            f"{self._base}/v1/runs/{run_id}/prompts/{prompt_id}",
            json=body,
            headers=self._auth,
        ) as resp:
            return await _read_json(resp)

    async def get_session(self, session_id: str) -> dict[str, Any]:
        """GET /v1/sessions/{id} — returns the session row + current
        overrides. Channels use this to highlight the active model in
        the /model picker."""
        async with self.session.get(
            f"{self._base}/v1/sessions/{session_id}",
            headers=self._auth,
        ) as resp:
            return await _read_json(resp)

    async def update_session(
        self,
        session_id: str,
        *,
        model: str | None = None,
        mode: str | None = None,
        provider: str | None = None,
    ) -> dict[str, Any]:
        """M126: PATCH /v1/sessions/{id} — set per-session overrides
        (model, mode, provider). At least one must be non-None; the
        daemon validates and returns the merged override map."""
        body: dict[str, Any] = {}
        if model is not None:
            body["model"] = model
        if mode is not None:
            body["mode"] = mode
        if provider is not None:
            body["provider"] = provider
        if not body:
            raise DaemonClientError("update_session requires at least one of model/mode/provider")
        async with self.session.patch(
            f"{self._base}/v1/sessions/{session_id}",
            json=body,
            headers=self._auth,
        ) as resp:
            return await _read_json(resp)

    async def stream_events(self, run_id: str) -> AsyncIterator[dict[str, Any]]:
        """Yield parsed JSON events from `WS /v1/runs/{run_id}/events`."""
        ws_url = self._base.replace("http://", "ws://", 1).replace("https://", "wss://", 1)
        async with self.session.ws_connect(
            f"{ws_url}/v1/runs/{run_id}/events", headers=self._auth
        ) as ws:
            async for msg in ws:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    with suppress(json.JSONDecodeError):
                        event = json.loads(msg.data)
                        if isinstance(event, dict):
                            yield event
                            if event.get("type") in ("completed", "error"):
                                break
                elif msg.type in (
                    aiohttp.WSMsgType.CLOSED,
                    aiohttp.WSMsgType.CLOSE,
                    aiohttp.WSMsgType.CLOSING,
                    aiohttp.WSMsgType.ERROR,
                ):
                    break


async def _read_json(resp: aiohttp.ClientResponse) -> dict[str, Any]:
    text = await resp.text()
    if resp.status >= 400:
        raise DaemonClientError(f"daemon returned {resp.status}", status=resp.status, body=text)
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise DaemonClientError(
            f"daemon returned non-JSON: {text[:200]}", status=resp.status, body=text
        ) from exc
    if not isinstance(data, dict):
        raise DaemonClientError(
            f"daemon returned non-object JSON: {text[:200]}",
            status=resp.status,
            body=text,
        )
    return data

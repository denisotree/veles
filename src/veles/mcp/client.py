"""Synchronous facade over the asyncio MCP SDK (M157).

The Veles agent loop is synchronous; the official ``mcp`` python SDK is
asyncio. `McpClientManager` bridges the two with one background event
loop running in a daemon thread per manager: every server connection
lives entirely inside that loop (one long-lived task per server, so all
anyio cancel scopes enter and exit in the same task), and sync callers
submit work via ``asyncio.run_coroutine_threadsafe`` with timeouts.

Transports: stdio, streamable HTTP (`transport = "http"`), and SSE
(`transport = "sse"`) — all three via the official SDK clients.

Failure policy: a server that fails to connect is recorded as
``failed`` with its error message and logged as a warning. Connect
failures NEVER raise out of `connect_all` — agent startup must not
break because a third-party MCP server is down.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import logging
import os
import threading
from contextlib import AsyncExitStack
from dataclasses import dataclass
from typing import Any

from veles.mcp.config import McpServerConfig

logger = logging.getLogger(__name__)

_CLOSE_GRACE_S = 5.0


class McpError(RuntimeError):
    """Base class for MCP client errors surfaced to sync callers."""


class McpServerUnavailable(McpError):
    """The named server is unknown, disabled, or not connected."""


class McpToolTimeout(McpError):
    """A tool call exceeded its configured timeout."""


@dataclass(slots=True)
class ServerStatus:
    """Sync-side snapshot of one server's connection state."""

    name: str
    transport: str
    state: str  # "connecting" | "connected" | "failed" | "closed"
    error: str | None
    tool_count: int


class _ServerConn:
    """Per-server state owned by the background loop (except `state`/`error`
    snapshots, which sync callers read — single-writer, so plain attributes
    are safe under CPython)."""

    def __init__(self, config: McpServerConfig) -> None:
        self.config = config
        self.state = "connecting"
        self.error: str | None = None
        self.tools: list[Any] = []
        self.session: Any = None
        self.ready = asyncio.Event()
        self.stop = asyncio.Event()
        self.task: asyncio.Task[None] | None = None


class McpClientManager:
    """Owns the background loop thread and all MCP server connections.

    Lifecycle: `connect_all(configs)` → `list_tools` / `call_tool` →
    `close()`. The manager is reusable across `connect_all` calls
    (already-connected servers are skipped)."""

    def __init__(self) -> None:
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._servers: dict[str, _ServerConn] = {}
        self._lock = threading.Lock()

    # ---- loop management ----

    def _ensure_loop(self) -> asyncio.AbstractEventLoop:
        with self._lock:
            if self._loop is not None and not self._loop.is_closed():
                return self._loop
            loop = asyncio.new_event_loop()

            def _run() -> None:
                asyncio.set_event_loop(loop)
                try:
                    loop.run_forever()
                finally:
                    loop.close()

            thread = threading.Thread(target=_run, name="veles-mcp-loop", daemon=True)
            thread.start()
            self._loop = loop
            self._thread = thread
            return loop

    # ---- connect ----

    def connect_all(self, configs: dict[str, McpServerConfig]) -> None:
        """Connect every enabled server in parallel; never raises.

        Each server gets its own `connect_timeout_s` budget; the worst
        case wall time is the max (not the sum) because all `_serve`
        tasks start before any result is awaited."""
        to_connect: list[tuple[str, _ServerConn]] = []
        for name, cfg in configs.items():
            if not cfg.enabled:
                logger.info("MCP server %r is disabled; skipping", name)
                continue
            existing = self._servers.get(name)
            if existing is not None and existing.state in {"connecting", "connected"}:
                continue
            to_connect.append((name, _ServerConn(cfg)))
        if not to_connect:
            return

        loop = self._ensure_loop()
        pending: list[tuple[str, _ServerConn, concurrent.futures.Future[None]]] = []
        for name, conn in to_connect:
            self._servers[name] = conn
            fut = asyncio.run_coroutine_threadsafe(self._start_server(conn), loop)
            pending.append((name, conn, fut))

        for name, conn, fut in pending:
            try:
                fut.result(timeout=conn.config.connect_timeout_s)
            except concurrent.futures.TimeoutError:
                conn.state = "failed"
                conn.error = f"connect timed out after {conn.config.connect_timeout_s:g}s"

                def _abort(c: _ServerConn = conn) -> None:
                    c.stop.set()
                    if c.task is not None:
                        c.task.cancel()

                loop.call_soon_threadsafe(_abort)
                logger.warning("MCP server %r: %s", name, conn.error)
            except Exception as exc:
                conn.state = "failed"
                if conn.error is None:
                    conn.error = str(exc)
                logger.warning("MCP server %r failed to connect: %s", name, conn.error)

    async def _start_server(self, conn: _ServerConn) -> None:
        """Spawn the long-lived per-server task and await its readiness."""
        conn.task = asyncio.get_running_loop().create_task(self._serve(conn))
        await conn.ready.wait()
        if conn.state != "connected":
            raise McpServerUnavailable(conn.error or "connect failed")

    async def _serve(self, conn: _ServerConn) -> None:
        """One task per server: open transport, init session, idle until stop.

        All async context managers (transport, session) are entered and
        exited inside this single task — anyio cancel scopes require it."""
        cfg = conn.config
        try:
            async with AsyncExitStack() as stack:
                read, write = await self._open_transport(stack, cfg)
                from mcp import ClientSession

                session = await stack.enter_async_context(ClientSession(read, write))
                await session.initialize()
                listed = await session.list_tools()
                conn.tools = list(listed.tools)
                conn.session = session
                conn.state = "connected"
                conn.ready.set()
                await conn.stop.wait()
        except asyncio.CancelledError:
            # A connect-timeout abort arrives as cancellation; keep the
            # sync side's "failed" verdict if it already recorded one.
            if conn.state == "connected":
                conn.state = "closed"
            raise
        except BaseException as exc:
            if conn.state == "connected":
                conn.state = "closed"
            else:
                conn.state = "failed"
                conn.error = f"{type(exc).__name__}: {exc}".strip(": ")
        else:
            conn.state = "closed"
        finally:
            conn.session = None
            conn.ready.set()

    @staticmethod
    async def _open_transport(stack: AsyncExitStack, cfg: McpServerConfig) -> tuple[Any, Any]:
        """Enter the SDK transport context for `cfg`; returns (read, write)."""
        if cfg.transport == "stdio":
            from mcp import StdioServerParameters
            from mcp.client.stdio import stdio_client

            params = StdioServerParameters(
                command=cfg.command or "",
                args=list(cfg.args),
                env={**os.environ, **cfg.env} if cfg.env else None,
            )
            read, write = await stack.enter_async_context(stdio_client(params))
            return read, write
        if cfg.transport == "http":
            from mcp.client.streamable_http import streamablehttp_client

            read, write, _get_session_id = await stack.enter_async_context(
                streamablehttp_client(cfg.url or "", timeout=cfg.connect_timeout_s)
            )
            return read, write
        if cfg.transport == "sse":
            from mcp.client.sse import sse_client

            read, write = await stack.enter_async_context(
                sse_client(cfg.url or "", timeout=cfg.connect_timeout_s)
            )
            return read, write
        raise ValueError(f"unknown MCP transport {cfg.transport!r}")

    # ---- sync API ----

    def status(self) -> dict[str, ServerStatus]:
        """Snapshot of every known server's state."""
        return {
            name: ServerStatus(
                name=name,
                transport=conn.config.transport,
                state=conn.state,
                error=conn.error,
                tool_count=len(conn.tools),
            )
            for name, conn in self._servers.items()
        }

    def list_tools(self, server: str) -> list[Any]:
        """Raw SDK Tool objects discovered at connect time for `server`."""
        conn = self._servers.get(server)
        if conn is None:
            raise McpServerUnavailable(f"MCP server {server!r} is not configured/connected")
        return list(conn.tools)

    def call_tool(
        self,
        server: str,
        tool: str,
        arguments: dict[str, Any] | None = None,
        *,
        timeout_s: float | None = None,
    ) -> Any:
        """Invoke `tool` on `server`; returns the SDK CallToolResult.

        Blocks the calling (sync) thread up to `timeout_s` (default: the
        server's configured `timeout_s`)."""
        conn = self._servers.get(server)
        if conn is None or conn.state != "connected" or conn.session is None:
            detail = conn.error if conn is not None else None
            raise McpServerUnavailable(
                f"MCP server {server!r} is not connected" + (f" ({detail})" if detail else "")
            )
        loop = self._loop
        if loop is None or loop.is_closed():
            raise McpServerUnavailable("MCP client manager is closed")
        budget = timeout_s if timeout_s is not None else conn.config.timeout_s
        fut = asyncio.run_coroutine_threadsafe(conn.session.call_tool(tool, arguments or {}), loop)
        try:
            return fut.result(timeout=budget)
        except concurrent.futures.TimeoutError:
            fut.cancel()
            raise McpToolTimeout(f"MCP tool {server}/{tool} timed out after {budget:g}s") from None

    def close(self) -> None:
        """Tear down all connections and stop the background loop. Idempotent."""
        with self._lock:
            loop = self._loop
            thread = self._thread
            self._loop = None
            self._thread = None
        if loop is None or loop.is_closed():
            self._servers.clear()
            return

        tasks = [c.task for c in self._servers.values() if c.task is not None]

        async def _shutdown() -> None:
            for conn in self._servers.values():
                conn.stop.set()
            if tasks:
                await asyncio.wait(tasks, timeout=_CLOSE_GRACE_S)

        try:
            asyncio.run_coroutine_threadsafe(_shutdown(), loop).result(timeout=_CLOSE_GRACE_S * 2)
        except Exception as exc:
            logger.warning("MCP shutdown did not complete cleanly: %s", exc)
        loop.call_soon_threadsafe(loop.stop)
        if thread is not None:
            thread.join(timeout=_CLOSE_GRACE_S)
        self._servers.clear()


__all__ = [
    "McpClientManager",
    "McpError",
    "McpServerUnavailable",
    "McpToolTimeout",
    "ServerStatus",
]

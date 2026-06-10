"""Veles daemon (M51) — long-lived agent loop exposed over HTTP + WebSocket.

The CLI dispatches a one-shot agent run per invocation. Third-party
clients (TUI clients, IDE plugins, M52 channel modules) need to drive
the same `Agent.run` without re-execing the CLI. The daemon binds to
`127.0.0.1` by default, serves a small JSON API over aiohttp, and fans
streaming events over WebSocket.

Auth: bearer tokens persisted to `~/.veles/daemon.tokens.json` (mode
0600). The daemon refuses to serve any endpoint except `/v1/health`
without a valid `Authorization: Bearer <token>` header.

Project scope: single project per daemon process, captured at startup.
Multi-project routing inside a single daemon process is deferred — run
multiple daemons on different ports if you need that.
"""

"""Channel modules (M52) — generic gateway protocol on top of the daemon.

Channels are long-running foreground processes that bridge external
chat surfaces (Telegram, Slack, Discord, web) to a running
`veles daemon` (M51) over HTTP+WebSocket. Each user message becomes a
`POST /v1/runs` against the daemon; streaming events from
`WS /v1/runs/{id}/events` are batched and pushed back to the user.

A channel owns:

- a `DaemonClient` — HTTP/WS client against M51 endpoints, bearer-auth.
- a `SessionMap` — persistent `chat_id → veles session_id` mapping so a
  user's conversation stays continuous across daemon restarts.
- a channel-specific transport (Telegram Bot API in M52; other
  channels follow the same `ChannelGateway` protocol).

Each channel runs as `veles channel run --channel <name>`. Multiple
channels = multiple processes, each pointing at the same daemon.

Module API integration (M24 hook-style modules getting a long-running
`start()` entrypoint) is deferred — channels need their own
foreground loop and signal handling, which doesn't map cleanly onto
the agent-loop hook surface.
"""

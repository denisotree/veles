# How to run Veles as a daemon

> 🌐 **Languages:** **English** · [简体中文](../../zh-CN/how-to/run-as-daemon.md) · [繁體中文](../../zh-TW/how-to/run-as-daemon.md) · [日本語](../../ja/how-to/run-as-daemon.md) · [한국어](../../ko/how-to/run-as-daemon.md) · [Español](../../es/how-to/run-as-daemon.md) · [Français](../../fr/how-to/run-as-daemon.md) · [Italiano](../../it/how-to/run-as-daemon.md) · [Português (BR)](../../pt-BR/how-to/run-as-daemon.md) · [Português (PT)](../../pt-PT/how-to/run-as-daemon.md) · [Русский](../../ru/how-to/run-as-daemon.md) · [العربية](../../ar/how-to/run-as-daemon.md) · [हिन्दी](../../hi/how-to/run-as-daemon.md) · [বাংলা](../../bn/how-to/run-as-daemon.md) · [Tiếng Việt](../../vi/how-to/run-as-daemon.md)

The daemon is an optional long-lived HTTP+WS server that exposes the agent as an
API — the foundation for [channels](connect-telegram.md) (Telegram, …), scheduled
[jobs](long-running-tasks.md), and remote/headless use.

## Start and stop

```bash
veles daemon start              # detaches by default; binds 127.0.0.1:8765 (or the next free port)
veles daemon status             # is this project's daemon running?
veles daemon stop               # SIGTERM via the pid file
```

Each project runs its own daemon: starting one in a second project picks the
next free port automatically instead of refusing with "already running" —
pin a port per project with `[daemon] port` in the config if you need a
stable address. If a pinned port turns out to be held by *another project's*
daemon (the wizard writes the same default into every project), the start
rolls to the next free port with a warning; a port held by anything else
fails loudly. `stop`/`status` address the daemon of the project you are in;
`veles daemon list` shows all of them.

`start` detaches and returns your shell. For a foreground process (systemd
`Type=simple`, Docker, debugging) pass `--foreground`. Override the bind:

```bash
veles daemon start --host 0.0.0.0 --port 9000
```

The daemon's model and provider come from the project config and are **fixed for
its lifetime** — set them before starting:

```toml
# <project>/.veles/config.toml
[engine]
provider = "ollama"           # provider name
model = "qwen3:4b-instruct"   # model id
```

## Authentication tokens

API clients authenticate with a bearer token:

```bash
veles daemon token add tui-client     # mint a token
veles daemon token list               # list (masked)
veles daemon token remove tui-client
```

## Running a prompt over HTTP

Submit a prompt and get a run id back:

```bash
curl -s localhost:8765/v1/runs \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"prompt": "summarise today", "deliver_to": "telegram:-100123"}'
```

The response is `202` with a run id — the run is still going. Three ways to get
the answer:

| | |
|---|---|
| `GET /v1/runs/{id}` | poll until `state` is `completed`, then read `final_text` |
| `WS /v1/runs/{id}/events` | stream `text_delta` events live; the final `completed` event carries the full text |
| `deliver_to` | the daemon pushes the finished answer to a chat itself |

`GET /v1/runs` (the list) reports state only — the answer text is on the
single-run endpoint, so listing a long-lived daemon's runs stays cheap.

Optional fields on `POST /v1/runs`:

- **`session_id`** — continue an existing session instead of starting a new one.
- **`origin`** — the chat this request came from. Reminders and jobs the agent
  creates during the run default to delivering there.
- **`deliver_to`** — where to send the finished answer: `telegram:<chat_id>`,
  `<platform>:<chat_id>:<thread_id>`, `local`, or `origin` to reuse the field
  above. A malformed target is rejected immediately with `400`; asking for
  delivery on a daemon with no channel running gives `503`.

Delivery is best-effort and never changes the run's outcome — a chat that can't
be reached says nothing about whether the agent did its work. If a send fails,
the run still reports `completed` and `delivery_error` on the single-run
endpoint explains why. Note the two are set a moment apart, so a client that
stops polling the instant it sees `completed` may read `delivery_error` before
the send has finished; treat it as telemetry, not as a receipt.

**Any valid token can do all of this**, including delivering to any chat the bot
can reach — tokens carry no scopes. Treat a daemon token as full access to the
project, and keep the daemon on `127.0.0.1` unless you have a reason not to.

## The daemon picker (TUI)

Run `veles daemon` with no subcommand to open the control panel — a tree of your
project's daemons and each daemon's channels:

```
Project: my-project
  default   running  pid=…  up 1.2h  qwen3:4b-instruct
    chan: telegram
  api       stopped
Other projects
  other-proj  running
```

Keys: `Enter` opens a daemon's log; `s`/`t`/`r` start/stop/restart; `d` delete;
`c`/`x` add/remove a channel; `q` quit.

## Multiple daemons per project (named sessions)

A project can run several daemons with different models/ports at once. Declare a
named session, then start it:

```bash
veles daemon session create api --port 8801 --provider anthropic --model claude-opus-4.8
veles daemon start --name api
veles daemon session list
```

Each named session has its own `[daemon.<name>]` config block and its own
channels (`[daemon.<name>.channels.*]`).

## List daemons across projects

```bash
veles daemon list
veles daemon restart <project-or-slug>
veles daemon delete  <project-or-slug>
```

## Next

- [Connect a Telegram channel](connect-telegram.md)
- [Schedule jobs](long-running-tasks.md)

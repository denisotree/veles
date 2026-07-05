# How to run Veles as a daemon

> 🌐 **Languages:** **English** · [简体中文](../../zh-CN/how-to/run-as-daemon.md) · [繁體中文](../../zh-TW/how-to/run-as-daemon.md) · [日本語](../../ja/how-to/run-as-daemon.md) · [한국어](../../ko/how-to/run-as-daemon.md) · [Español](../../es/how-to/run-as-daemon.md) · [Français](../../fr/how-to/run-as-daemon.md) · [Italiano](../../it/how-to/run-as-daemon.md) · [Português (BR)](../../pt-BR/how-to/run-as-daemon.md) · [Português (PT)](../../pt-PT/how-to/run-as-daemon.md) · [Русский](../../ru/how-to/run-as-daemon.md) · [العربية](../../ar/how-to/run-as-daemon.md) · [हिन्दी](../../hi/how-to/run-as-daemon.md) · [বাংলা](../../bn/how-to/run-as-daemon.md) · [Tiếng Việt](../../vi/how-to/run-as-daemon.md)

The daemon is an optional long-lived HTTP+WS server that exposes the agent as an
API — the foundation for [channels](connect-telegram.md) (Telegram, …), scheduled
[jobs](long-running-tasks.md), and remote/headless use.

## Start and stop

```bash
veles daemon start              # detaches by default; binds 127.0.0.1:8765
veles daemon status             # is it running?
veles daemon stop               # SIGTERM via the pid file
```

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

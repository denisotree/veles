# Como rodar o Veles como daemon

> 🌐 **Idiomas:** [English](../../en/how-to/run-as-daemon.md) · [简体中文](../../zh-CN/how-to/run-as-daemon.md) · [繁體中文](../../zh-TW/how-to/run-as-daemon.md) · [日本語](../../ja/how-to/run-as-daemon.md) · [한국어](../../ko/how-to/run-as-daemon.md) · [Español](../../es/how-to/run-as-daemon.md) · [Français](../../fr/how-to/run-as-daemon.md) · [Italiano](../../it/how-to/run-as-daemon.md) · **Português (BR)** · [Português (PT)](../../pt-PT/how-to/run-as-daemon.md) · [Русский](../../ru/how-to/run-as-daemon.md) · [العربية](../../ar/how-to/run-as-daemon.md) · [हिन्दी](../../hi/how-to/run-as-daemon.md) · [বাংলা](../../bn/how-to/run-as-daemon.md) · [Tiếng Việt](../../vi/how-to/run-as-daemon.md)

O daemon é um servidor HTTP+WS opcional e de longa duração que expõe o agente como
uma API — a base para [canais](connect-telegram.md) (Telegram, …),
[jobs](long-running-tasks.md) agendados e uso remoto/headless.

## Iniciar e parar

```bash
veles daemon start              # detaches by default; binds 127.0.0.1:8765
veles daemon status             # is it running?
veles daemon stop               # SIGTERM via the pid file
```

`start` desanexa e devolve o seu shell. Para um processo em primeiro plano
(`Type=simple` do systemd, Docker, depuração), passe `--foreground`. Sobrescreva o
bind:

```bash
veles daemon start --host 0.0.0.0 --port 9000
```

O modelo e o provedor do daemon vêm da config do projeto e ficam **fixos durante
todo o seu ciclo de vida** — defina-os antes de iniciar:

```toml
# <project>/.veles/config.toml
[provider]
default = "ollama"            # provider name
model = "qwen3:4b-instruct"   # model id
```

## Tokens de autenticação

Os clientes da API se autenticam com um token bearer:

```bash
veles daemon token add tui-client     # mint a token
veles daemon token list               # list (masked)
veles daemon token remove tui-client
```

## O seletor de daemons (TUI)

Rode `veles daemon` sem subcomando para abrir o painel de controle — uma árvore dos
daemons do seu projeto e dos canais de cada daemon:

```
Project: my-project
  default   running  pid=…  up 1.2h  qwen3:4b-instruct
    chan: telegram
  api       stopped
Other projects
  other-proj  running
```

Teclas: `Enter` abre o log de um daemon; `s`/`t`/`r` inicia/para/reinicia; `d`
exclui; `c`/`x` adiciona/remove um canal; `q` sai.

## Vários daemons por projeto (sessões nomeadas)

Um projeto pode rodar vários daemons com modelos/portas diferentes ao mesmo tempo.
Declare uma sessão nomeada e depois inicie-a:

```bash
veles daemon session create api --port 8801 --provider anthropic --model claude-opus-4.8
veles daemon start --name api
veles daemon session list
```

Cada sessão nomeada tem seu próprio bloco de config `[daemon.<name>]` e seus
próprios canais (`[daemon.<name>.channels.*]`).

## Liste daemons entre projetos

```bash
veles daemon list
veles daemon restart <project-or-slug>
veles daemon delete  <project-or-slug>
```

## Próximo

- [Conectar um canal do Telegram](connect-telegram.md)
- [Agendar jobs](long-running-tasks.md)

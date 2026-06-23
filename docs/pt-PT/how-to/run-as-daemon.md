# Como executar o Veles como daemon

> 🌐 **Languages:** **English** · [Русский](../../ru/how-to/run-as-daemon.md)

O daemon é um servidor HTTP+WS opcional e de longa duração que expõe o agente como uma
API — o alicerce para os [canais](connect-telegram.md) (Telegram, …), as [tarefas](long-running-tasks.md)
agendadas, e o uso remoto/sem cabeça (headless).

## Arrancar e parar

```bash
veles daemon start              # detaches by default; binds 127.0.0.1:8765
veles daemon status             # is it running?
veles daemon stop               # SIGTERM via the pid file
```

`start` destaca-se e devolve-lhe a shell. Para um processo em primeiro plano (systemd
`Type=simple`, Docker, depuração) passe `--foreground`. Sobreponha o vínculo (bind):

```bash
veles daemon start --host 0.0.0.0 --port 9000
```

O modelo e o fornecedor do daemon vêm da configuração do projecto e são **fixos durante o
seu tempo de vida** — defina-os antes de arrancar:

```toml
# <project>/.veles/config.toml
[provider]
default = "ollama"            # provider name
model = "qwen3:4b-instruct"   # model id
```

## Tokens de autenticação

Os clientes de API autenticam-se com um bearer token:

```bash
veles daemon token add tui-client     # mint a token
veles daemon token list               # list (masked)
veles daemon token remove tui-client
```

## O selector de daemons (TUI)

Execute `veles daemon` sem subcomando para abrir o painel de controlo — uma árvore dos
daemons do seu projecto e dos canais de cada daemon:

```
Project: my-project
  default   running  pid=…  up 1.2h  qwen3:4b-instruct
    chan: telegram
  api       stopped
Other projects
  other-proj  running
```

Teclas: `Enter` abre o log de um daemon; `s`/`t`/`r` arrancar/parar/reiniciar; `d` apagar;
`c`/`x` adicionar/remover um canal; `q` sair.

## Vários daemons por projecto (sessões nomeadas)

Um projecto pode executar vários daemons com modelos/portas diferentes em simultâneo.
Declare uma sessão nomeada e depois arranque-a:

```bash
veles daemon session create api --port 8801 --provider anthropic --model claude-opus-4.8
veles daemon start --name api
veles daemon session list
```

Cada sessão nomeada tem o seu próprio bloco de configuração `[daemon.<name>]` e os seus
próprios canais (`[daemon.<name>.channels.*]`).

## Listar daemons em todos os projectos

```bash
veles daemon list
veles daemon restart <project-or-slug>
veles daemon delete  <project-or-slug>
```

## A seguir

- [Ligar um canal do Telegram](connect-telegram.md)
- [Agendar tarefas](long-running-tasks.md)

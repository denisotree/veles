# Como executar o Veles como daemon

> 🌐 **Languages:** **English** · [Русский](../../ru/how-to/run-as-daemon.md)

O daemon é um servidor HTTP+WS opcional e de longa duração que expõe o agente
como uma API — a base para os [canais](connect-telegram.md) (Telegram, …), os
[trabalhos](long-running-tasks.md) agendados e a utilização remota/headless.

## Iniciar e parar

```bash
veles daemon start              # desanexa por omissão; liga-se a 127.0.0.1:8765
veles daemon status             # está a correr?
veles daemon stop               # SIGTERM através do ficheiro pid
```

O `start` desanexa e devolve-lhe a shell. Para um processo em primeiro plano
(systemd `Type=simple`, Docker, depuração) passe `--foreground`. Substitua o
endereço de ligação:

```bash
veles daemon start --host 0.0.0.0 --port 9000
```

O modelo e o fornecedor do daemon provêm da configuração do projeto e são
**fixos durante todo o seu tempo de vida** — defina-os antes de iniciar:

```toml
# <project>/.veles/config.toml
[provider]
default = "ollama:qwen3:4b-instruct"
```

## Tokens de autenticação

Os clientes da API autenticam-se com um token de portador (bearer):

```bash
veles daemon token add tui-client     # gerar um token
veles daemon token list               # listar (mascarados)
veles daemon token remove tui-client
```

## O seletor de daemons (TUI)

Execute `veles daemon` sem subcomando para abrir o painel de controlo — uma
árvore dos daemons do seu projeto e dos canais de cada daemon:

```
Project: my-project
  default   running  pid=…  up 1.2h  qwen3:4b-instruct
    chan: telegram
  api       stopped
Other projects
  other-proj  running
```

Teclas: `Enter` abre o registo de um daemon; `s`/`t`/`r` iniciar/parar/reiniciar;
`d` eliminar; `c`/`x` adicionar/remover um canal; `q` sair.

## Vários daemons por projeto (sessões nomeadas)

Um projeto pode executar vários daemons com modelos/portas diferentes em
simultâneo. Declare uma sessão nomeada e depois inicie-a:

```bash
veles daemon session create api --port 8801 --provider anthropic --model claude-opus-4.8
veles daemon start --name api
veles daemon session list
```

Cada sessão nomeada tem o seu próprio bloco de configuração `[daemon.<name>]` e
os seus próprios canais (`[daemon.<name>.channels.*]`).

## Listar daemons de vários projetos

```bash
veles daemon list
veles daemon restart <project-or-slug>
veles daemon delete  <project-or-slug>
```

## A seguir

- [Ligar um canal de Telegram](connect-telegram.md)
- [Agendar trabalhos](long-running-tasks.md)

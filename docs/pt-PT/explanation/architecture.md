# Visão geral da arquitetura

> 🌐 **Idiomas:** [English](../../en/explanation/architecture.md) · [简体中文](../../zh-CN/explanation/architecture.md) · [繁體中文](../../zh-TW/explanation/architecture.md) · [日本語](../../ja/explanation/architecture.md) · [한국어](../../ko/explanation/architecture.md) · [Español](../../es/explanation/architecture.md) · [Français](../../fr/explanation/architecture.md) · [Italiano](../../it/explanation/architecture.md) · [Português (BR)](../../pt-BR/explanation/architecture.md) · **Português (PT)** · [Русский](../../ru/explanation/architecture.md) · [العربية](../../ar/explanation/architecture.md) · [हिन्दी](../../hi/explanation/architecture.md) · [বাংলা](../../bn/explanation/architecture.md) · [Tiếng Việt](../../vi/explanation/architecture.md)

Esta página explica o que o Veles *é* e como as suas partes se encaixam, para que o
resto da documentação faça sentido. Para a visão de produto autoritativa, consulte o
`VISION.md` na raiz do repositório.

## A intenção de design

O Veles é deliberadamente **minimalista e bem decomposto** — módulos de
responsabilidade única, sem ficheiros-monstro. É **local-first**: executa-o sobre um
diretório na sua máquina e ele mantém aí a sua própria memória estruturada.

## Os cinco pilares (o núcleo)

Tudo no núcleo serve uma de cinco funções:

1. **Memória do projeto** — um artefacto estruturado (separado do seu conteúdo) que
   guarda o registo de sessões, regras/insights aprendidos, um mapa de ficheiros do
   projeto e os registos de skills/ferramentas com telemetria. Consulte
   [memória do projeto e o ciclo de aprendizagem](project-memory-and-learning-loop.md).
2. **O ciclo de aprendizagem** — o curador, o extrator de insights e o "dreaming" que
   mantêm a memória atualizada e transformam a experiência em regras reutilizáveis.
3. **Orquestração multi-agente** — um gestor que decompõe uma tarefa e gera workers
   especializados. Consulte [orquestração multi-agente](multi-agent-orchestration.md).
4. **Um protocolo de provedores** — uma única interface sobre vários backends de LLM
   (cloud, local, delegação a CLI). Consulte [provedores](../reference/providers.md).
5. **Ferramentas e skills mínimas** — um pequeno conjunto inicial que **se acumula** à
   medida que o Veles escreve as suas próprias ferramentas e formaliza processos
   repetidos em skills. Consulte [skills e ferramentas](skills-and-tools.md).

## Tudo o resto é um módulo opcional

Gateways/canais, o daemon, o agendador, a TUI, visão/STT — tudo isto é **acoplável** e
carrega apenas quando é usado. O Veles arranca com o mínimo e expande-se a pedido, pelo
que um simples `veles run` permanece simples.

## Como flui um turno

```
o seu prompt
   │
   ▼
contexto: AGENTS.md (pequeno) + recall a pedido a partir da memória do projeto
   │
   ▼
ciclo do agente  ──►  provedor (encaminhado por tarefa)  ──►  chamadas de ferramentas
   │                                               │
   │            (a escada de confiança controla ferramentas sensíveis)
   ▼
resposta  ──►  gravada na memória  ──►  gatilhos de aprendizagem (insights, curador)
```

O ficheiro de contexto (`AGENTS.md`) é mantido pequeno de propósito; o conhecimento
auxiliar (páginas da wiki, o mapa de ficheiros do projeto, turnos passados relevantes) é
trazido **a pedido** em vez de ser despejado logo no início.

## Onde vive o estado

- `<project>/.veles/` — a memória, a configuração e as skills/ferramentas locais deste
  projeto.
- `~/.veles/` — configuração global do utilizador, skills/ferramentas entre projetos,
  caches, confiança.
- `<project>/AGENTS.md`, `wiki/`, `sources/` — o seu conteúdo (o layout LLM-Wiki).

Consulte [layout do projeto](../reference/project-layout.md).

## Multi-projeto num único ciclo

Um único ciclo de agente serve muitos projetos. Cada projeto tem o seu próprio diretório
com o seu próprio contexto e memória; o `AGENTS.md` é ligado por symlink a
`CLAUDE.md`/`GEMINI.md` para que uma CLI externa lançada aí veja o mesmo contexto.
Consulte [múltiplos projetos](../how-to/multi-project-and-subprojects.md).

## As superfícies

- **CLI** (`veles run`, `veles add`, …) — utilização pontual e em scripts.
- **TUI** (`veles tui`) — REPL interativa com [modos de execução](modes.md).
- **Daemon + canais** — API headless, Telegram, tarefas agendadas.

As três acionam o mesmo ciclo de agente central.

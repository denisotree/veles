# Visão geral da arquitetura

> 🌐 **Idiomas:** **English** · [Русский](../../ru/explanation/architecture.md)

Esta página explica o que o Veles *é* e como suas partes se encaixam, para que o
resto da documentação faça sentido. Para a visão de produto oficial, veja o
`VISION.md` na raiz do repositório.

## A intenção de design

O Veles é deliberadamente **minimalista e bem decomposto** — módulos de
responsabilidade única, sem arquivos-monstro. Ele é **local-first**: você o executa
contra um diretório na sua máquina, e ele mantém ali a sua própria memória
estruturada.

## Os cinco pilares (o núcleo)

Tudo no núcleo serve a um destes cinco propósitos:

1. **Memória do projeto** — um artefato estruturado (separado do seu conteúdo) que
   guarda o log de sessões, regras/insights aprendidos, um mapa dos arquivos do
   projeto e os registros de skills/ferramentas com telemetria. Veja
   [memória do projeto e o loop de aprendizado](project-memory-and-learning-loop.md).
2. **O loop de aprendizado** — o curador, o extrator de insights e o "sonhar" que
   mantêm a memória atualizada e transformam experiência em regras reutilizáveis.
3. **Orquestração multiagente** — um gerente que decompõe uma tarefa e gera
   workers especializados. Veja [orquestração multiagente](multi-agent-orchestration.md).
4. **Um protocolo de provedor** — uma única interface sobre vários backends de LLM
   (nuvem, local, delegação para CLI). Veja [provedores](../reference/providers.md).
5. **Ferramentas e skills mínimas** — um pequeno conjunto inicial que **se acumula**
   conforme o Veles escreve suas próprias ferramentas e formaliza processos
   repetitivos em skills. Veja [skills e ferramentas](skills-and-tools.md).

## Todo o resto é um módulo opcional

Gateways/canais, o daemon, o agendador, a TUI, visão/STT — todos são
**plugáveis** e carregam apenas quando usados. O Veles inicia com o mínimo e se
expande sob demanda, então um simples `veles run` permanece simples.

## Como um turno flui

```
your prompt
   │
   ▼
context: AGENTS.md (small) + on-demand recall from project memory
   │
   ▼
agent loop  ──►  provider (routed per task)  ──►  tool calls
   │                                               │
   │            (trust ladder gates sensitive tools)
   ▼
response  ──►  saved to memory  ──►  learning triggers (insights, curator)
```

O arquivo de contexto (`AGENTS.md`) é mantido pequeno de propósito; conhecimento
auxiliar (páginas do wiki, o mapa de arquivos do projeto, turnos passados
relevantes) é trazido **sob demanda**, em vez de ser despejado tudo de uma vez no
início.

## Onde o estado vive

- `<project>/.veles/` — a memória, a configuração e as skills/ferramentas locais
  deste projeto.
- `~/.veles/` — configuração global do usuário, skills/ferramentas entre projetos,
  caches e trust.
- `<project>/AGENTS.md`, `wiki/`, `sources/` — o seu conteúdo (o layout LLM-Wiki).

Veja [layout do projeto](../reference/project-layout.md).

## Múltiplos projetos em um só loop

Um único loop de agente atende a muitos projetos. Cada projeto recebe seu próprio
diretório com seu próprio contexto e memória; o `AGENTS.md` é vinculado por symlink
a `CLAUDE.md`/`GEMINI.md`, de modo que uma CLI externa iniciada ali enxergue o mesmo
contexto. Veja [múltiplos projetos](../how-to/multi-project-and-subprojects.md).

## As superfícies

- **CLI** (`veles run`, `veles add`, …) — uso pontual e em scripts.
- **TUI** (`veles tui`) — REPL interativo com [modos de execução](modes.md).
- **Daemon + canais** — API headless, Telegram, jobs agendados.

As três acionam o mesmo loop central do agente.

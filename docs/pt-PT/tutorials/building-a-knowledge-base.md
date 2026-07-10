# Construir uma base de conhecimento

> 🌐 **Idiomas:** [English](../../en/tutorials/building-a-knowledge-base.md) · [简体中文](../../zh-CN/tutorials/building-a-knowledge-base.md) · [繁體中文](../../zh-TW/tutorials/building-a-knowledge-base.md) · [日本語](../../ja/tutorials/building-a-knowledge-base.md) · [한국어](../../ko/tutorials/building-a-knowledge-base.md) · [Español](../../es/tutorials/building-a-knowledge-base.md) · [Français](../../fr/tutorials/building-a-knowledge-base.md) · [Italiano](../../it/tutorials/building-a-knowledge-base.md) · [Português (BR)](../../pt-BR/tutorials/building-a-knowledge-base.md) · **Português (PT)** · [Русский](../../ru/tutorials/building-a-knowledge-base.md) · [العربية](../../ar/tutorials/building-a-knowledge-base.md) · [हिन्दी](../../hi/tutorials/building-a-knowledge-base.md) · [বাংলা](../../bn/tutorials/building-a-knowledge-base.md) · [Tiếng Việt](../../vi/tutorials/building-a-knowledge-base.md)

Neste tutorial transformas um projeto Veles numa base de conhecimento viva: ingeres
algumas fontes, deixas o Veles escrever páginas de wiki, fazes perguntas e consolidas o
que aprendeste. Este é o fluxo **LLM-Wiki** predefinido. Cerca de 15 minutos.

Deves ter concluído primeiro os [Primeiros passos](getting-started.md).

## A ideia

Um projeto Veles tem duas zonas de conteúdo:

- `sources/` — material em bruto e imutável que lhe dás (só de leitura para o agente).
- `wiki/` — o conhecimento próprio do agente, gerado por LLM (a única zona onde ele
  escreve conteúdo).

Tu forneces fontes; o Veles destila-as em páginas de wiki interligadas; tu consultas a
wiki em linguagem natural. Consulta [layout packs e o LLM-Wiki](../explanation/layout-packs-and-llm-wiki.md)
para o porquê.

## 1. Ingerir uma fonte

`veles add` lê um ficheiro ou URL e escreve uma página de wiki que o resume:

```bash
veles add https://en.wikipedia.org/wiki/Knowledge_management
veles add ./notes/meeting-2026-06-01.md
```

Cada `add` produz uma página em `wiki/` e liga-a ao grafo da wiki.

## 2. Ver a wiki crescer

Observa o que foi escrito:

```bash
ls wiki/concepts wiki/entities
```

As páginas referenciam-se umas às outras. O catálogo `wiki/INDEX.md`, carregado a
pedido, mantém um mapa que o agente carrega quando precisa (não um despejo
monolítico de contexto).

## 3. Fazer perguntas

Agora consulta a tua base de conhecimento em linguagem natural:

```bash
veles run "Using the wiki, summarise the main approaches to knowledge management
and cite the pages you used."
```

O Veles pesquisa na wiki, lê as páginas relevantes e responde — fundamentado no que
ingeriste, em vez de depender apenas dos seus dados de treino.

Para um diálogo interativo, faz o mesmo na TUI (`veles tui`).

## 4. Consolidar sessões

À medida que trabalhas, as conversas acumulam-se. Corre o curator para as compactar em
páginas de wiki duradouras e extrair lições:

```bash
veles curate
```

Isto escreve páginas em `wiki/sessions/` e atualiza os insights e regras do projeto.
O Veles também faz isto automaticamente ao longo do tempo — consulta
[memória de projeto e o ciclo de aprendizagem](../explanation/project-memory-and-learning-loop.md).

## 5. Manter a wiki saudável

Com o tempo, as páginas ficam desatualizadas ou órfãs. A operação `lint` deteta-as:

```bash
veles run "lint"
```

(`ingest`, `query` e `lint` são skills incluídas no layout LLM-Wiki; invoca-las
com `veles run "<operation>"` ou deixas o agente chamá-las.)

## O que construíste

Uma base de conhecimento auto-organizada: fontes a entrar, páginas de wiki interligadas
a sair, consultável em linguagem natural, que se torna mais arrumada à medida que o Veles
consolida. A partir daqui:

- **[Gerir skills, ferramentas e módulos](../how-to/manage-skills-and-tools.md)** —
  ensina ao Veles fluxos de trabalho reutilizáveis.
- **[Correr como daemon](../how-to/run-as-daemon.md)** + **[ligar o Telegram](../how-to/connect-telegram.md)** —
  fala com a tua base de conhecimento a partir do telemóvel.
- **[Vários projetos e subprojetos](../how-to/multi-project-and-subprojects.md)** —
  escala para muitas bases de conhecimento.

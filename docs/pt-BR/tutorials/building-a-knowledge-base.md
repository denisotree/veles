# Construindo uma base de conhecimento

> 🌐 **Idiomas:** **English** · [Русский](../../ru/tutorials/building-a-knowledge-base.md)

Neste tutorial você vai transformar um projeto Veles em uma base de conhecimento
viva: ingerir algumas fontes, deixar o Veles escrever páginas de wiki, fazer
perguntas e consolidar o que você aprendeu. Esse é o fluxo padrão **LLM-Wiki**.
Cerca de 15 minutos.

Você já deve ter concluído o [Primeiros passos](getting-started.md) antes.

## A ideia

Um projeto Veles tem duas zonas de conteúdo:

- `sources/` — material bruto e imutável que você fornece (somente leitura para o
  agente).
- `wiki/` — o conhecimento próprio do agente, gerado por LLM (a única zona em que
  ele escreve conteúdo).

Você alimenta as fontes; o Veles as destila em páginas de wiki interligadas; você
consulta a wiki em linguagem natural. Veja [packs de layout e a LLM-Wiki](../explanation/layout-packs-and-llm-wiki.md)
para entender o porquê.

## 1. Ingerir uma fonte

`veles add` lê um arquivo ou uma URL e escreve uma página de wiki resumindo-a:

```bash
veles add https://en.wikipedia.org/wiki/Knowledge_management
veles add ./notes/meeting-2026-06-01.md
```

Cada `add` produz uma página em `wiki/` e a interliga ao grafo da wiki.

## 2. Acompanhe a wiki crescer

Veja o que foi escrito:

```bash
ls wiki/concepts wiki/entities wiki/sources
```

As páginas fazem referências cruzadas entre si. O catálogo sob demanda
`wiki/INDEX.md` mantém um mapa que o agente carrega quando precisa dele (não é um
despejo monolítico de contexto).

## 3. Faça perguntas

Agora consulte sua base de conhecimento em linguagem natural:

```bash
veles run "Using the wiki, summarise the main approaches to knowledge management
and cite the pages you used."
```

O Veles pesquisa na wiki, lê as páginas relevantes e responde — fundamentado no
que você ingeriu, e não apenas nos seus dados de treinamento.

Para um diálogo interativo de ida e volta, faça o mesmo na TUI (`veles tui`).

## 4. Consolidar sessões

Conforme você trabalha, as conversas se acumulam. Execute o curador para
compactá-las em páginas de wiki duradouras e extrair lições:

```bash
veles curate
```

Isso escreve páginas em `wiki/sessions/` e atualiza os insights e as regras do
projeto. O Veles também faz isso automaticamente ao longo do tempo — veja
[memória do projeto e o ciclo de aprendizado](../explanation/project-memory-and-learning-loop.md).

## 5. Mantenha a wiki saudável

Com o tempo, as páginas ficam desatualizadas ou órfãs. A operação `lint` as
encontra:

```bash
veles run "lint"
```

(`ingest`, `query` e `lint` são skills incluídas no layout LLM-Wiki; você as
invoca com `veles run "<operação>"` ou deixa o agente chamá-las.)

## O que você construiu

Uma base de conhecimento auto-organizável: fontes entram, páginas de wiki
interligadas saem, consultável em linguagem natural, e que fica mais organizada à
medida que o Veles consolida. A partir daqui:

- **[Gerenciar skills, ferramentas e módulos](../how-to/manage-skills-and-tools.md)** —
  ensine ao Veles fluxos de trabalho reutilizáveis.
- **[Executar como daemon](../how-to/run-as-daemon.md)** + **[conectar o Telegram](../how-to/connect-telegram.md)** —
  converse com sua base de conhecimento pelo celular.
- **[Múltiplos projetos e subprojetos](../how-to/multi-project-and-subprojects.md)** —
  escale para muitas bases de conhecimento.

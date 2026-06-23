# Layout packs e a LLM-Wiki

> 🌐 **Idiomas:** [English](../../en/explanation/layout-packs-and-llm-wiki.md) · [简体中文](../../zh-CN/explanation/layout-packs-and-llm-wiki.md) · [繁體中文](../../zh-TW/explanation/layout-packs-and-llm-wiki.md) · [日本語](../../ja/explanation/layout-packs-and-llm-wiki.md) · [한국어](../../ko/explanation/layout-packs-and-llm-wiki.md) · [Español](../../es/explanation/layout-packs-and-llm-wiki.md) · [Français](../../fr/explanation/layout-packs-and-llm-wiki.md) · [Italiano](../../it/explanation/layout-packs-and-llm-wiki.md) · [Português (BR)](../../pt-BR/explanation/layout-packs-and-llm-wiki.md) · **Português (PT)** · [Русский](../../ru/explanation/layout-packs-and-llm-wiki.md) · [العربية](../../ar/explanation/layout-packs-and-llm-wiki.md) · [हिन्दी](../../hi/explanation/layout-packs-and-llm-wiki.md) · [বাংলা](../../bn/explanation/layout-packs-and-llm-wiki.md) · [Tiếng Việt](../../vi/explanation/layout-packs-and-llm-wiki.md)

Um **layout pack** define como o *conteúdo do utilizador* de um projeto está organizado —
que diretórios existem, em quais o agente pode escrever e que operações oferece. A
predefinição é a **LLM-Wiki**. Esta é uma opção de conteúdo, e **não** um princípio
central do Veles.

## O que é um layout pack

Um layout pack é um diretório com um manifesto `layout.toml` (mais ficheiros opcionais de
skills e de templates). O manifesto declara:

- **Zonas graváveis** — diretórios onde o agente pode escrever conteúdo (aplicado em cada
  `write_file`).
- **Zonas só de leitura** — material que o agente lê mas nunca modifica.
- **Operações** — fluxos de trabalho nomeados, fornecidos como skills dentro do pack.
- **Scaffold** (`[layout.scaffold]`) — o que o `veles init` cria: diretórios e um template
  `AGENTS.md` opcional (`{name}` é substituído).
- **Engines** (`[layout.engines]`) — qual a maquinaria de conteúdo do núcleo que o pack
  ativa. Hoje existe uma engine: `wiki`. Sem ela, não existem ferramentas de wiki, nem
  recall de wiki, nem injeção de INDEX no projeto.
- **Ficheiro de contexto** (`context_file`) — um ficheiro injetado no prompt de sistema
  estável do agente (a LLM-Wiki usa o `INDEX.md`).

## Packs incorporados

| Pack | O que o `veles init --layout <name>` produz |
|---|---|
| `llm-wiki` *(predefinição)* | A [LLM-Wiki ao estilo Karpathy](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f): `sources/` (só de leitura), `wiki/` (gravável pelo agente), `INDEX.md` injetado no prompt, skills `ingest`/`query`/`lint`, a engine de wiki ativa. |
| `notes` | Um único diretório `notes/` plano onde o agente escreve. Sem maquinaria de wiki. |
| `bare` | Sem qualquer scaffold de conteúdo — para repositórios de código e trabalho de forma livre. As escritas são permissivas dentro da raiz do projeto (continuando sujeitas à escada de confiança). |

## Layouts personalizados

Coloque um pack em `~/.veles/layouts/<name>/layout.toml` (global do utilizador) ou
`<project>/.veles/layouts/<name>/` (local ao projeto; tem precedência sobre packs do
utilizador e incorporados com o mesmo nome) e passe `veles init --layout <name>`. O pack
incorporado `notes` é o exemplo mínimo para copiar. Também pode descrever convenções no
`AGENTS.md` — o layout impõe as zonas, o AGENTS.md orienta o comportamento.

## O que *não* é

O layout governa **apenas o seu conteúdo**. A memória de projeto do próprio Veles —
`memory.db` mais a árvore de artefactos `.veles/memory/` (insights, resumos de sessões,
propostas, o registo de operações do sistema) — é do lado do sistema e funciona de forma
idêntica sob qualquer layout. Mudar de layout nunca toca no ciclo de aprendizagem, nas
sessões ou nos registos. Consulte [arquitetura](architecture.md) e
[layout do projeto](../reference/project-layout.md).

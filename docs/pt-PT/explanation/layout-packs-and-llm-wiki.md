# Layout packs e a LLM-Wiki

> 🌐 **Idiomas:** [English](../../en/explanation/layout-packs-and-llm-wiki.md) · [简体中文](../../zh-CN/explanation/layout-packs-and-llm-wiki.md) · [繁體中文](../../zh-TW/explanation/layout-packs-and-llm-wiki.md) · [日本語](../../ja/explanation/layout-packs-and-llm-wiki.md) · [한국어](../../ko/explanation/layout-packs-and-llm-wiki.md) · [Español](../../es/explanation/layout-packs-and-llm-wiki.md) · [Français](../../fr/explanation/layout-packs-and-llm-wiki.md) · [Italiano](../../it/explanation/layout-packs-and-llm-wiki.md) · [Português (BR)](../../pt-BR/explanation/layout-packs-and-llm-wiki.md) · **Português (PT)** · [Русский](../../ru/explanation/layout-packs-and-llm-wiki.md) · [العربية](../../ar/explanation/layout-packs-and-llm-wiki.md) · [हिन्दी](../../hi/explanation/layout-packs-and-llm-wiki.md) · [বাংলা](../../bn/explanation/layout-packs-and-llm-wiki.md) · [Tiếng Việt](../../vi/explanation/layout-packs-and-llm-wiki.md)

Um **layout pack** define como o *conteúdo do utilizador* de um projeto está organizado —
que diretórios existem, em quais o agente pode escrever e que operações oferece. A
predefinição é o **`bare`**, que não acrescenta ao seu diretório nada além de `.veles/`
e `AGENTS.md`. A **LLM-Wiki** é uma opção do registo de extensões, e **não** um princípio
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
- **Engines** (`[layout.engines]`) — qual a maquinaria de conteúdo que o pack
  pede. Uma engine é fornecida por um módulo (o módulo `wiki` do registo fornece `wiki`).
  Sem ela, não existem ferramentas de wiki, nem recall de wiki, nem injeção de INDEX no
  projeto.
- **Ficheiro de contexto** (`context_file`) — um ficheiro injetado no prompt de sistema
  estável do agente (a LLM-Wiki usa o `INDEX.md`).

## Packs disponíveis

| Pack | De onde vem | O que o `veles init --layout <name>` produz |
|---|---|---|
| `bare` *(predefinição)* | incorporado | Sem qualquer scaffold de conteúdo — para repositórios de código e trabalho de forma livre. As escritas são permissivas dentro da raiz do projeto (continuando sujeitas à escada de confiança). |
| `llm-wiki` | registo (`public:official/llm-wiki`, traz o módulo `wiki`) | A [LLM-Wiki ao estilo Karpathy](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f): `sources/` (só de leitura por convenção, não imposto), `wiki/` (gravável pelo agente), `INDEX.md` injetado no prompt, skills `ingest`/`query`/`lint`/`organize`/`structure_design`, a engine de wiki ativa, `veles add` e `/wiki`. Um prompt comportamental declarado pelo layout (`templates/behaviour.md`) transporta a disciplina sources/wiki e as regras de migração/patch do log. |
| `notes` | registo (`public:official/notes`) | Um único diretório `notes/` plano onde o agente escreve. Sem maquinaria de wiki. |

O `veles init` num terminal pergunta que pack usar (os instalados e os dos seus
registos); escolher um que não está instalado oferece instalá-lo.
`veles registry install llm-wiki` instala-o antecipadamente.

## Projetos anteriores à 1.2.3

Um projeto cujo layout não está instalado (um projeto `llm-wiki` após a atualização, ou
um sem a chave `layout` — todos eram projetos wiki) abre na mesma. Num terminal, `veles`
e `veles run` oferecem instalar o pack (com a engine de que precisa) com uma única
confirmação; noutros sítios — o daemon, os canais, os restantes verbos — o Veles imprime
o comando de instalação uma vez e trabalha sem a wiki. Nada em `wiki/` é tocado.

## Layouts personalizados

Coloque um pack em `~/.veles/layouts/<name>/layout.toml` (global do utilizador) ou
`<project>/.veles/layouts/<name>/` (local ao projeto; tem precedência sobre packs do
utilizador e incorporados com o mesmo nome) e passe `veles init --layout <name>`. O pack
`notes` do registo é um exemplo mínimo para copiar. Um pack que pede uma engine que
nenhum módulo instalado fornece recebe a mesma oferta de instalação. Também pode descrever convenções no
`AGENTS.md` — o layout impõe as zonas, o AGENTS.md orienta o comportamento.

## O que *não* é

O layout governa **apenas o seu conteúdo**. A memória de projeto do próprio Veles —
`memory.db` mais a árvore de artefactos `.veles/memory/` (insights, resumos de sessões,
propostas, o registo de operações do sistema) — é do lado do sistema e funciona de forma
idêntica sob qualquer layout. Mudar de layout nunca toca no ciclo de aprendizagem, nas
sessões ou nos registos. Consulte [arquitetura](architecture.md) e
[layout do projeto](../reference/project-layout.md).

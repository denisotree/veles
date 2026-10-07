# Pacotes de layout e o LLM-Wiki

> 🌐 **Idiomas:** [English](../../en/explanation/layout-packs-and-llm-wiki.md) · [简体中文](../../zh-CN/explanation/layout-packs-and-llm-wiki.md) · [繁體中文](../../zh-TW/explanation/layout-packs-and-llm-wiki.md) · [日本語](../../ja/explanation/layout-packs-and-llm-wiki.md) · [한국어](../../ko/explanation/layout-packs-and-llm-wiki.md) · [Español](../../es/explanation/layout-packs-and-llm-wiki.md) · [Français](../../fr/explanation/layout-packs-and-llm-wiki.md) · [Italiano](../../it/explanation/layout-packs-and-llm-wiki.md) · **Português (BR)** · [Português (PT)](../../pt-PT/explanation/layout-packs-and-llm-wiki.md) · [Русский](../../ru/explanation/layout-packs-and-llm-wiki.md) · [العربية](../../ar/explanation/layout-packs-and-llm-wiki.md) · [हिन्दी](../../hi/explanation/layout-packs-and-llm-wiki.md) · [বাংলা](../../bn/explanation/layout-packs-and-llm-wiki.md) · [Tiếng Việt](../../vi/explanation/layout-packs-and-llm-wiki.md)

Um **pacote de layout** define como o *conteúdo de usuário* de um projeto é
organizado — quais diretórios existem, em quais o agente pode escrever e quais
operações ele oferece. O padrão é o **`bare`**, que não acrescenta ao seu diretório
nada além de `.veles/` e `AGENTS.md`. O **LLM-Wiki** é uma opção do registro de
extensões, **não** um princípio central do Veles.

## O que é um pacote de layout

Um pacote de layout é um diretório com um manifesto `layout.toml` (além de
arquivos opcionais de skills e templates). O manifesto declara:

- **Zonas graváveis** — diretórios nos quais o agente pode escrever conteúdo
  (aplicado em cada `write_file`).
- **Zonas somente leitura** — material que o agente lê, mas nunca modifica.
- **Operações** — fluxos de trabalho nomeados, entregues como skills dentro do
  pacote.
- **Scaffold** (`[layout.scaffold]`) — o que o `veles init` cria: diretórios
  e um template opcional de `AGENTS.md` (`{name}` é substituído).
- **Engines** (`[layout.engines]`) — qual maquinaria de conteúdo o
  pacote pede. Um engine é fornecido por um módulo (o módulo `wiki` do registro
  fornece `wiki`). Sem ele, não existem ferramentas de wiki, nem recall de wiki,
  nem injeção de INDEX no projeto.
- **Arquivo de contexto** (`context_file`) — um arquivo injetado no prompt de
  sistema estável do agente (o LLM-Wiki usa `INDEX.md`).

## Pacotes disponíveis

| Pacote | De onde vem | O que `veles init --layout <name>` produz |
|---|---|---|
| `bare` *(padrão)* | embutido | Nenhum scaffold de conteúdo — para repositórios de código e trabalho em formato livre. As escritas são permissivas dentro da raiz do projeto (ainda sujeitas à escada de confiança). |
| `llm-wiki` | registro (`public:official/llm-wiki`, traz o módulo `wiki`) | O [LLM-Wiki ao estilo Karpathy](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f): `sources/` (somente leitura por convenção, não imposto), `wiki/` (gravável pelo agente), `INDEX.md` injetado no prompt, skills `ingest`/`query`/`lint`/`organize`/`structure_design`, o engine de wiki ativado, `veles add` e `/wiki`. Um prompt comportamental declarado pelo layout (`templates/behaviour.md`) carrega a disciplina sources/wiki e as regras de migração/patch do log. |
| `notes` | registro (`public:official/notes`) | Um único diretório plano `notes/` no qual o agente escreve. Sem maquinaria de wiki. |

O `veles init` em um terminal pergunta qual pacote usar (os instalados e os dos seus
registros); escolher um que não está instalado oferece instalá-lo.
`veles registry install llm-wiki` o instala antecipadamente.

## Projetos anteriores à 1.2.3

Um projeto cujo layout não está instalado (um projeto `llm-wiki` após a atualização, ou
um sem a chave `layout` — todos eram projetos wiki) ainda abre. Em um terminal, `veles`
e `veles run` oferecem instalar o pacote (com o engine de que ele precisa) com uma única
confirmação; em outros lugares — o daemon, os canais, os demais verbos — o Veles imprime
o comando de instalação uma vez e trabalha sem a wiki. Nada em `wiki/` é tocado.

## Layouts customizados

Coloque um pacote em `~/.veles/layouts/<name>/layout.toml` (global do usuário) ou
`<project>/.veles/layouts/<name>/` (local do projeto; tem precedência sobre
pacotes do usuário e embutidos de mesmo nome) e passe `veles init --layout <name>`.
O pacote `notes` do registro é um exemplo mínimo para copiar. Um pacote que pede um
engine que nenhum módulo instalado fornece recebe a mesma oferta de instalação. Você também pode descrever
convenções no `AGENTS.md` — o layout impõe as zonas, o AGENTS.md orienta o
comportamento.

## O que ele *não* é

O layout governa **apenas o seu conteúdo**. A própria memória de projeto do Veles —
`memory.db` mais a árvore de artefatos `.veles/memory/` (insights, resumos de
sessão, propostas, o diário de operações do sistema) — fica do lado do sistema e
funciona de forma idêntica sob qualquer layout. Trocar de layout nunca afeta o
loop de aprendizado, as sessões ou os registros. Veja [arquitetura](architecture.md) e
[layout do projeto](../reference/project-layout.md).

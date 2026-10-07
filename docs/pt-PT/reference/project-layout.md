# Estrutura e estado do projeto

> 🌐 **Idiomas:** [English](../../en/reference/project-layout.md) · [简体中文](../../zh-CN/reference/project-layout.md) · [繁體中文](../../zh-TW/reference/project-layout.md) · [日本語](../../ja/reference/project-layout.md) · [한국어](../../ko/reference/project-layout.md) · [Español](../../es/reference/project-layout.md) · [Français](../../fr/reference/project-layout.md) · [Italiano](../../it/reference/project-layout.md) · [Português (BR)](../../pt-BR/reference/project-layout.md) · **Português (PT)** · [Русский](../../ru/reference/project-layout.md) · [العربية](../../ar/reference/project-layout.md) · [हिन्दी](../../hi/reference/project-layout.md) · [বাংলা](../../bn/reference/project-layout.md) · [Tiếng Việt](../../vi/reference/project-layout.md)

O que o `veles init` cria, onde o Veles guarda o estado e o esquema da memória de projeto.

## O que o `veles init` produz

A metade de conteúdo de utilizador depende do layout pack escolhido (`--layout`,
predefinição `bare` — nada além de `AGENTS.md`); a metade de estado `.veles/` é
idêntica em todo o lado. Abaixo, um projeto com o layout `llm-wiki` do registo:

```
my-project/                  # veles init --layout llm-wiki
├── AGENTS.md                # project context (injected into the agent)
├── CLAUDE.md → AGENTS.md    # symlink, so a `claude` CLI picks up the same context
├── GEMINI.md → AGENTS.md    # symlink, for a `gemini` CLI
├── sources/                 # (llm-wiki) raw source material, readonly by convention
├── wiki/                    # (llm-wiki) the LLM-writable knowledge zone
│   ├── concepts/ entities/ queries/ self-doc/ sessions/
└── .veles/                  # project state (do not commit; machine-managed)
    ├── project.toml         # name, created_at, schema_version, layout
    ├── memory.db            # SQLite: sessions, turns, insights, rules, telemetry
    ├── memory/              # the agent's own memory artefacts:
    │   ├── LOG.md           #   append-only system-ops journal
    │   ├── insights/        #   rendered views of `insights` rows
    │   ├── sessions/        #   compaction summaries
    │   └── proposals/       #   subproject / skill-promotion proposals
    ├── jobs/                # scheduled-job outputs
    └── skills/              # project-local skills
```

Com o `bare` predefinido não há qualquer scaffold de conteúdo; com `notes` (do
registo) a metade de conteúdo é um único diretório `notes/`. O `INDEX.md` (o
catálogo a pedido da wiki) é gerado à medida que a wiki cresce; o `config.toml`, `tools/`
e `plans/` surgem em `.veles/` assim que configuras algo, um agente
escreve uma ferramenta ou corres um objetivo.

## Diretórios de estado

| Caminho | Âmbito | Versionado? |
|---|---|---|
| `<project>/AGENTS.md` + conteúdo do layout (`wiki/`, `sources/`, `notes/`, …) | Conteúdo do projeto | **Sim** — esta é a tua base de conhecimento |
| `<project>/.veles/` | Estado de máquina do projeto (memória, configuração, skills/ferramentas locais) | Não |
| `~/.veles/` | Global do utilizador: `config.toml`, concessões de confiança, skills/ferramentas inter-projeto, layout packs, cache de modelos, locales | Não |

`VELES_USER_HOME` redireciona `~` para a árvore global do utilizador (testes, sandboxes).

## Memória de projeto (`.veles/memory.db` + `.veles/memory/`)

A memória de projeto do Veles é um **artefacto estruturado**, separado do teu
conteúdo e independente do layout. A base de dados SQLite (modo WAL) é a
fonte de verdade; `.veles/memory/` contém o lado legível por humanos (vistas
renderizadas de insights, resumos de sessões, propostas, o journal de operações
do sistema). Tabelas principais:

| Tabela | Contém |
|---|---|
| `sessions`, `turns` | Histórico de conversas (uma linha por turno) |
| `turns_fts` | Índice full-text sobre os turnos (suporta `veles sessions search`) |
| `insights`, `insights_fts`, `insight_refs` | Insights aprendidos (linhas canónicas; as vistas markdown são regeneráveis) + ligações de deduplicação |
| `rules`, `rules_fts` | Regras de formato/do/don't/preferência injetadas no prompt estável |
| `skills`, `skill_uses`, `skill_tool_refs` | Registo de skills + telemetria + ligações a ferramentas |
| `tools`, `tool_uses` | Registo de ferramentas + telemetria (contagens de uso/sucesso/erro) |
| `project_tree` | Mapa em cache dos ficheiros do projeto + tags semânticas para ranking de relevância |

Consulta [Memória de projeto e o ciclo de aprendizagem](../explanation/project-memory-and-learning-loop.md)
para perceber como estes são escritos e recuperados.

## Layout packs

`veles init --layout {bare|llm-wiki|notes|<custom>}` escolhe o layout de
conteúdo (só o `bare` é incorporado; os restantes vêm de um registo e são oferecidos
para instalação); o pack é dono do scaffold, do template AGENTS.md, das zonas
escrevíveis e de qual motor de conteúdo (p. ex. a wiki: ferramentas wiki, injeção do
prompt INDEX, recall da wiki) pede. Consulta
[layout packs e o LLM-Wiki](../explanation/layout-packs-and-llm-wiki.md).

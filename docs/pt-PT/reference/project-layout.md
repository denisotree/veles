# Estrutura e estado do projeto

> 🌐 **Languages:** **English** · [Русский](../../ru/reference/project-layout.md)

O que o `veles init` cria, onde o Veles guarda o estado e o esquema da memória de projeto.

## O que o `veles init` produz

A metade de conteúdo de utilizador depende do layout pack escolhido (`--layout`,
predefinição `llm-wiki`); a metade de estado `.veles/` é idêntica em todo o lado.

```
my-project/                  # veles init  (default llm-wiki layout)
├── AGENTS.md                # project context (injected into the agent)
├── CLAUDE.md → AGENTS.md    # symlink, so a `claude` CLI picks up the same context
├── GEMINI.md → AGENTS.md    # symlink, for a `gemini` CLI
├── sources/                 # raw, immutable source material (agent-readonly)
├── wiki/                    # the LLM-writable knowledge zone
│   ├── concepts/ entities/ queries/ self-doc/ sessions/ sources/
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

Com `--layout notes` a metade de conteúdo é um único diretório `notes/`; com
`--layout bare` não há qualquer scaffold de conteúdo. O `wiki/INDEX.md` (o
catálogo a pedido) é gerado à medida que a wiki cresce; o `config.toml`, `tools/`
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

`veles init --layout {llm-wiki|notes|bare|<custom>}` escolhe o layout de
conteúdo; o pack é dono do scaffold, do template AGENTS.md, das zonas
escrevíveis e de saber se o motor wiki (ferramentas wiki, injeção do prompt
INDEX, recall da wiki) está ativo. Consulta
[layout packs e o LLM-Wiki](../explanation/layout-packs-and-llm-wiki.md).

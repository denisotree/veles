# Layout e estado do projeto

> 🌐 **Idiomas:** [English](../../en/reference/project-layout.md) · [简体中文](../../zh-CN/reference/project-layout.md) · [繁體中文](../../zh-TW/reference/project-layout.md) · [日本語](../../ja/reference/project-layout.md) · [한국어](../../ko/reference/project-layout.md) · [Español](../../es/reference/project-layout.md) · [Français](../../fr/reference/project-layout.md) · [Italiano](../../it/reference/project-layout.md) · **Português (BR)** · [Português (PT)](../../pt-PT/reference/project-layout.md) · [Русский](../../ru/reference/project-layout.md) · [العربية](../../ar/reference/project-layout.md) · [हिन्दी](../../hi/reference/project-layout.md) · [বাংলা](../../bn/reference/project-layout.md) · [Tiếng Việt](../../vi/reference/project-layout.md)

O que o `veles init` cria, onde o Veles guarda o estado e o schema da memória do projeto.

## O que o `veles init` produz

A metade de conteúdo do usuário depende do pacote de layout escolhido (`--layout`,
padrão `llm-wiki`); a metade de estado em `.veles/` é idêntica em todos os casos.

```
my-project/                  # veles init  (layout llm-wiki padrão)
├── AGENTS.md                # contexto do projeto (injetado no agente)
├── CLAUDE.md → AGENTS.md    # symlink, para que uma CLI `claude` capte o mesmo contexto
├── GEMINI.md → AGENTS.md    # symlink, para uma CLI `gemini`
├── sources/                 # material-fonte bruto e imutável (somente leitura pelo agente)
├── wiki/                    # a zona de conhecimento gravável pela LLM
│   ├── concepts/ entities/ queries/ self-doc/ sessions/
└── .veles/                  # estado do projeto (não comitar; gerenciado pela máquina)
    ├── project.toml         # name, created_at, schema_version, layout
    ├── memory.db            # SQLite: sessões, turnos, insights, regras, telemetria
    ├── memory/              # os artefatos de memória do próprio agente:
    │   ├── LOG.md           #   diário de operações do sistema (somente acréscimo)
    │   ├── insights/        #   visões renderizadas das linhas de `insights`
    │   ├── sessions/        #   resumos de compactação
    │   └── proposals/       #   propostas de subprojeto / promoção de skill
    ├── jobs/                # saídas de tarefas agendadas
    └── skills/              # skills locais do projeto
```

Com `--layout notes`, a metade de conteúdo é um único diretório `notes/`; com
`--layout bare` não há scaffold de conteúdo nenhum. O `wiki/INDEX.md` (o
catálogo sob demanda) é gerado conforme a wiki cresce; `config.toml`, `tools/`
e `plans/` aparecem em `.veles/` assim que você configura algo, um agente
escreve uma ferramenta ou você executa um goal.

## Diretórios de estado

| Caminho | Escopo | Comitar? |
|---|---|---|
| `<project>/AGENTS.md` + conteúdo do layout (`wiki/`, `sources/`, `notes/`, …) | Conteúdo do projeto | **Sim** — esta é a sua base de conhecimento |
| `<project>/.veles/` | Estado de máquina do projeto (memória, configuração, skills/ferramentas locais) | Não |
| `~/.veles/` | Global do usuário: `config.toml`, concessões de trust, skills/ferramentas entre projetos, pacotes de layout, cache de modelos, locales | Não |

`VELES_USER_HOME` redireciona `~` para a árvore global do usuário (testes, sandboxes).

## Memória do projeto (`.veles/memory.db` + `.veles/memory/`)

A memória do projeto do Veles é um **artefato estruturado**, separado do seu
conteúdo e independente do layout. O banco SQLite (modo WAL) é a
fonte da verdade; `.veles/memory/` guarda o lado legível por humanos (visões
renderizadas de insights, resumos de sessão, propostas, o diário de operações do sistema).
Tabelas principais:

| Tabela | Contém |
|---|---|
| `sessions`, `turns` | Histórico de conversa (uma linha por turno) |
| `turns_fts` | Índice de texto completo dos turnos (alimenta `veles sessions search`) |
| `insights`, `insights_fts`, `insight_refs` | Insights aprendidos (linhas canônicas; as visões em markdown são regeneráveis) + links de deduplicação |
| `rules`, `rules_fts` | Regras de formato/fazer/não fazer/preferência injetadas no prompt estável |
| `skills`, `skill_uses`, `skill_tool_refs` | Registry de skills + telemetria + links de ferramentas |
| `tools`, `tool_uses` | Registry de ferramentas + telemetria (contagem de usos/sucessos/erros) |
| `project_tree` | Mapa de arquivos do projeto em cache + tags semânticas para ranqueamento de relevância |

Veja [Memória do projeto e o loop de aprendizado](../explanation/project-memory-and-learning-loop.md)
para saber como esses dados são gravados e recuperados.

## Pacotes de layout

`veles init --layout {llm-wiki|notes|bare|<custom>}` escolhe o layout de
conteúdo; o pacote é dono do scaffold, do template do AGENTS.md, das zonas graváveis
e de definir se a engine de wiki (ferramentas de wiki, injeção do INDEX no prompt, recuperação
da wiki) está ativa. Veja
[pacotes de layout e o LLM-Wiki](../explanation/layout-packs-and-llm-wiki.md).

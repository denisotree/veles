# Referência de configuração

> 🌐 **Languages:** **English** · [Русский](../../ru/reference/configuration.md)

O Veles é configurado por dois ficheiros TOML e um conjunto de directórios de estado.
Os segredos (chaves de API, tokens de bot) **nunca** são escritos nestes ficheiros —
residem no chaveiro do SO ou em variáveis de ambiente (ver [variáveis de ambiente](environment-variables.md)).

## Onde reside o estado

| Caminho | Âmbito | Conteúdo |
|---|---|---|
| `~/.veles/` | Global do utilizador | `config.toml`, concessões de confiança, skills/ferramentas transversais a projectos, cache de modelos, locales, registo |
| `<project>/.veles/` | Local do projecto | `project.toml`, `config.toml`, `memory.db`, skills/ferramentas do projecto, planos, artefactos de runtime |
| `<project>/AGENTS.md` | Projecto | O ficheiro de contexto injectado no agente (com symlink para `CLAUDE.md` / `GEMINI.md`) |
| `<project>/wiki/`, `sources/` | Projecto | Conteúdo do utilizador (o layout LLM-Wiki predefinido) |

`VELES_USER_HOME` redirecciona o `~` (para que o estado do utilizador fique em
`<override>/.veles/`). Ver [estrutura do projecto](project-layout.md) para a árvore completa.

---

## Configuração do utilizador — `~/.veles/config.toml`

Escrita pelo assistente do primeiro arranque; segura para editar à mão.

```toml
[user]
language = "en"                  # "en" | "ru" — UI string locale
default_provider = "openrouter"  # default provider for new projects
default_model = "anthropic/claude-sonnet-4.6"
first_project_name = "myorg"     # recorded by the wizard
tui_theme = "everforest"         # everforest | dracula | gruvbox | tokyo-night | catppuccin

[permissions]                    # optional per-tool policy
fetch_url  = "approval_required" # allow | approval_required | always_confirm
write_file = "always_confirm"

[routing.tasks]                  # optional user-scope routing (see below)
compressor = "openrouter:anthropic/claude-haiku-4.5"

[mcp.servers.my-server]          # optional user-scope MCP servers
transport = "stdio"
command = "python"               # executable only — arguments go in `args`
args = ["-m", "my_mcp_server"]
```

| Chave | Tipo | Finalidade |
|---|---|---|
| `[user] language` | `"en"` \| `"ru"` | Locale para as strings da UI (sobreponível via `VELES_LOCALE`) |
| `[user] default_provider` | string | Fornecedor usado quando nenhum é indicado |
| `[user] default_model` | string | Modelo usado quando nenhum é indicado |
| `[user] tui_theme` | string | Tema de cores predefinido da TUI |
| `[permissions] <tool>` | política | Política de permissões por ferramenta (ver [confiança e sandbox](../explanation/trust-and-sandbox.md)) |

---

## Configuração do projecto — `<project>/.veles/config.toml`

```toml
[provider]
default = "openrouter"                               # provider name for the main agent + routing base
model = "anthropic/claude-sonnet-4.6"                # model id (omit to require --model or the user default_model)

[routing.tasks]                  # per-task overrides (highest priority below explicit flags)
default    = "openrouter:anthropic/claude-sonnet-4.6"
compressor = "openrouter:anthropic/claude-haiku-4.5"
insights   = "openrouter:anthropic/claude-haiku-4.5"
advisor    = "openrouter:anthropic/claude-opus-4.8"
vision     = "openai:gpt-4o"
embedding  = "openai:text-embedding-3-small"

[daemon]                         # the unnamed/"default" daemon
enabled = true
host = "127.0.0.1"
port = 8765
autostart = false

[daemon.api]                     # a named daemon session ("api")
provider = "anthropic"
model = "claude-opus-4.8"
host = "127.0.0.1"
port = 8801
mode = "auto"

[channels.telegram]              # global channels (served by the unnamed daemon)
enabled = true
whitelist = ["@alice", "123456789"]

[daemon.api.channels.telegram]   # channels bound to a named daemon session
enabled = true
whitelist = ["@bob"]

[mcp.servers.github]             # external MCP servers (project scope)
transport = "stdio"             # stdio | http | sse
command = "npx"                  # executable only — arguments go in `args`
args = ["-y", "@modelcontextprotocol/server-github"]
env = { GITHUB_TOKEN = "${GITHUB_TOKEN}" }   # ${VAR} interpolates from the environment
```

### Secções

| Secção | Finalidade |
|---|---|
| `[provider]` | Fornecedor base (`default` = nome do fornecedor) + modelo (`model` = id do modelo) para o agente principal e a cascata de encaminhamento |
| `[routing.tasks]` | Sobreposições `provider:model` por tarefa — ver [encaminhamento por tarefa](../how-to/per-task-routing.md) |
| `[permissions]` | Política de permissões por ferramenta (âmbito do projecto) |
| `[daemon]` | Vínculo (bind) + autostart do daemon sem nome/"default" |
| `[daemon.<name>]` | Uma sessão de daemon nomeada (modelo/fornecedor/host/porta/modo próprios) |
| `[channels.<type>]` | Um canal servido pelo daemon sem nome (p. ex. `telegram`) |
| `[daemon.<name>.channels.<type>]` | Um canal ligado a uma sessão de daemon nomeada |
| `[mcp.servers.<name>]` | Um servidor MCP externo (fonte de ferramentas) |

Tipos de tarefa para `[routing.tasks]`: `default`, `curator`, `compressor`, `insights`,
`skills`, `advisor`, `vision`, `embedding`.

> As pistas de encaminhamento em linguagem natural no `AGENTS.md` são analisadas para um
> `routing.nl.toml` gerado automaticamente; as entradas explícitas em `[routing.tasks]`
> ganham sempre. Execute `veles route refresh` para reanalisar. Ver
> [encaminhamento por tarefa](../how-to/per-task-routing.md).

### `project.toml`

O `<project>/.veles/project.toml` contém metadados imutáveis do projecto (`name`,
`created_at`, `schema_version`, `layout`). Normalmente não o edita à mão.

---

## AGENTS.md

O ficheiro de contexto do projecto, na raiz do projecto. É injectado no prompt de sistema
do agente no arranque e ligado por symlink a `CLAUDE.md` e `GEMINI.md` para que uma CLI
`claude` ou `gemini` lançada no directório apanhe o mesmo contexto.

Mantenha-o pequeno — os ficheiros `.md` auxiliares (p. ex. `wiki/INDEX.md`) carregam a
pedido. Valide as secções obrigatórias com `veles schema validate`. Ver
[packs de layout e o LLM-Wiki](../explanation/layout-packs-and-llm-wiki.md).

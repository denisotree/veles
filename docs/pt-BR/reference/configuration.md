# Referência de configuração

> 🌐 **Idiomas:** [English](../../en/reference/configuration.md) · [简体中文](../../zh-CN/reference/configuration.md) · [繁體中文](../../zh-TW/reference/configuration.md) · [日本語](../../ja/reference/configuration.md) · [한국어](../../ko/reference/configuration.md) · [Español](../../es/reference/configuration.md) · [Français](../../fr/reference/configuration.md) · [Italiano](../../it/reference/configuration.md) · **Português (BR)** · [Português (PT)](../../pt-PT/reference/configuration.md) · [Русский](../../ru/reference/configuration.md) · [العربية](../../ar/reference/configuration.md) · [हिन्दी](../../hi/reference/configuration.md) · [বাংলা](../../bn/reference/configuration.md) · [Tiếng Việt](../../vi/reference/configuration.md)

O Veles é configurado por dois arquivos TOML e um conjunto de diretórios de
estado. Segredos (chaves de API, tokens de bot) **nunca** são gravados nesses
arquivos — eles ficam no chaveiro do SO ou em variáveis de ambiente (veja
[variáveis de ambiente](environment-variables.md)).

## Onde o estado fica

| Caminho | Escopo | Conteúdo |
|---|---|---|
| `~/.veles/` | Global do usuário | `config.toml`, concessões de confiança, skills/tools entre projetos, cache de modelos, locales, registry |
| `<project>/.veles/` | Local do projeto | `project.toml`, `config.toml`, `memory.db`, skills/tools do projeto, planos, artefatos de runtime |
| `<project>/AGENTS.md` | Projeto | O arquivo de contexto injetado no agente (com symlink para `CLAUDE.md` / `GEMINI.md`) |
| `<project>/wiki/`, `sources/` | Projeto | Conteúdo do usuário (o layout padrão LLM-Wiki) |

`VELES_USER_HOME` redireciona o `~` (de modo que o estado do usuário fica em
`<override>/.veles/`). Veja [layout do projeto](project-layout.md) para a árvore completa.

---

## Config do usuário — `~/.veles/config.toml`

Escrito pelo assistente de primeira execução; pode ser editado à mão com segurança.

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
| `[user] language` | `"en"` \| `"ru"` | Locale das strings da UI (sobrescrevível via `VELES_LOCALE`) |
| `[user] default_provider` | string | Provedor usado quando nenhum é informado |
| `[user] default_model` | string | Modelo usado quando nenhum é informado |
| `[user] tui_theme` | string | Tema de cores padrão da TUI |
| `[permissions] <tool>` | política | Política de permissão por tool (veja [confiança e sandbox](../explanation/trust-and-sandbox.md)) |

---

## Config do projeto — `<project>/.veles/config.toml`

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

### Seções

| Seção | Finalidade |
|---|---|
| `[provider]` | Provedor base (`default` = nome do provedor) + modelo (`model` = id do modelo) para o agente principal e a cascata de roteamento |
| `[routing.tasks]` | Sobrescritas `provider:model` por tarefa — veja [roteamento por tarefa](../how-to/per-task-routing.md) |
| `[permissions]` | Política de permissão por tool (escopo do projeto) |
| `[daemon]` | Bind + autostart do daemon sem nome/"default" |
| `[daemon.<name>]` | Uma sessão de daemon nomeada (modelo/provedor/host/porta/modo próprios) |
| `[channels.<type>]` | Um canal servido pelo daemon sem nome (ex.: `telegram`) |
| `[daemon.<name>.channels.<type>]` | Um canal vinculado a uma sessão de daemon nomeada |
| `[mcp.servers.<name>]` | Um servidor MCP externo (fonte de tools) |

Tipos de tarefa para `[routing.tasks]`: `default`, `curator`, `compressor`,
`insights`, `skills`, `advisor`, `vision`, `embedding`.

> Dicas de roteamento em linguagem natural no `AGENTS.md` são analisadas e
> transformadas em um `routing.nl.toml` gerado automaticamente; entradas explícitas
> em `[routing.tasks]` sempre prevalecem. Execute `veles route refresh` para
> reanalisar. Veja [roteamento por tarefa](../how-to/per-task-routing.md).

### `project.toml`

`<project>/.veles/project.toml` guarda metadados imutáveis do projeto (`name`,
`created_at`, `schema_version`, `layout`). Normalmente você não o edita à mão.

---

## AGENTS.md

O arquivo de contexto do projeto, na raiz do projeto. Ele é injetado no system
prompt do agente na inicialização e recebe symlink para `CLAUDE.md` e `GEMINI.md`,
de modo que uma CLI `claude` ou `gemini` iniciada no diretório pegue o mesmo
contexto.

Mantenha-o pequeno — arquivos `.md` auxiliares (ex.: `wiki/INDEX.md`) carregam sob
demanda. Valide as seções obrigatórias com `veles schema validate`. Veja
[pacotes de layout e a LLM-Wiki](../explanation/layout-packs-and-llm-wiki.md).

# Referência de configuração

> 🌐 **Idiomas:** **English** · [Русский](../../ru/reference/configuration.md)

O Veles é configurado por dois arquivos TOML e um conjunto de diretórios de estado. Segredos
(chaves de API, tokens de bot) **nunca** são gravados nesses arquivos — eles ficam no
keychain do SO ou em variáveis de ambiente (veja [variáveis de ambiente](environment-variables.md)).

## Onde o estado fica

| Caminho | Escopo | Conteúdo |
|---|---|---|
| `~/.veles/` | Global do usuário | `config.toml`, concessões de trust, skills/ferramentas entre projetos, cache de modelos, locales, registry |
| `<project>/.veles/` | Local do projeto | `project.toml`, `config.toml`, `memory.db`, skills/ferramentas do projeto, planos, artefatos de runtime |
| `<project>/AGENTS.md` | Projeto | O arquivo de contexto injetado no agente (com symlink para `CLAUDE.md` / `GEMINI.md`) |
| `<project>/wiki/`, `sources/` | Projeto | Conteúdo do usuário (o layout LLM-Wiki padrão) |

`VELES_USER_HOME` redireciona `~` (de modo que o estado do usuário fique em `<override>/.veles/`).
Veja [layout do projeto](project-layout.md) para a árvore completa.

---

## Configuração do usuário — `~/.veles/config.toml`

Escrita pelo assistente da primeira execução; pode ser editada à mão com segurança.

```toml
[user]
language = "en"                  # "en" | "ru" — locale das strings da interface
default_provider = "openrouter"  # provedor padrão para novos projetos
default_model = "anthropic/claude-sonnet-4.6"
first_project_name = "myorg"     # registrado pelo assistente
tui_theme = "everforest"         # everforest | dracula | gruvbox | tokyo-night | catppuccin

[permissions]                    # política opcional por ferramenta
fetch_url  = "approval_required" # approval_required | always_confirm | always_allow
write_file = "always_confirm"

[routing.tasks]                  # roteamento opcional de escopo de usuário (veja abaixo)
compressor = "openrouter:anthropic/claude-haiku-4.5"

[mcp.servers.my-server]          # servidores MCP opcionais de escopo de usuário
transport = "stdio"
command = "python"               # apenas o executável — os argumentos vão em `args`
args = ["-m", "my_mcp_server"]
```

| Chave | Tipo | Finalidade |
|---|---|---|
| `[user] language` | `"en"` \| `"ru"` | Locale das strings da interface (sobrescrevível via `VELES_LOCALE`) |
| `[user] default_provider` | string | Provedor usado quando nenhum é informado |
| `[user] default_model` | string | Modelo usado quando nenhum é informado |
| `[user] tui_theme` | string | Tema de cores padrão da TUI |
| `[permissions] <tool>` | política | Política de permissão por ferramenta (veja [trust e sandbox](../explanation/trust-and-sandbox.md)) |

---

## Configuração do projeto — `<project>/.veles/config.toml`

```toml
[provider]
default = "openrouter:anthropic/claude-sonnet-4.6"   # base para o agente principal + roteamento

[routing.tasks]                  # overrides por tarefa (maior prioridade abaixo de flags explícitas)
default    = "openrouter:anthropic/claude-sonnet-4.6"
compressor = "openrouter:anthropic/claude-haiku-4.5"
insights   = "openrouter:anthropic/claude-haiku-4.5"
advisor    = "openrouter:anthropic/claude-opus-4.8"
vision     = "openai:gpt-4o"
embedding  = "openai:text-embedding-3-small"

[daemon]                         # o daemon sem nome/"default"
enabled = true
host = "127.0.0.1"
port = 8765
autostart = false

[daemon.api]                     # uma sessão de daemon nomeada ("api")
provider = "anthropic"
model = "claude-opus-4.8"
host = "127.0.0.1"
port = 8801
mode = "auto"

[channels.telegram]              # canais globais (servidos pelo daemon sem nome)
enabled = true
whitelist = ["@alice", "123456789"]

[daemon.api.channels.telegram]   # canais vinculados a uma sessão de daemon nomeada
enabled = true
whitelist = ["@bob"]

[mcp.servers.github]             # servidores MCP externos (escopo de projeto)
transport = "stdio"             # stdio | http | sse
command = "npx"                  # apenas o executável — os argumentos vão em `args`
args = ["-y", "@modelcontextprotocol/server-github"]
env = { GITHUB_TOKEN = "${GITHUB_TOKEN}" }   # ${VAR} interpola a partir do ambiente
```

### Seções

| Seção | Finalidade |
|---|---|
| `[provider]` | Provedor/modelo base para o agente principal e a cascata de roteamento |
| `[routing.tasks]` | Overrides de `provider:model` por tarefa — veja [roteamento por tarefa](../how-to/per-task-routing.md) |
| `[permissions]` | Política de permissão por ferramenta (escopo de projeto) |
| `[daemon]` | Bind + autostart do daemon sem nome/"default" |
| `[daemon.<name>]` | Uma sessão de daemon nomeada (model/provider/host/port/mode próprios) |
| `[channels.<type>]` | Um canal servido pelo daemon sem nome (ex.: `telegram`) |
| `[daemon.<name>.channels.<type>]` | Um canal vinculado a uma sessão de daemon nomeada |
| `[mcp.servers.<name>]` | Um servidor MCP externo (fonte de ferramentas) |

Tipos de tarefa para `[routing.tasks]`: `default`, `curator`, `compressor`, `insights`,
`skills`, `advisor`, `vision`, `embedding`.

> Dicas de roteamento em linguagem natural no `AGENTS.md` são analisadas em um
> `routing.nl.toml` gerado automaticamente; entradas explícitas em `[routing.tasks]` sempre vencem. Execute
> `veles route refresh` para re-analisar. Veja [roteamento por tarefa](../how-to/per-task-routing.md).

### `project.toml`

`<project>/.veles/project.toml` guarda metadados imutáveis do projeto (`name`,
`created_at`, `schema_version`, `layout`). Normalmente você não o edita à mão.

---

## AGENTS.md

O arquivo de contexto do projeto, na raiz do projeto. Ele é injetado no prompt do
sistema do agente na inicialização e tem symlink para `CLAUDE.md` e `GEMINI.md`, de modo que uma
CLI `claude` ou `gemini` iniciada no diretório capte o mesmo contexto.

Mantenha-o pequeno — arquivos `.md` auxiliares (ex.: `wiki/INDEX.md`) carregam sob demanda.
Valide as seções obrigatórias com `veles schema validate`. Veja
[pacotes de layout e o LLM-Wiki](../explanation/layout-packs-and-llm-wiki.md).

# Referência de configuração

> 🌐 **Languages:** **English** · [Русский](../../ru/reference/configuration.md)

O Veles é configurado por dois ficheiros TOML e um conjunto de diretórios de
estado. Os segredos (chaves de API, tokens de bots) **nunca** são escritos nestes
ficheiros — ficam no porta-chaves (keychain) do sistema operativo ou em variáveis
de ambiente (consulte [variáveis de ambiente](environment-variables.md)).

## Onde fica o estado

| Caminho | Âmbito | Conteúdo |
|---|---|---|
| `~/.veles/` | Global do utilizador | `config.toml`, autorizações de confiança, skills/ferramentas entre projetos, cache de modelos, locales, registo |
| `<project>/.veles/` | Local do projeto | `project.toml`, `config.toml`, `memory.db`, skills/ferramentas do projeto, planos, artefactos de execução |
| `<project>/AGENTS.md` | Projeto | O ficheiro de contexto injetado no agente (com symlink para `CLAUDE.md` / `GEMINI.md`) |
| `<project>/wiki/`, `sources/` | Projeto | Conteúdo do utilizador (o layout LLM-Wiki por omissão) |

`VELES_USER_HOME` redireciona `~` (de modo que o estado do utilizador fica em
`<override>/.veles/`). Consulte [layout do projeto](project-layout.md) para a
árvore completa.

---

## Configuração do utilizador — `~/.veles/config.toml`

Escrita pelo assistente da primeira execução; segura para editar à mão.

```toml
[user]
language = "en"                  # "en" | "ru" — locale das strings da UI
default_provider = "openrouter"  # fornecedor predefinido para novos projetos
default_model = "anthropic/claude-sonnet-4.6"
first_project_name = "myorg"     # registado pelo assistente
tui_theme = "everforest"         # everforest | dracula | gruvbox | tokyo-night | catppuccin

[permissions]                    # política opcional por ferramenta
fetch_url  = "approval_required" # approval_required | always_confirm | always_allow
write_file = "always_confirm"

[routing.tasks]                  # encaminhamento opcional de âmbito de utilizador (ver abaixo)
compressor = "openrouter:anthropic/claude-haiku-4.5"

[mcp.servers.my-server]          # servidores MCP opcionais de âmbito de utilizador
transport = "stdio"
command = "python"               # apenas o executável — os argumentos vão em `args`
args = ["-m", "my_mcp_server"]
```

| Chave | Tipo | Finalidade |
|---|---|---|
| `[user] language` | `"en"` \| `"ru"` | Locale para as strings da UI (substituível via `VELES_LOCALE`) |
| `[user] default_provider` | string | Fornecedor usado quando nenhum é indicado |
| `[user] default_model` | string | Modelo usado quando nenhum é indicado |
| `[user] tui_theme` | string | Tema de cores predefinido da TUI |
| `[permissions] <tool>` | política | Política de permissões por ferramenta (consulte [confiança e sandbox](../explanation/trust-and-sandbox.md)) |

---

## Configuração do projeto — `<project>/.veles/config.toml`

```toml
[provider]
default = "openrouter:anthropic/claude-sonnet-4.6"   # base para o agente principal + encaminhamento

[routing.tasks]                  # substituições por tarefa (prioridade mais alta abaixo das opções explícitas)
default    = "openrouter:anthropic/claude-sonnet-4.6"
compressor = "openrouter:anthropic/claude-haiku-4.5"
insights   = "openrouter:anthropic/claude-haiku-4.5"
advisor    = "openrouter:anthropic/claude-opus-4.8"
vision     = "openai:gpt-4o"
embedding  = "openai:text-embedding-3-small"

[daemon]                         # o daemon sem nome / "default"
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

[daemon.api.channels.telegram]   # canais ligados a uma sessão de daemon nomeada
enabled = true
whitelist = ["@bob"]

[mcp.servers.github]             # servidores MCP externos (âmbito de projeto)
transport = "stdio"             # stdio | http | sse
command = "npx"                  # apenas o executável — os argumentos vão em `args`
args = ["-y", "@modelcontextprotocol/server-github"]
env = { GITHUB_TOKEN = "${GITHUB_TOKEN}" }   # ${VAR} interpola a partir do ambiente
```

### Secções

| Secção | Finalidade |
|---|---|
| `[provider]` | Fornecedor/modelo base para o agente principal e a cascata de encaminhamento |
| `[routing.tasks]` | Substituições de `provider:model` por tarefa — consulte [encaminhamento por tarefa](../how-to/per-task-routing.md) |
| `[permissions]` | Política de permissões por ferramenta (âmbito de projeto) |
| `[daemon]` | Endereço de ligação + autostart do daemon sem nome / "default" |
| `[daemon.<name>]` | Uma sessão de daemon nomeada (modelo/fornecedor/host/porta/modo próprios) |
| `[channels.<type>]` | Um canal servido pelo daemon sem nome (por exemplo, `telegram`) |
| `[daemon.<name>.channels.<type>]` | Um canal ligado a uma sessão de daemon nomeada |
| `[mcp.servers.<name>]` | Um servidor MCP externo (fonte de ferramentas) |

Tipos de tarefa para `[routing.tasks]`: `default`, `curator`, `compressor`,
`insights`, `skills`, `advisor`, `vision`, `embedding`.

> As sugestões de encaminhamento em linguagem natural no `AGENTS.md` são
> interpretadas e geram automaticamente um `routing.nl.toml`; as entradas
> explícitas em `[routing.tasks]` prevalecem sempre. Execute
> `veles route refresh` para reinterpretar. Consulte [encaminhamento por tarefa](../how-to/per-task-routing.md).

### `project.toml`

`<project>/.veles/project.toml` contém os metadados imutáveis do projeto (`name`,
`created_at`, `schema_version`, `layout`). Normalmente não o edita à mão.

---

## AGENTS.md

O ficheiro de contexto do projeto na raiz do projeto. É injetado no system prompt
do agente no arranque e tem symlinks para `CLAUDE.md` e `GEMINI.md`, de modo que
uma CLI `claude` ou `gemini` iniciada no diretório capta o mesmo contexto.

Mantenha-o pequeno — os ficheiros `.md` auxiliares (por exemplo, `wiki/INDEX.md`)
carregam a pedido. Valide as secções obrigatórias com `veles schema validate`.
Consulte [pacotes de layout e a LLM-Wiki](../explanation/layout-packs-and-llm-wiki.md).

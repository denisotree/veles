# 配置参考

> 🌐 **Languages:** **English** · [Русский](../../ru/reference/configuration.md)

Veles 由两个 TOML 文件和一组状态目录进行配置。密钥
（API 密钥、机器人令牌）**绝不会**写入这些文件 —— 它们保存在操作系统
钥匙串或环境变量中（参见[环境变量](environment-variables.md)）。

## 状态存储位置

| 路径 | 作用域 | 内容 |
|---|---|---|
| `~/.veles/` | 用户全局 | `config.toml`、信任授权、跨项目技能/工具、模型缓存、locales、注册表 |
| `<project>/.veles/` | 项目本地 | `project.toml`、`config.toml`、`memory.db`、项目技能/工具、计划、运行时临时数据 |
| `<project>/AGENTS.md` | 项目 | 注入到智能体的上下文文件（符号链接到 `CLAUDE.md` / `GEMINI.md`） |
| `<project>/wiki/`、`sources/` | 项目 | 用户内容（默认的 LLM-Wiki 布局） |

`VELES_USER_HOME` 重定向 `~`（因此用户状态会落到 `<override>/.veles/`）。
完整的目录树参见[项目布局](project-layout.md)。

---

## 用户配置 —— `~/.veles/config.toml`

由首次运行的向导写入；可以手动安全地编辑。

```toml
[user]
language = "en"                  # "en" | "ru" — UI string locale
default_provider = "openrouter"  # default provider for new projects
default_model = "anthropic/claude-sonnet-4.6"
first_project_name = "myorg"     # recorded by the wizard
tui_theme = "everforest"         # everforest | dracula | gruvbox | tokyo-night | catppuccin

[permissions]                    # optional per-tool policy
fetch_url  = "approval_required" # approval_required | always_confirm | always_allow
write_file = "always_confirm"

[routing.tasks]                  # optional user-scope routing (see below)
compressor = "openrouter:anthropic/claude-haiku-4.5"

[mcp.servers.my-server]          # optional user-scope MCP servers
transport = "stdio"
command = "python"               # executable only — arguments go in `args`
args = ["-m", "my_mcp_server"]
```

| 键 | 类型 | 用途 |
|---|---|---|
| `[user] language` | `"en"` \| `"ru"` | UI 字符串的语言（可通过 `VELES_LOCALE` 覆盖） |
| `[user] default_provider` | string | 未指定时使用的提供方 |
| `[user] default_model` | string | 未指定时使用的模型 |
| `[user] tui_theme` | string | 默认 TUI 配色主题 |
| `[permissions] <tool>` | policy | 按工具的权限策略（参见[信任与沙箱](../explanation/trust-and-sandbox.md)） |

---

## 项目配置 —— `<project>/.veles/config.toml`

```toml
[provider]
default = "openrouter:anthropic/claude-sonnet-4.6"   # base for the main agent + routing

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

### 各小节

| 小节 | 用途 |
|---|---|
| `[provider]` | 主智能体和路由级联的基础提供方/模型 |
| `[routing.tasks]` | 按任务的 `provider:model` 覆盖 —— 参见[按任务路由](../how-to/per-task-routing.md) |
| `[permissions]` | 按工具的权限策略（项目作用域） |
| `[daemon]` | 未命名/“default”守护进程的绑定 + 自启动 |
| `[daemon.<name>]` | 一个命名守护进程会话（拥有自己的 model/provider/host/port/mode） |
| `[channels.<type>]` | 由未命名守护进程服务的频道（例如 `telegram`） |
| `[daemon.<name>.channels.<type>]` | 绑定到某个命名守护进程会话的频道 |
| `[mcp.servers.<name>]` | 一个外部 MCP 服务器（工具源） |

`[routing.tasks]` 的任务类型：`default`、`curator`、`compressor`、`insights`、
`skills`、`advisor`、`vision`、`embedding`。

> `AGENTS.md` 中的自然语言路由提示会被解析进一个自动生成的
> `routing.nl.toml`；显式的 `[routing.tasks]` 条目始终优先。运行
> `veles route refresh` 来重新解析。参见[按任务路由](../how-to/per-task-routing.md)。

### `project.toml`

`<project>/.veles/project.toml` 保存不可变的项目元数据（`name`、
`created_at`、`schema_version`、`layout`）。通常你不需要手动编辑它。

---

## AGENTS.md

位于项目根目录的项目上下文文件。它在启动时被注入到智能体的
系统提示中，并被符号链接到 `CLAUDE.md` 和 `GEMINI.md`，这样在该目录中
启动的 `claude` 或 `gemini` CLI 就能获取相同的上下文。

保持它简短 —— 辅助的 `.md` 文件（例如 `wiki/INDEX.md`）按需加载。
用 `veles schema validate` 校验必需的小节。参见
[布局包与 LLM-Wiki](../explanation/layout-packs-and-llm-wiki.md)。

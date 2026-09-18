# 配置参考

> 🌐 **语言：** [English](../../en/reference/configuration.md) · **简体中文** · [繁體中文](../../zh-TW/reference/configuration.md) · [日本語](../../ja/reference/configuration.md) · [한국어](../../ko/reference/configuration.md) · [Español](../../es/reference/configuration.md) · [Français](../../fr/reference/configuration.md) · [Italiano](../../it/reference/configuration.md) · [Português (BR)](../../pt-BR/reference/configuration.md) · [Português (PT)](../../pt-PT/reference/configuration.md) · [Русский](../../ru/reference/configuration.md) · [العربية](../../ar/reference/configuration.md) · [हिन्दी](../../hi/reference/configuration.md) · [বাংলা](../../bn/reference/configuration.md) · [Tiếng Việt](../../vi/reference/configuration.md)

Veles 由两个 TOML 文件和一组状态目录进行配置。密钥（API key、bot token）**绝不会**写入这些文件——它们存放在操作系统钥匙串或环境变量中（参见[环境变量](environment-variables.md)）。

## 状态存放位置

| 路径 | 作用域 | 内容 |
|---|---|---|
| `~/.veles/` | 用户全局 | `config.toml`、trust 授权、跨项目 skills/tools、模型缓存、本地化、注册表 |
| `<project>/.veles/` | 项目本地 | `project.toml`、`config.toml`、`memory.db`、项目级 skills/tools、plans、运行时临时数据 |
| `<project>/AGENTS.md` | 项目 | 注入到 agent 中的上下文文件（符号链接到 `CLAUDE.md` / `GEMINI.md`） |
| `<project>/wiki/`、`sources/` | 项目 | 用户内容（默认的 LLM-Wiki 布局） |

`VELES_USER_HOME` 会重定向 `~`（这样用户状态会落到 `<override>/.veles/`）。完整目录树参见[项目布局](project-layout.md)。

---

## 用户配置 — `~/.veles/config.toml`

由首次运行的向导写入；可以安全地手动编辑。

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

| 键 | 类型 | 用途 |
|---|---|---|
| `[user] language` | `"en"` \| `"ru"` | UI 字符串的语言（可通过 `VELES_LOCALE` 覆盖） |
| `[user] default_provider` | string | 未指定时使用的提供方 |
| `[user] default_model` | string | 未指定时使用的模型 |
| `[user] tui_theme` | string | 默认的 TUI 配色主题 |
| `[permissions] <tool>` | policy | 按 tool 的权限策略（参见[信任与沙箱](../explanation/trust-and-sandbox.md)） |

---

## 项目配置 — `<project>/.veles/config.toml`

```toml
[engine]
provider = "openrouter"                               # provider name for the main agent + routing base
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

### 各节

| 节 | 用途 |
|---|---|
| `[engine]` | 基础提供方（`provider` = 提供方名称）+ 模型（`model` = 模型 id），供主 agent 和路由级联使用 |
| `[routing.tasks]` | 按任务的 `provider:model` 覆盖——参见[按任务路由](../how-to/per-task-routing.md) |
| `[permissions]` | 按 tool 的权限策略（项目作用域） |
| `[daemon]` | 未命名/"默认" daemon 的绑定地址 + 自动启动 |
| `[daemon.<name>]` | 一个具名 daemon session（拥有自己的 model/provider/host/port/mode） |
| `[channels.<type>]` | 由未命名 daemon 提供服务的 channel（例如 `telegram`） |
| `[daemon.<name>.channels.<type>]` | 绑定到某个具名 daemon session 的 channel |
| `[mcp.servers.<name>]` | 一个外部 MCP 服务器（tool 来源） |

`[routing.tasks]` 的任务类型：`default`、`curator`、`compressor`、`insights`、`skills`、`advisor`、`vision`、`embedding`。

> `AGENTS.md` 中的自然语言路由提示会被解析为自动生成的 `routing.nl.toml`；显式的 `[routing.tasks]` 条目始终优先。运行 `veles route refresh` 重新解析。参见[按任务路由](../how-to/per-task-routing.md)。

### 固定后端，以及其他请求体键

`[engine.request.<provider>]` 会**原样**转发到该提供商的请求体中。Veles 不去建模
上游的 schema，因此提供商接受的任何选项都能直接生效，无需等待 Veles 支持：

```toml
[engine.request.openrouter.provider]
order = ["GMICloud"]
allow_fallbacks = false

[engine.request.openrouter.reasoning]
enabled = false
```

该小节以**提供商名称**为键（`openrouter`、`anthropic`、`openai`、`gemini`、
`ollama`、`llamacpp`、`openai-compat`），这样同一份项目配置就能跨越后端切换：把
OpenRouter 的 `provider` 块发给 llama.cpp 会得到 400，所以每个后端只读自己的子小节。
不声明该小节时，请求与之前逐字节相同。

**什么时候需要它：可复现的测量。** 像 OpenRouter 这样的中继会把同一个模型分发到许多
量化方式不同的后端，于是同样输入的两次运行可能因为与输入无关的原因而不一致。基于
`session_id` 的粘性路由能把一次会话固定在同一个后端，却不会告诉你是**哪一个**。

请用 `order` 固定，而不是 `quantizations`。截至 2026-09-18，`z-ai/glm-5.3-flash`
有 29 个端点：`fp8` 16 个、`fp4` 3 个、`nvfp4` 1 个、**完全不声明量化方式的有 9 个**，
`bf16` 一个也没有。因此 `quantizations = ["fp8"]` 仍会留下 16 个候选，上下文窗口
从 262144 到 1310720 token 不等；而只含一个元素的 `order` 加上
`allow_fallbacks = false` 则能唯一确定后端。列出某个模型的端点：

```bash
curl -s https://openrouter.ai/api/v1/models/<author>/<slug>/endpoints \
  -H "Authorization: Bearer $OPENROUTER_API_KEY" | jq '.data.endpoints[]
  | {provider_name, quantization, context_length}'
```

固定只保留在测量项目里——生产环境需要粘性路由，它保住了可用性和回退。

**验证固定是否生效。** 每次模型调用都会把意图和结果一起写入
`.veles/traces.jsonl`：`request_extra` 是发出去的内容，`upstream_provider` 是真正
应答的后端。一行命令即可：

```bash
jq -r 'select(.session_id=="<sid>") | .upstream_provider' .veles/traces.jsonl | sort -u
```

输出多于一行，说明这次运行混用了后端。同样的记录还带有 `reasoning_tokens`（预算中
用于推理的部分）和 `est_cost_usd`（上游报告的实际计费成本）。

**错误是故意吵闹的。** 提供商名称拼错，或小节路径写错（`[engine.reqest.…]`），都会以
`ConfigError` 中断运行，并指出文件名和已知的提供商：一个从未到达线路的固定，会悄悄
使它本来要服务的测量失效。提供商子小节*内部*的键 Veles 不做校验，因为上游会校验：
OpenRouter 对未知键返回 `400 provider: Unrecognized key: "quantization"`，对无法匹配
的值返回 `404 No endpoints found …`。

### 对话记录保留多久

```toml
[memory]
turn_retention_days = 90   # 0 表示永久保留
```

原始对话轮次会在超过该天数后删除，而从中提取出的**洞察**和规则则永久保留。记录是
原材料，洞察才是阅读它的目的——于是 `memory.db` 不再无限增长，而智能体仍保有它学到的
东西。

一份记录被丢弃需要**同时**满足两个条件：早于保留窗口，**并且**策展器已经处理过该
会话。策展器尚未触及的会话永远不会被删除，无论多旧——否则记录会在还没从中学到任何
东西之前就被销毁。

可见的代价：`veles sessions search` 只能找到窗口之内的文本。`veles sessions list`
仍然会列出更早的运行，因为会话行（id、标题、时间戳）会保留，消失的只是消息正文。
清理发生在 `veles dream` 期间，位于洞察提取之后。

### 日志轮转

`traces.jsonl` 与 `events.jsonl` 在 50 MB 时轮转为 `<名称>.<unix_ts>`，并保留最近的
**10** 份，更早的会在下一次轮转时删除。此前它们会被永久保存。

在通常的用量下无需任何配置：每条 trace 记录约 530 字节，智能体每轮约 1.1 KB 事件，
距离第一次轮转还有数年。这个设置之所以存在，是因为没有策略的无限增长是一处泄漏，
最终得由接手这台机器的人去发现。

### 图片

发送到频道的照片会在这一轮开始之前先被描述，使用的是 `[routing.tasks].vision` 指向的
模型——若未显式配置路由，即你的 `[engine]` 模型。因此多模态引擎完全不需要配置。

`[vision] mode` 选择处理流程：

- `model`（默认）——由视觉模型描述图片。
- `ocr` —— 仅用 Tesseract。本地、免费、不调用 LLM；适合文字扫描件。
- `ocr+model` —— 先给出逐字文本，再给出模型的描述。
- `off` —— 什么都不读；文件仍会保存，智能体如果需要可以自行调用
  `image_describe` / `image_ocr`。

当引擎只支持文本时，请设置 `[vision] model`。任何具备视觉能力的提供商都可以，包括
本地服务器：`ollama:llava`、`llamacpp:…`、`openai-compat:…`。

### `project.toml`

`<project>/.veles/project.toml` 保存不可变的项目元数据（`name`、`created_at`、`schema_version`、`layout`）。通常不需要手动编辑。

---

## AGENTS.md

位于项目根目录的项目上下文文件。它在启动时注入到 agent 的系统 prompt 中，并被符号链接到 `CLAUDE.md` 和 `GEMINI.md`，这样在该目录中启动的 `claude` 或 `gemini` CLI 会拾取到相同的上下文。

保持它精简——辅助性的 `.md` 文件（例如 `wiki/INDEX.md`）会按需加载。用 `veles schema validate` 校验必需的章节。参见[layout 包与 LLM-Wiki](../explanation/layout-packs-and-llm-wiki.md)。

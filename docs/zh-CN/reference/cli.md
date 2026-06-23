# CLI 参考

> 🌐 **语言：** [English](../../en/reference/cli.md) · **简体中文** · [繁體中文](../../zh-TW/reference/cli.md) · [日本語](../../ja/reference/cli.md) · [한국어](../../ko/reference/cli.md) · [Español](../../es/reference/cli.md) · [Français](../../fr/reference/cli.md) · [Italiano](../../it/reference/cli.md) · [Português (BR)](../../pt-BR/reference/cli.md) · [Português (PT)](../../pt-PT/reference/cli.md) · [Русский](../../ru/reference/cli.md) · [العربية](../../ar/reference/cli.md) · [हिन्दी](../../hi/reference/cli.md) · [বাংলা](../../bn/reference/cli.md) · [Tiếng Việt](../../vi/reference/cli.md)

Veles 的所有命令、子命令和参数。运行 `veles <command> --help` 可获取最权威、始终保持最新的命令签名——本页镜像了 `src/veles/cli/_parsers/` 中的参数解析器。

```
veles [--no-wizard] <command> [subcommand] [options]
```

- `--no-wizard` — 即使 `~/.veles/config.toml` 缺失也跳过首次运行的设置向导（同样受 TTY 以及 `VELES_NO_WIZARD=1` 的约束）。
- 不带任何参数时，`veles` 会启动交互式 [TUI](tui.md)。

大多数 agent 命令都接受底部列出的[共享 agent-loop 参数](#shared-agent-loop-flags)和[提供方名称](#provider-names)。

---

## 项目生命周期

### `veles init [name]`
在当前目录创建一个新的 Veles 项目（一个 `.veles/` 状态目录 + `AGENTS.md` + 所选 layout 包的内容脚手架）。

| 参数 | 默认值 | 用途 |
|---|---|---|
| `name`（位置参数） | 当前目录名 | 项目名称 |
| `--layout <name>` | `llm-wiki` | 内容脚手架使用的 layout 包（`llm-wiki`、`notes`、`bare`，或来自 `~/.veles/layouts/` 的自定义包） |
| `--force` | 关闭 | 即使 `.veles/` 已存在也重新创建 |

### `veles schema {validate,edit,fix}`
校验或编辑 `AGENTS.md`（项目上下文文件）。

- `validate` — 检查是否包含必需的 H2 章节。
- `edit` — 在 `$EDITOR`（默认 `vi`）中打开 `AGENTS.md`，退出时进行校验。
- `fix` — 通过 LLM 向导交互式地补全缺失的章节。

### `veles self-doc [refresh|show]`
生成并显示项目自文档（`wiki/self-doc/overview.md`）。不带参数的 `veles self-doc` 显示当前页面；`refresh` 会重新生成它。

### `veles doctor`
对用户全局状态和当前活动项目运行健康检查。无论是否有活动项目都可用。

| 参数 | 默认值 | 用途 |
|---|---|---|
| `--json` | 关闭 | 输出 JSON 报告 |
| `--strict` | 关闭 | 任何警告都以非零状态退出（用于 CI 把关） |

### `veles export {full,template} <path>`
将项目打包为 `.tar.gz` 归档。参见[备份与分享](../how-to/backup-and-share.md)。

- `full <path>` — 整个项目（`.veles/` + `AGENTS.md`），不含运行时临时数据。
- `template <path>` — 经过清洗的子集（schema + skills + modules + 非 session 的 wiki 页面）；剥离 `memory.db`、`sources/`、`sessions/`、`trust` 授权，并对文本进行 PII 脱敏。

### `veles import <path>`
还原由 `veles export` 创建的归档。

| 参数 | 默认值 | 用途 |
|---|---|---|
| `path`（位置参数） | — | 归档路径（`.tar.gz`） |
| `--into <dir>` | 当前目录 | 目标目录 |
| `--force` | 关闭 | 覆盖目标位置已存在的 `.veles/` |

---

## 运行 agent

### `veles run "<prompt>"`
端到端运行单个 prompt，带记忆持久化以及 curator/学习触发器。接受所有[共享 agent-loop 参数](#shared-agent-loop-flags)，外加：

| 参数 | 默认值 | 用途 |
|---|---|---|
| `--resume <session_id>` | 新建 session | 继续一个已有的 session |
| `--manager` | 关闭 | 通过多 agent manager 进行任务分解（也可用 `VELES_MANAGER_MODE=1`） |
| `--verify` | 关闭 | 运行结束后，由路由到的 advisor 评判答案；当确信失败时，在更强的模型上重新运行（也可用 `VELES_VERIFY_MODE=1`） |
| `--plan` | 关闭 | 规划模式：允许读取/搜索/起草，禁止改动 |
| `--no-agents-md` | 关闭 | 不将 `AGENTS.md` 注入系统 prompt |
| `--no-index` | 关闭 | 不注入 `wiki/INDEX.md` |
| `--no-compress` | 关闭 | 禁用滑动窗口上下文压缩 |
| `--no-curator` | 关闭 | 本次运行禁用 curator 触发器 |
| `--no-insights` | 关闭 | 禁用运行后的 insight 提取 |
| `--no-proposer` | 关闭 | 禁用子项目 proposer 的自动触发 |
| `--no-route-refresh` | 关闭 | 禁用从 `AGENTS.md` 进行的 NL 路由刷新 |
| `--no-suggest-promote` | 关闭 | 禁用自动晋升建议器 |
| `--compressor-model <id>` | 路由决定 | 覆盖压缩模型 |
| `--compress-threshold-tokens <n>` | `50000` | 触发压缩的历史大小 |

### `veles tui`
打开交互式 REPL。参见 [TUI 参考](tui.md)。接受共享 agent-loop 参数、`--resume`、上述 `--no-*` 注入/压缩参数，以及：

| 参数 | 默认值 | 用途 |
|---|---|---|
| `--theme <name>` | 来自配置或 `everforest` | 配色主题（everforest、dracula、gruvbox、tokyo-night、catppuccin） |

### `veles add <source>`
读取一个来源（本地文件或 `http(s)://` URL）并将其综合成一个 wiki 页面。接受共享 agent-loop 参数。

### `veles curate`
运行一轮 curator：将未处理的 session 压缩为 `wiki/sessions/` 页面。

| 参数 | 默认值 | 用途 |
|---|---|---|
| `--limit <n>` | 一个较小的默认值 | 本次运行处理的最大 session 数 |

外加共享 agent-loop 参数。

### `veles research "<question>"`
深度研究：分解为子问题 → 并行检索网络 → 综合出带引用的报告。

| 参数 | 默认值 | 用途 |
|---|---|---|
| `--max-subquestions <n>` | `4` | 并行的研究角度数量 |

外加共享 agent-loop 参数。

### `veles dream`
运行一轮后台记忆巩固循环（insights → skill 去重 → 晋升建议 → wiki lint，可选 LLM 巩固）。

| 参数 | 默认值 | 用途 |
|---|---|---|
| `--include-consolidation` | 关闭 | 运行开销较大的 LLM 巩固（需要 API key） |
| `--dry-run` | 关闭 | 运行所有步骤但跳过 `wiki/state` 写入 |
| `--skip-insights` / `--skip-dedup` / `--skip-promote` / `--skip-lint` | 关闭 | 跳过单个步骤 |
| `--consolidation-model <id>` | 路由决定（回退到 `anthropic/claude-haiku-4.5`） | 覆盖巩固模型 |
| `--provider <name>` | 路由决定 | 巩固子 agent 使用的提供方（省略则使用项目路由的提供方） |
| `--project-root <path>` | 自动发现 | 覆盖项目位置 |

---

## 知识：skills、tools、modules

### `veles skill {list,show,add,remove,promote,demote,dedup,suggest-promote}`

| 子命令 | 用途 |
|---|---|
| `list` | 列出当前活动项目中的 skills（带遥测数据） |
| `show <name>` | 打印某个 skill 的 `SKILL.md` |
| `add <source> [--name N] [--scope project\|user] [-y]` | 从 git URL 或本地路径安装 |
| `remove <name> [--scope project\|user] [-y]` | 删除已安装的 skill |
| `promote <name> [--keep-telemetry]` | 将项目级 skill 复制到用户作用域（`~/.veles/skills/`） |
| `demote <name> [-y]` | 将用户级 skill 复制到当前活动项目 |
| `dedup [--mode auto\|embedding\|tfidf] [--embedding-threshold f] [--tfidf-threshold f]` | 查找近似重复的 skills |
| `suggest-promote [--save] [--min-uses n] [--min-success-rate f]` | 列出达到自动晋升门槛的 skills |

### `veles tool {list,show,promote}`

| 子命令 | 用途 |
|---|---|
| `list` | 列出本项目 `memory.db` 中编目的 tools |
| `show <name>` | 打印某个 tool 的清单 + 遥测数据 |
| `promote <name> [-y]` | 将项目级 tool 移动到 `~/.veles/tools/`（跨项目） |

### `veles module {list,show,add,remove}`

| 子命令 | 用途 |
|---|---|
| `list` | 列出已安装的 modules |
| `show <name>` | 打印某个 module 的清单 |
| `add <source> [--name N] [-y]` | 从 git URL 或本地路径安装 module |
| `remove <name> [-y]` | 删除已安装的 module |

### `veles browse {modules,skills} [query]`
浏览精选的注册表。

| 参数 | 默认值 | 用途 |
|---|---|---|
| `query`（位置参数） | `""` | 子串过滤 |
| `--source <url>` | 规范来源 | 覆盖注册表来源 |
| `--json` | 关闭 | 输出 JSON |

---

## Sessions 与记忆

### `veles sessions {list,show,delete,search}`

| 子命令 | 用途 |
|---|---|
| `list [--limit n]` | 列出最近的 sessions（默认 20 个） |
| `show <session_id>` | 打印某个 session 的完整回合历史 |
| `delete <session_id>` | 删除一个 session 及其回合 |
| `search "<query>" [--limit n] [--role user\|assistant\|both\|all] [--since 7d]` | 对回合内容进行全文（FTS5）搜索 |

---

## 多项目

### `veles project {list,add,remove,switch}`

| 子命令 | 用途 |
|---|---|
| `list` | 列出已注册的项目，最近的排在前面 |
| `add <path> [--slug S]` | 注册一个已有的项目目录 |
| `remove <slug>` | 取消注册某个项目（文件保持不变） |
| `switch <slug>` | 打印项目的绝对路径（用法：`cd $(veles project switch <slug>)`） |

### `veles subproject {init,list,switch,remove,suggest}`

| 子命令 | 用途 |
|---|---|
| `init <subdir> [--name N] [--description D]` | 创建并注册一个子项目 |
| `list` | 列出当前活动项目的子项目 |
| `switch <slug>` | 打印某个子项目的绝对路径 |
| `remove <slug>` | 取消注册某个子项目 |
| `suggest [--save] [--min-pages n] [--min-similarity f]` | 检测主题聚类并提议子项目 |

---

## 路由与模型

### `veles route {show,set,reset,refresh}`
按任务的集成路由——决定每种任务类型由哪个 `provider:model` 处理（`default`、`curator`、`compressor`、`insights`、`skills`、`advisor`、`vision`、`embedding`）。参见[按任务路由](../how-to/per-task-routing.md)。

| 子命令 | 用途 |
|---|---|
| `show` | 打印当前活动项目解析后的路由表 |
| `set <task> <provider:model>` | 将某个任务固定到指定规格 |
| `reset [task]` | 将一个任务（或全部）重置为默认值 |
| `refresh [--force]` | 重新解析 `AGENTS.md` 中的自然语言路由提示 |

### `veles models <provider>`
列出某个提供方的模型。云端提供方（openrouter/openai/gemini）缓存 24 小时；本地提供方始终实时获取。

| 参数 | 默认值 | 用途 |
|---|---|---|
| `provider`（位置参数） | — | [提供方名称](#provider-names)之一 |
| `--refresh` | 关闭 | 绕过磁盘缓存（仅云端） |
| `--json` | 关闭 | 以 JSON 形式输出 `{provider, source, models}` |

---

## 长时运行任务

### `veles goal {list,show,start,checkpoint,pause,resume,done,cancel}`
带预算和检查点的长周期目标。

| 子命令 | 用途 |
|---|---|
| `list [--status active\|paused\|completed\|blocked\|cancelled]` | 列出目标 |
| `show <id> [--json]` | 显示某个目标 |
| `start "<objective>" [--scope S] [--done-when D] [--max-steps n] [--max-cost-usd f] [--max-wall-time-s n] [--forbid A]… [--approve A]…` | 创建一个目标 |
| `checkpoint <id> "<note>" [--evidence U] [--cost-usd f] [--no-advance]` | 追加进展 |
| `pause <id>` / `resume <id>` | 暂停 / 恢复 |
| `done <id> [--evidence E]` / `cancel <id> [--reason R]` | 完成 / 取消 |

### `veles job {add,list,show,pause,resume,trigger,remove,history,tick}`
定时的 agent 任务。

| 子命令 | 用途 |
|---|---|
| `add --name N --schedule S --prompt P [--repeat n] [--context-from JOB_ID] [--deliver-to TARGET]` | 创建一个任务（schedule = cron、`<N><s\|m\|h\|d>` 或 ISO 时间戳） |
| `list [--json]` / `show <id>` | 检查任务 |
| `pause <id>` / `resume <id>` / `trigger <id>` / `remove <id>` | 生命周期管理 |
| `history <id> [--limit n]` | 最近的运行记录 |
| `tick` | 同步运行一次所有到期任务（无需 daemon；接受 agent-loop 参数） |

---

## 安全与访问控制

### `veles trust {list,set,revoke,clear}`
对敏感 tools（`run_shell`、`write_file`、`fetch_url`、…）的持久化授权。参见[安全](../how-to/security-and-permissions.md)。

| 子命令 | 用途 |
|---|---|
| `list` | 显示授权（用户 + 项目作用域） |
| `set <tool> [--scope project\|user]` | 授权某个 tool |
| `revoke <tool> [--scope project\|user\|both]` | 移除某项授权 |
| `clear [--scope project\|user\|all]` | 清除某个作用域内的全部授权 |

### `veles autopilot {enable,disable,status}`
一个限时窗口期，期间信任阶梯的提示会自动允许。

| 子命令 | 用途 |
|---|---|
| `enable --until <DUR>` | 开启一个窗口（`+30m`、`+2h`、`+1d` 或 ISO 格式 `2026-05-12T18:00:00Z`） |
| `disable` | 立即关闭窗口 |
| `status` | 报告 autopilot 是否处于活动状态 |

### `veles secret {set,get,list,delete}`
由操作系统钥匙串支持的密钥（API key、bot token）。

| 子命令 | 用途 |
|---|---|
| `set <name> [value]` | 存储（省略 value 则交互式 / 从 stdin 读取） |
| `get <name> [--reveal] [--no-env-fallback]` | 查询（默认回退到环境变量） |
| `list` | 显示已配置了哪些规范密钥 |
| `delete <name>` | 删除某个密钥 |

---

## Daemon 与 channels

### `veles daemon [start|stop|status|list|restart|delete|session|token]`
运行/控制 HTTP+WS daemon。不带子命令的 `veles daemon` 会打开 **daemon 选择器** TUI（项目 → daemons → channels）。参见[作为 daemon 运行](../how-to/run-as-daemon.md)。

| 子命令 | 用途 |
|---|---|
| `start [--host H] [--port P] [--foreground] [--name N]` | 启动一个 daemon（默认分离运行） |
| `stop [--name N]` / `status [--name N]` | 停止 / 检查 |
| `list` | 列出所有项目的 daemons |
| `restart [target] [--name N]` | 在相同 host/port 上停止并重新启动 |
| `delete <target> [-y]` | 停止并从注册表中移除 |
| `session create <name> [--host H] --port P [--model M] [--provider P] [--mode M]` | 声明一个具名 daemon session |
| `session list [--all]` / `session delete <name>` | 管理具名 sessions |
| `token add <name>` / `token list` / `token remove <name>` | Bearer-token 的增删查 |

`start` 同样接受共享 agent-loop 参数；对于 daemon，`--model` / `--provider` 默认取自项目配置，并在 daemon 的整个生命周期内固定不变。

### `veles channel {list,run,list-sessions,reset-session,add,remove}`
与 daemon 通信的外部聊天网关（Telegram 等）。参见[连接 Telegram](../how-to/connect-telegram.md)。

| 子命令 | 用途 |
|---|---|
| `list` | 列出已注册的 channel 平台 + session 计数 |
| `run --channel telegram [--bot-token T] [--daemon-url U] [--daemon-token T]` | 在前台启动一个网关 |
| `list-sessions [--channel C]` | 显示 `chat_id → session_id` 的映射 |
| `reset-session <chat_id> [--channel C]` | 遗忘某个映射（下一条消息将全新开始） |
| `add [--channel C] [--session S]` | 将某个 channel 绑定到 daemon（向导式；凭据 → 钥匙串） |
| `remove <channel> [--session S]` | 移除某个 channel 绑定 |

---

## MCP（外部 tool 服务器）

### `veles mcp {list,test}`
检查在 `[mcp.servers.*]` 下配置的外部 MCP 服务器。参见[外部 MCP 服务器](../how-to/external-mcp-servers.md)。

| 子命令 | 用途 |
|---|---|
| `list [--connect-timeout f]` | 显示已配置的服务器、连接状态、tool 数量 |
| `test <server>` | 连接某个服务器并列出其 tools |

---

## 共享 agent-loop 参数

`run`、`add`、`tui`、`curate`、`research`、`job tick` 和 `daemon start` 都接受：

| 参数 | 默认值 | 用途 |
|---|---|---|
| `--model <id>` | 从项目 `[provider]` 的 model 解析 → 用户 `default_model`（无硬编码默认值） | 模型 ID |
| `--provider <name>` | `openrouter` | 提供方（见下） |
| `--max-tokens-total <n>` | `100000` | 累计 token 预算；`0` 表示禁用 |
| `--max-iterations <n>` | `30` | 每个回合的最大 tool 调用迭代次数 |
| `--stream` | 关闭 | 逐 token 流式输出响应 |
| `--verbose` / `-v` | 关闭 | 将每回合进度输出到 stderr |
| `--project-root <path>` | 从当前目录自动发现 | 在其他位置的项目上操作 |

## 提供方名称

`openrouter`（默认） · `anthropic` · `openai` · `gemini` · `claude-cli` ·
`gemini-cli` · `ollama` · `llamacpp` · `openai-compat`

本地提供方（`ollama`、`llamacpp`、`openai-compat`）无需 API key。参见
[提供方参考](providers.md)和[配置提供方](../how-to/configure-providers.md)。

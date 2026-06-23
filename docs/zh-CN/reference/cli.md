# CLI 参考

> 🌐 **Languages:** **English** · [Русский](../../ru/reference/cli.md)

涵盖每一个 Veles 命令、子命令和标志。运行 `veles <command> --help` 可获取
权威且始终最新的签名 —— 本页镜像了 `src/veles/cli/_parsers/` 中的参数解析器。

```
veles [--no-wizard] <command> [subcommand] [options]
```

- `--no-wizard` —— 即使 `~/.veles/config.toml` 缺失也跳过首次运行的设置向导
  （同时还受 TTY 检测和 `VELES_NO_WIZARD=1` 的限制）。
- 不带任何参数时，`veles` 会启动交互式 [TUI](tui.md)。

大多数智能体命令都接受底部列出的[共享智能体循环标志](#shared-agent-loop-flags)
和[提供方名称](#provider-names)。

---

## 项目生命周期

### `veles init [name]`
在当前目录中创建一个新的 Veles 项目（一个 `.veles/` 状态目录
+ `AGENTS.md` + 所选布局包的内容脚手架）。

| 标志 | 默认值 | 用途 |
|---|---|---|
| `name`（位置参数） | cwd 的目录名 | 项目名称 |
| `--layout <name>` | `llm-wiki` | 用于内容脚手架的布局包（`llm-wiki`、`notes`、`bare`，或来自 `~/.veles/layouts/` 的自定义包） |
| `--force` | 关闭 | 即使 `.veles/` 已存在也重新创建 |

### `veles schema {validate,edit,fix}`
校验或编辑 `AGENTS.md`（项目上下文文件）。

- `validate` —— 检查必需的 H2 小节。
- `edit` —— 在 `$EDITOR`（默认 `vi`）中打开 `AGENTS.md`，退出时校验。
- `fix` —— 通过 LLM 向导交互式地补全缺失的小节。

### `veles self-doc [refresh|show]`
生成并显示项目自文档（`wiki/self-doc/overview.md`）。
单独的 `veles self-doc` 显示当前页面；`refresh` 重新生成它。

### `veles doctor`
对用户全局状态和激活项目运行健康检查。无论是否有激活项目都可使用。

| 标志 | 默认值 | 用途 |
|---|---|---|
| `--json` | 关闭 | 输出 JSON 报告 |
| `--strict` | 关闭 | 任何警告都以非零状态退出（用于 CI 门禁） |

### `veles export {full,template} <path>`
将项目打包成 `.tar.gz` 捆绑包。参见[备份与共享](../how-to/backup-and-share.md)。

- `full <path>` —— 整个项目（`.veles/` + `AGENTS.md`），不含运行时临时数据。
- `template <path>` —— 经过净化的子集（schema + 技能 + 模块 + 非会话
  wiki 页面）；会剥离 `memory.db`、`sources/`、`sessions/`、`trust` 授权，
  并对文本进行 PII 脱敏。

### `veles import <path>`
还原由 `veles export` 创建的捆绑包。

| 标志 | 默认值 | 用途 |
|---|---|---|
| `path`（位置参数） | — | 捆绑包路径（`.tar.gz`） |
| `--into <dir>` | cwd | 目标目录 |
| `--force` | 关闭 | 覆盖目标处已存在的 `.veles/` |

---

## 运行智能体

### `veles run "<prompt>"`
端到端地运行单个提示，带有内存持久化以及 curator/learning
触发器。接受所有[共享智能体循环标志](#shared-agent-loop-flags)，外加：

| 标志 | 默认值 | 用途 |
|---|---|---|
| `--resume <session_id>` | 新会话 | 继续一个已有会话 |
| `--manager` | 关闭 | 通过多智能体 manager 进行任务分解（也可用 `VELES_MANAGER_MODE=1`） |
| `--plan` | 关闭 | 规划模式：允许读取/搜索/起草，阻止变更操作 |
| `--no-agents-md` | 关闭 | 不将 `AGENTS.md` 注入系统提示 |
| `--no-index` | 关闭 | 不注入 `wiki/INDEX.md` |
| `--no-compress` | 关闭 | 禁用滑动窗口上下文压缩 |
| `--no-curator` | 关闭 | 本次运行禁用 curator 触发器 |
| `--no-insights` | 关闭 | 禁用运行后的洞见提取 |
| `--no-proposer` | 关闭 | 禁用子项目 proposer 的自动触发 |
| `--no-route-refresh` | 关闭 | 禁用从 `AGENTS.md` 刷新自然语言路由 |
| `--no-suggest-promote` | 关闭 | 禁用自动提升建议器 |
| `--compressor-model <id>` | 由路由决定 | 覆盖压缩模型 |
| `--compress-threshold-tokens <n>` | `50000` | 触发压缩的历史大小 |

### `veles tui`
打开交互式 REPL。参见 [TUI 参考](tui.md)。接受共享智能体循环标志、
`--resume`、上述 `--no-*` 注入/压缩标志，以及：

| 标志 | 默认值 | 用途 |
|---|---|---|
| `--theme <name>` | 配置或 `everforest` | 配色主题（everforest、dracula、gruvbox、tokyo-night、catppuccin） |

### `veles add <source>`
读取一个来源（本地文件或 `http(s)://` URL）并将其合成为一个 wiki
页面。接受共享智能体循环标志。

### `veles curate`
运行一轮 curator：将未处理的会话压缩进 `wiki/sessions/` 页面。

| 标志 | 默认值 | 用途 |
|---|---|---|
| `--limit <n>` | 一个较小的默认值 | 本次运行最多处理的会话数 |

外加共享智能体循环标志。

### `veles research "<question>"`
深度研究：分解为子问题 → 并行探索网络 →
合成一份带引用的报告。

| 标志 | 默认值 | 用途 |
|---|---|---|
| `--max-subquestions <n>` | `4` | 并行的研究角度数 |

外加共享智能体循环标志。

### `veles dream`
运行一轮后台内存整合周期（洞见 → 技能去重 → 提升
建议 → wiki lint，可选 LLM 整合）。

| 标志 | 默认值 | 用途 |
|---|---|---|
| `--include-consolidation` | 关闭 | 运行昂贵的 LLM 整合（需要 API 密钥） |
| `--dry-run` | 关闭 | 运行所有步骤但跳过 `wiki/state` 写入 |
| `--skip-insights` / `--skip-dedup` / `--skip-promote` / `--skip-lint` | 关闭 | 跳过单个步骤 |
| `--consolidation-model <id>` | `anthropic/claude-haiku-4.5` | 覆盖整合模型 |
| `--provider <name>` | `openrouter` | 整合子智能体的提供方 |
| `--project-root <path>` | 自动发现 | 覆盖项目 |

---

## 知识：技能、工具、模块

### `veles skill {list,show,add,remove,promote,demote,dedup,suggest-promote}`

| 子命令 | 用途 |
|---|---|
| `list` | 列出激活项目中的技能（带遥测数据） |
| `show <name>` | 打印某个技能的 `SKILL.md` |
| `add <source> [--name N] [--scope project\|user] [-y]` | 从 git URL 或本地路径安装 |
| `remove <name> [--scope project\|user] [-y]` | 删除一个已安装的技能 |
| `promote <name> [--keep-telemetry]` | 将项目技能复制到用户作用域（`~/.veles/skills/`） |
| `demote <name> [-y]` | 将用户技能复制进激活项目 |
| `dedup [--mode auto\|embedding\|tfidf] [--embedding-threshold f] [--tfidf-threshold f]` | 查找近似重复的技能 |
| `suggest-promote [--save] [--min-uses n] [--min-success-rate f]` | 列出达到自动提升标准的技能 |

### `veles tool {list,show,promote}`

| 子命令 | 用途 |
|---|---|
| `list` | 列出本项目 `memory.db` 中编目的工具 |
| `show <name>` | 打印某个工具的清单 + 遥测数据 |
| `promote <name> [-y]` | 将项目工具移动到 `~/.veles/tools/`（跨项目） |

### `veles module {list,show,add,remove}`

| 子命令 | 用途 |
|---|---|
| `list` | 列出已安装的模块 |
| `show <name>` | 打印某个模块的清单 |
| `add <source> [--name N] [-y]` | 从 git URL 或本地路径安装一个模块 |
| `remove <name> [-y]` | 删除一个已安装的模块 |

### `veles browse {modules,skills} [query]`
浏览经过策展的注册表。

| 标志 | 默认值 | 用途 |
|---|---|---|
| `query`（位置参数） | `""` | 子串过滤 |
| `--source <url>` | 规范源 | 覆盖注册表源 |
| `--json` | 关闭 | 输出 JSON |

---

## 会话与内存

### `veles sessions {list,show,delete,search}`

| 子命令 | 用途 |
|---|---|
| `list [--limit n]` | 列出最近的会话（默认 20 条） |
| `show <session_id>` | 打印某个会话的完整轮次历史 |
| `delete <session_id>` | 删除一个会话及其轮次 |
| `search "<query>" [--limit n] [--role user\|assistant\|both\|all] [--since 7d]` | 对轮次内容进行全文（FTS5）搜索 |

---

## 多项目

### `veles project {list,add,remove,switch}`

| 子命令 | 用途 |
|---|---|
| `list` | 列出已注册的项目，最近的在前 |
| `add <path> [--slug S]` | 注册一个已有的项目目录 |
| `remove <slug>` | 注销一个项目（文件不动） |
| `switch <slug>` | 打印项目的绝对路径（用 `cd $(veles project switch <slug>)`） |

### `veles subproject {init,list,switch,remove,suggest}`

| 子命令 | 用途 |
|---|---|
| `init <subdir> [--name N] [--description D]` | 创建并注册一个子项目 |
| `list` | 列出激活项目的子项目 |
| `switch <slug>` | 打印某个子项目的绝对路径 |
| `remove <slug>` | 注销一个子项目 |
| `suggest [--save] [--min-pages n] [--min-similarity f]` | 检测主题聚类并建议子项目 |

---

## 路由与模型

### `veles route {show,set,reset,refresh}`
按任务的集成路由 —— 哪个 `provider:model` 处理每种任务类型
（`default`、`curator`、`compressor`、`insights`、`skills`、`advisor`、`vision`、
`embedding`）。参见[按任务路由](../how-to/per-task-routing.md)。

| 子命令 | 用途 |
|---|---|
| `show` | 打印激活项目解析后的路由表 |
| `set <task> <provider:model>` | 将一个任务固定到某个规格 |
| `reset [task]` | 将一个任务（或全部）重置为默认值 |
| `refresh [--force]` | 重新解析 `AGENTS.md` 中的自然语言路由提示 |

### `veles models <provider>`
列出某个提供方的模型。云端提供方（openrouter/openai/gemini）缓存
24 小时；本地提供方始终为实时。

| 标志 | 默认值 | 用途 |
|---|---|---|
| `provider`（位置参数） | — | [提供方名称](#provider-names)之一 |
| `--refresh` | 关闭 | 绕过磁盘缓存（仅限云端） |
| `--json` | 关闭 | 以 JSON 形式输出 `{provider, source, models}` |

---

## 长时运行任务

### `veles goal {list,show,start,checkpoint,pause,resume,done,cancel}`
带预算和检查点的长周期目标。

| 子命令 | 用途 |
|---|---|
| `list [--status active\|paused\|completed\|blocked\|cancelled]` | 列出目标 |
| `show <id> [--json]` | 显示单个目标 |
| `start "<objective>" [--scope S] [--done-when D] [--max-steps n] [--max-cost-usd f] [--max-wall-time-s n] [--forbid A]… [--approve A]…` | 创建一个目标 |
| `checkpoint <id> "<note>" [--evidence U] [--cost-usd f] [--no-advance]` | 追加进度 |
| `pause <id>` / `resume <id>` | 暂停 / 恢复 |
| `done <id> [--evidence E]` / `cancel <id> [--reason R]` | 完成 / 取消 |

### `veles job {add,list,show,pause,resume,trigger,remove,history,tick}`
定时的智能体任务。

| 子命令 | 用途 |
|---|---|
| `add --name N --schedule S --prompt P [--repeat n] [--context-from JOB_ID] [--deliver-to TARGET]` | 创建一个任务（schedule = cron、`<N><s\|m\|h\|d>` 或 ISO 时间戳） |
| `list [--json]` / `show <id>` | 检视任务 |
| `pause <id>` / `resume <id>` / `trigger <id>` / `remove <id>` | 生命周期 |
| `history <id> [--limit n]` | 最近的运行 |
| `tick` | 同步地运行一次所有到期任务（无需守护进程；接受智能体循环标志） |

---

## 安全与访问控制

### `veles trust {list,set,revoke,clear}`
针对敏感工具（`run_shell`、`write_file`、`fetch_url` 等）的持久化授权。
参见[安全](../how-to/security-and-permissions.md)。

| 子命令 | 用途 |
|---|---|
| `list` | 显示授权（用户 + 项目作用域） |
| `set <tool> [--scope project\|user]` | 授权一个工具 |
| `revoke <tool> [--scope project\|user\|both]` | 移除一项授权 |
| `clear [--scope project\|user\|all]` | 清空某个作用域中的授权 |

### `veles autopilot {enable,disable,status}`
一个限时窗口，期间信任阶梯的提示会自动放行。

| 子命令 | 用途 |
|---|---|
| `enable --until <DUR>` | 开启一个窗口（`+30m`、`+2h`、`+1d`，或 ISO `2026-05-12T18:00:00Z`） |
| `disable` | 立即关闭窗口 |
| `status` | 报告自动驾驶是否处于激活状态 |

### `veles secret {set,get,list,delete}`
由操作系统钥匙串支持的密钥（API 密钥、机器人令牌）。

| 子命令 | 用途 |
|---|---|
| `set <name> [value]` | 存储（省略 value 以进行交互式 / stdin 输入） |
| `get <name> [--reveal] [--no-env-fallback]` | 查找（默认回退到环境变量） |
| `list` | 显示哪些规范密钥已配置 |
| `delete <name>` | 移除一个密钥 |

---

## 守护进程与频道

### `veles daemon [start|stop|status|list|restart|delete|session|token]`
运行/控制 HTTP+WS 守护进程。单独的 `veles daemon` 会打开**守护进程选择器**
TUI（项目 → 守护进程 → 频道）。参见[作为守护进程运行](../how-to/run-as-daemon.md)。

| 子命令 | 用途 |
|---|---|
| `start [--host H] [--port P] [--foreground] [--name N]` | 启动一个守护进程（默认分离运行） |
| `stop [--name N]` / `status [--name N]` | 停止 / 检视 |
| `list` | 列出所有项目中的守护进程 |
| `restart [target] [--name N]` | 停止并在相同 host/port 上重新启动 |
| `delete <target> [-y]` | 停止并从注册表中移除 |
| `session create <name> [--host H] --port P [--model M] [--provider P] [--mode M]` | 声明一个命名守护进程会话 |
| `session list [--all]` / `session delete <name>` | 管理命名会话 |
| `token add <name>` / `token list` / `token remove <name>` | bearer 令牌的增删查 |

`start` 同样接受共享智能体循环标志；对于守护进程，`--model` /
`--provider` 默认取自项目配置，并在守护进程的整个生命周期内固定不变。

### `veles channel {list,run,list-sessions,reset-session,add,remove}`
与守护进程通信的外部聊天网关（Telegram 等）。参见
[接入 Telegram](../how-to/connect-telegram.md)。

| 子命令 | 用途 |
|---|---|
| `list` | 列出已注册的频道平台 + 会话计数 |
| `run --channel telegram [--bot-token T] [--daemon-url U] [--daemon-token T]` | 在前台启动一个网关 |
| `list-sessions [--channel C]` | 显示 `chat_id → session_id` 映射 |
| `reset-session <chat_id> [--channel C]` | 忘记一个映射（下一条消息将重新开始） |
| `add [--channel C] [--session S]` | 将一个频道绑定到守护进程（向导；凭据 → 钥匙串） |
| `remove <channel> [--session S]` | 移除一个频道绑定 |

---

## MCP（外部工具服务器）

### `veles mcp {list,test}`
检视配置在 `[mcp.servers.*]` 下的外部 MCP 服务器。参见
[外部 MCP 服务器](../how-to/external-mcp-servers.md)。

| 子命令 | 用途 |
|---|---|
| `list [--connect-timeout f]` | 显示已配置的服务器、连接状态、工具数量 |
| `test <server>` | 连接到一个服务器并列出其工具 |

---

## 共享智能体循环标志

被 `run`、`add`、`tui`、`curate`、`research`、`job tick` 和 `daemon
start` 接受：

| 标志 | 默认值 | 用途 |
|---|---|---|
| `--model <id>` | `anthropic/claude-sonnet-4.6`（tui：持久化） | 模型 ID |
| `--provider <name>` | `openrouter` | 提供方（见下文） |
| `--max-tokens-total <n>` | `100000` | 累计 token 预算；`0` 表示禁用 |
| `--max-iterations <n>` | `30` | 每轮最多的工具调用迭代次数 |
| `--stream` | 关闭 | 逐 token 流式输出响应 |
| `--verbose` / `-v` | 关闭 | 将每轮进度输出到 stderr |
| `--project-root <path>` | 从 cwd 发现 | 操作位于别处的项目 |

## 提供方名称

`openrouter`（默认） · `anthropic` · `openai` · `gemini` · `claude-cli` ·
`gemini-cli` · `ollama` · `llamacpp` · `openai-compat`

本地提供方（`ollama`、`llamacpp`、`openai-compat`）无需 API 密钥。参见
[提供方参考](providers.md)和[配置提供方](../how-to/configure-providers.md)。

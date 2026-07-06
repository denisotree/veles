# Veles

[![CI](https://github.com/denisotree/veles/actions/workflows/ci.yml/badge.svg)](https://github.com/denisotree/veles/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/veles-ai.svg)](https://pypi.org/project/veles-ai/)
[![License: Apache-2.0](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)
[![Python 3.13+](https://img.shields.io/badge/python-3.13%2B-blue.svg)](pyproject.toml)

<p align="center">
  <a href="README.md">English</a> ·
  <b>简体中文</b> ·
  <a href="README.zh-TW.md">繁體中文</a> ·
  <a href="README.ja.md">日本語</a> ·
  <a href="README.ko.md">한국어</a> ·
  <a href="README.es.md">Español</a> ·
  <a href="README.fr.md">Français</a> ·
  <a href="README.it.md">Italiano</a> ·
  <a href="README.pt-BR.md">Português (BR)</a> ·
  <a href="README.pt-PT.md">Português (PT)</a> ·
  <a href="README.ru.md">Русский</a> ·
  <a href="README.ar.md">العربية</a> ·
  <a href="README.hi.md">हिन्दी</a> ·
  <a href="README.bn.md">বাংলা</a> ·
  <a href="README.vi.md">Tiếng Việt</a>
</p>

**一个极简的 CLI 智能体框架，每一次会话都让它变得更聪明。**

<p align="center">
  <img src="docs/assets/tui-hero.gif" alt="Veles REPL —— 提出问题，得到一个基于项目自身内存的答案" width="800">
</p>

与每次都从零开始的聊天工具不同，Veles 维护着**结构化的项目内存**——洞见、规则和经过整理的知识，它们会跨会话不断积累，让你用得越久，智能体越有用。你的*内容*如何组织是可插拔的：默认采用 Karpathy 风格的 LLM wiki，也可以用扁平笔记，或者对代码仓库完全不施加任何结构。代码构建干净：没有巨型文件，没有厂商锁定，没有云端同步。

```bash
uv tool install veles-ai          # installs the `veles` command
veles init && veles run "Summarize the project architecture."
veles        # interactive REPL (just run `veles` with no subcommand)
```

---

## 为什么选择 Veles？

**复利式内存**——每一次会话都会被 Curator 提炼成按项目划分的内存（洞见、行为规则、会话摘要，存放在 `.veles/` 中）。智能体会自动回忆起相关事实和过去的决策——你不必再反复解释相同的上下文。内存在*任何*内容布局下都能工作。

**可插拔的内容布局**——`veles init` 默认搭建一个 Karpathy 风格的 LLM wiki；`--layout notes` 给你一个扁平的笔记目录；`--layout bare` 则完全不添加任何结构（非常适合代码仓库）。自定义布局包只是 `~/.veles/layouts/` 下的一个 TOML 文件。

**与厂商无关的路由**——OpenRouter、Anthropic、OpenAI、Gemini、Ollama、llamacpp，或者你的 `claude`/`gemini` CLI 订阅。不同类型的任务（规划、压缩、洞见提取）可以路由到不同的模型。

**会积累的技能**——可复用的提示块会变成智能体工具。把一个技能从项目层级提升到用户全局层级，它就能在任何地方使用。内置去重功能会在技能彼此偏离之前找出近似重复的项。

**本地优先 + 沙箱化**——没有遥测，没有云端同步。智能体只能看到当前活动的项目目录。信任阶梯会对每一次敏感的工具调用进行提示；CI 场景可以预先授权。

**模块化，而非单体**——核心极小（内存、智能体循环、提供商协议、工具注册表）。其他一切——TUI、守护进程、Telegram 网关、深度研究、作业调度器——都是可选的、可加载的模块。

---

## 快速开始

**环境要求：** Python 3.13+，macOS / Linux（Windows 尽力支持）。请先安装 [uv](https://docs.astral.sh/uv/)。

```bash
# 1. Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# 2. Install veles (the package is published as `veles-ai`; the command is `veles`)
uv tool install veles-ai
# …or from source:
#   git clone https://github.com/denisotree/veles.git && cd veles && uv tool install .

# 3. Set an API key — OpenRouter is recommended (access to all models, one key)
export OPENROUTER_API_KEY=sk-or-v1-...

# 4. Create a project
mkdir my-project && cd my-project
veles init

# 5. Talk to the agent
veles run "Read AGENTS.md and describe this project."
```

或者打开交互式 REPL（直接运行 `veles` 效果相同）：

```bash
veles
```

首次运行时，设置向导会询问你偏好的语言、提供商以及项目名称。

---

## 提供商

| 提供商 | 环境变量 | 说明 |
|---|---|---|
| **OpenRouter** *（推荐）* | `OPENROUTER_API_KEY` | Claude、GPT、Gemini、Llama——一个密钥，数百个模型 |
| Anthropic | `ANTHROPIC_API_KEY` | 直连 API |
| OpenAI | `OPENAI_API_KEY` | 直连 API |
| Gemini | `GEMINI_API_KEY` 或 `GOOGLE_API_KEY` | 直连 API |
| `claude` CLI | — | 使用你的 Claude 订阅；无需 API 密钥 |
| `gemini` CLI | — | 使用你的 Gemini 订阅；无需 API 密钥 |
| Ollama | — | 本地模型，`http://localhost:11434/v1` |
| llamacpp | — | 本地模型，`http://localhost:8080/v1` |
| openai-compat | `OPENAI_COMPAT_BASE_URL` | 任何兼容 OpenAI 的端点 |

按单次运行覆盖：

```bash
veles run --provider anthropic --model anthropic/claude-opus-4-8 "..."
veles run --provider ollama --model llama3.2 "..."
```

将 API 密钥存入操作系统钥匙串，而不是环境变量：

```bash
veles secret set OPENROUTER_API_KEY    # prompts for value, stores in keychain
```

---

## 核心工作流

### 选择一种内容布局

```bash
veles init                  # default: Karpathy-style LLM wiki (sources/ + wiki/)
veles init --layout notes   # a single flat notes/ directory
veles init --layout bare    # no content scaffold — code repos, free-form work
```

智能体自身的内存（洞见、规则、会话摘要，存放在 `.veles/` 中）在每一种布局下的工作方式都完全相同。自定义布局包是 `~/.veles/layouts/<name>/` 下的一个 `layout.toml`。

### 构建知识库（llm-wiki 布局）

```bash
veles add paper.pdf                   # read a source → write a wiki page
veles add https://example.com/post    # web pages, PDFs, plain text

veles run "What do we know about the authentication design?"
veles curate                          # explicit session → memory consolidation
```

<p align="center">
  <img src="docs/assets/kb-ingest.gif" alt="Veles 知识库 —— 将一个来源摄取为一个 wiki 页面，然后提问并得到一个引用它的答案" width="800">
</p>

Curator 会在会话结束后自动运行。洞见提取会捕捉诸如「always prefer X」或「never do Y」之类的措辞，并将它们写为持久化的项目洞见。

### 深度研究

```bash
veles research "What are the trade-offs between SQLite and PostgreSQL for this use case?"
```

将问题分解为多个并行的子问题，逐一探索，然后综合成一份结构化的报告。

### 长期目标

```bash
veles goal start "Migrate auth module to the new provider" --max-cost-usd 2.00
veles goal list
veles goal checkpoint <id> "Completed step 1: identified all call sites"
```

### 计划作业

```bash
veles job add --name "weekly-review" --schedule "0 9 * * 1" --prompt "Generate a weekly progress summary"
veles job list
```

---

## 模型路由（集成）

将不同类型的任务路由到不同的模型——设置一次便可一劳永逸。

**通过 CLI：**
```bash
veles route show                                          # current routing table
veles route set compressor anthropic/claude-haiku-4-5    # typed override
veles route reset compressor                             # back to default
```

**通过 `AGENTS.md` 中的自然语言：**
```markdown
## Routing
Use Opus for planning and architecture decisions.
Haiku is fine for compression and insight extraction.
```

```bash
veles route refresh    # parse the NL hints; typed overrides always win
```

---

## 技能与模块

**技能**是可复用的提示块（`SKILL.md`），会自动变成智能体工具。

```bash
veles skill add https://github.com/org/skill-repo    # install from git
veles skill add ./local-skill-dir                    # or from local path
veles skill list                                     # list with telemetry
veles skill promote my-skill                         # copy to ~/.veles/skills (global)
veles skill dedup                                    # find near-duplicates
veles skill suggest-promote --save                   # propose promotions based on usage
```

**模块**是 Python 插件，可以挂入智能体生命周期（`pre_turn`、`post_turn`、`pre_tool_call`、`post_tool_call`），并否决工具调度。

```bash
veles module add https://github.com/org/module-repo
veles module list
```

---

## 交互式会话（REPL）

```bash
veles                        # new session (bare `veles` launches the interactive REPL)
veles -c                     # continue the most recent session in this project
veles --resume <id>          # resume a specific session
```

<p align="center">
  <img src="docs/assets/tui-tour.gif" alt="Veles REPL —— 斜杠检查器（/status、/context）、模式切换以及命令面板" width="800">
</p>

斜杠命令实时呈现一切——`/status`、`/tokens`、`/context`、`/mode`、`/help`——而 `Shift+Tab` 则在各模式之间循环（auto / planning / writing / goal）。

| 按键 | 操作 |
|---|---|
| `Enter` | 发送消息 |
| `Shift+Enter` | 在输入框中换行 |
| `Ctrl+I` | 切换工具活动检查器 |
| `Ctrl+R` | 会话选择器浮层 |
| `Ctrl+G` | 对当前草稿打开 `$EDITOR` |
| `Tab` | 斜杠命令自动补全 |
| `Ctrl+D` | 退出 |

斜杠命令：`/help` · `/model` · `/mode` · `/status` · `/tokens` · `/context` · `/wiki` · `/save <slug>` · `/history` · `/insights` · `/rules` · `/daemon` 等等。

---

## 守护进程 + Telegram

将 Veles 作为带有 HTTP/WebSocket API 的常驻守护进程运行。在一个全新的项目目录中，`veles daemon start` 会引导你完成设置——初始化项目、启用守护进程，并**连接一个通道**：先选择一种通道*类型*（如今 Telegram 是唯一的平台，但这个选择器正是新通道注册的接缝），然后填写该通道的字段（机器人令牌、白名单）。无需先打开 TUI。

<p align="center">
  <img src="docs/assets/daemon-setup.gif" alt="veles daemon start —— 启动守护进程并连接一个 Telegram 通道的向导（先选通道类型，再填它的令牌和白名单）" width="800">
</p>

```bash
veles daemon start                        # wizard (fresh dir) → starts on 127.0.0.1:8765
veles daemon status                       # is it running?
veles daemon list                         # daemons across all projects
```

直接运行 `veles daemon` 会打开一个实时控制面板——一棵 项目 → 守护进程 → 通道 的树。你可以启动、停止、重启或删除守护进程，并跨所有项目添加/移除通道（同样是先选通道类型的流程，按键 `c`），这一切都可以从键盘完成：

<p align="center">
  <img src="docs/assets/daemon-panel.gif" alt="veles daemon —— 控制面板 TUI：一棵 项目 → 守护进程 → 通道 的树，支持启动/停止/重启/删除以及内联的通道管理" width="800">
</p>

同样的通道向导也能在一个已经运行的项目上独立使用（`veles channel add`）。

API 端点：`POST /v1/runs` 提交一个提示，`WS /v1/runs/{id}/events` 流式接收响应，`GET /v1/sessions` 列出会话。除 `GET /v1/health` 外，所有端点都需要 `Authorization: Bearer <token>`（用 `veles daemon token add <name>` 生成一个）。

每个 Telegram 用户都会获得一个持久化会话。使用 `veles channel list-sessions` / `reset-session` 来管理映射关系。

---

## 多项目

```bash
veles project list                       # registered projects
veles project switch <slug>              # print the absolute path
cd $(veles project switch <slug>)        # jump to a project

veles subproject init frontend           # create a child project
veles subproject suggest --save          # agent-detected topic clusters → proposals
```

---

## 信任与安全

每一次敏感的工具调用（执行 shell、写入文件、抓取 URL）都会提示：

```
Tool 'run_shell' wants to execute. Allow?
  [1] Once  [2] Always for this project  [3] Always everywhere  [4] Refuse
```

为 CI 或长时间自主运行预先授权：

```bash
veles trust set run_shell --scope project   # pre-grant for this project
veles autopilot enable --until +2h          # temporary trust bypass (audit-logged)
veles autopilot disable
```

智能体只能看到当前活动的项目目录——其他项目、符号链接逃逸以及 `..` 遍历都会被阻止。

---

## 导出 / 导入

```bash
veles export full ./backup.tar.gz        # full backup: memory, sessions, telemetry
veles export template ./template.tar.gz  # sanitised template (no sources/sessions/PII)
veles import ./backup.tar.gz --into ./new-dir
```

---

## CLI 参考

| 命令 | 用途 |
|---|---|
| `veles init [name]` | 创建一个新项目 |
| `veles run "<prompt>"` | 单轮智能体运行 |
| `veles` | 交互式 REPL（无子命令） |
| `veles add <file\|url>` | 摄取一个来源 → wiki 页面 |
| `veles research "<question>"` | 多角度深度研究 |
| `veles curate` | 将会话整合进 wiki |
| `veles sessions {list,show,delete,search}` | 会话管理 |
| `veles skill {list,add,remove,promote,demote,dedup,suggest-promote}` | 技能管理 |
| `veles tool {list,show,promote}` | 工具管理 |
| `veles module {list,add,remove}` | 插件管理 |
| `veles route {show,set,reset,refresh}` | 模型路由 |
| `veles goal {list,show,start,checkpoint,pause,resume,done,cancel}` | 长周期目标 |
| `veles job {list,add,show,pause,resume,trigger,remove,history}` | 计划作业 |
| `veles dream` | 后台内存整合循环 |
| `veles project {list,add,remove,switch}` | 多项目注册表 |
| `veles subproject {init,list,switch,remove,suggest}` | 子项目 |
| `veles trust {list,set,revoke,clear}` | 信任授权 |
| `veles autopilot {enable,disable,status}` | 临时信任旁路 |
| `veles secret {set,get,list,delete}` | 操作系统钥匙串密钥 |
| `veles daemon {start,stop,status,list,restart,delete,session,token}` | HTTP/WS 守护进程 |
| `veles channel {run,list-sessions,reset-session}` | 外部通道网关 |
| `veles mcp {list,test}` | 外部 MCP 服务器 |
| `veles models <provider>` | 列出提供商的模型 |
| `veles doctor` | 健康检查 |
| `veles export / import` | 项目备份与迁移 |

每个命令都有 `--help`。

---

## 文档

完整文档——按 Diátaxis 组织（教程 · 操作指南 · 参考 · 解释）：

- **简体中文:** [`docs/zh-CN/index.md`](docs/zh-CN/index.md)

其他语言：使用任意文档页面顶部的 🌐 切换器。

---

## 参与贡献

我们非常欢迎贡献——Veles **生来就是为了被扩展的**。核心保持精简（智能体循环 + 项目内存 + 提供商协议）；几乎其他所有东西都是可插拔的扩展点，因此添加一项能力很少需要触碰核心：

- **提供商适配器**（`src/veles/adapters/`）——接入一个新的模型后端。
- **技能**——带有 `extends:` 继承的可复用提示块和工具，可从项目提升到用户全局。
- **工具**——智能体编写并复用的、带类型的 Python，位于 `<project>/.veles/tools/` 下。
- **布局包**——`~/.veles/layouts/<name>/` 下的单个 `layout.toml` 即可定义一整套内容布局。
- **模块钩子**——通过 `pre_turn` / `post_turn` 钩子实现可观测性、日志记录和策略（`src/veles/core/modules.py`）。
- **通道与 MCP 服务器**——新的网关和外部工具来源。
- **本地化**——`src/veles/locales/` 中的翻译。

```bash
git clone https://github.com/denisotree/veles.git && cd veles
uv sync                              # runtime + dev dependencies
uv run pytest                        # the full suite (3200+ tests, no network)
uv run ruff check src tests && uv run mypy
```

代码库是刻意拆分的——单一职责，没有巨型文件。在提交 PR 之前，请阅读 [`CONTRIBUTING.md`](CONTRIBUTING.md) 了解约定，并阅读 [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md)。适合上手的首批贡献：提供商适配器、工作流技能、模块钩子和本地化文件。

---

## 许可证

Apache 2.0，附带专利授权——参见 [`LICENSE`](LICENSE) 和 [`NOTICE`](NOTICE)。

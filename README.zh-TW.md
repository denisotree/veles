# Veles

[![CI](https://github.com/denisotree/veles/actions/workflows/ci.yml/badge.svg)](https://github.com/denisotree/veles/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/veles-ai.svg)](https://pypi.org/project/veles-ai/)
[![License: Apache-2.0](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)
[![Python 3.13+](https://img.shields.io/badge/python-3.13%2B-blue.svg)](pyproject.toml)

<p align="center">
  <a href="README.md">English</a> ·
  <a href="README.zh-CN.md">简体中文</a> ·
  <b>繁體中文</b> ·
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

**一個極簡的 CLI 代理框架，每次工作階段都讓它變得更聰明。**

<p align="center">
  <img src="docs/assets/tui-hero.gif" alt="Veles REPL — 提出一個問題，獲得一個立基於專案自身記憶的回答" width="800">
</p>

不同於每次都從零開始的聊天工具，Veles 維護著**結構化的專案記憶**——洞見、規則與精心整理的知識會跨工作階段不斷累積，讓代理使用得越久就越有用。你的*內容*如何組織是可插拔的：預設採用 Karpathy 風格的 LLM wiki、扁平筆記，或對於程式碼儲存庫完全不施加任何結構。架構乾淨：沒有巨型檔案、沒有供應商鎖定、沒有雲端同步。

```bash
uv tool install veles-ai          # installs the `veles` command
veles init && veles run "Summarize the project architecture."
veles        # interactive REPL (bare `veles` with no subcommand)
```

---

## 為什麼選擇 Veles？

**複利式記憶**——每次工作階段都會由策展器（Curator）提煉成各專案專屬的記憶（`.veles/` 中的洞見、行為規則、工作階段摘要）。代理會自動回想起相關的事實與過往的決策——你不必再重複解釋相同的脈絡。記憶在*任何*內容版面配置下都能運作。

**可插拔的內容版面配置**——`veles init` 預設建立 Karpathy 風格的 LLM wiki 鷹架；`--layout notes` 提供一個扁平的筆記目錄；`--layout bare` 完全不加任何結構（最適合程式碼儲存庫）。自訂版面配置套件就是 `~/.veles/layouts/` 中的單一 TOML 檔案。

**與供應商無關的路由**——OpenRouter、Anthropic、OpenAI、Gemini、Ollama、llamacpp，或你的 `claude`／`gemini` CLI 訂閱。不同的任務類型（規劃、壓縮、洞見）可以路由到不同的模型。

**會累積的技能**——可重複使用的提示區塊會變成代理工具。將一個技能從專案提升為使用者全域，它便可在任何地方使用。內建的去重功能能在技能彼此偏移之前找出近乎重複的技能。

**本地優先 + 沙箱化**——沒有遙測、沒有雲端同步。代理只看得到目前作用中的專案目錄。信任階梯會為每一次敏感工具呼叫提示確認；可為 CI 預先授權。

**模組化，而非單體式**——精簡的核心（記憶、代理迴圈、供應商協定、工具登錄）。其他所有東西——TUI、常駐程式、Telegram 閘道、深度研究、工作排程器——都是可選的、可載入的模組。

---

## 快速開始

**系統需求：** Python 3.13+，macOS／Linux（Windows 盡力支援）。請先安裝 [uv](https://docs.astral.sh/uv/)。

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

改為開啟互動式 REPL（直接執行 `veles` 效果相同）：

```bash
veles
```

第一次執行時，設定精靈會詢問你偏好的語言、供應商與專案名稱。

---

## 供應商

| 供應商 | 環境變數 | 備註 |
|---|---|---|
| **OpenRouter** *（推薦）* | `OPENROUTER_API_KEY` | Claude、GPT、Gemini、Llama——一把金鑰，數百個模型 |
| Anthropic | `ANTHROPIC_API_KEY` | 直連 API |
| OpenAI | `OPENAI_API_KEY` | 直連 API |
| Gemini | `GEMINI_API_KEY` 或 `GOOGLE_API_KEY` | 直連 API |
| `claude` CLI | — | 使用你的 Claude 訂閱；不需要 API 金鑰 |
| `gemini` CLI | — | 使用你的 Gemini 訂閱；不需要 API 金鑰 |
| Ollama | — | 本地模型，`http://localhost:11434/v1` |
| llamacpp | — | 本地模型，`http://localhost:8080/v1` |
| openai-compat | `OPENAI_COMPAT_BASE_URL` | 任何相容 OpenAI 的端點 |

按執行逐次覆寫：

```bash
veles run --provider anthropic --model anthropic/claude-opus-4-8 "..."
veles run --provider ollama --model llama3.2 "..."
```

將 API 金鑰存放在作業系統的金鑰圈（keychain）而非環境變數中：

```bash
veles secret set OPENROUTER_API_KEY    # prompts for value, stores in keychain
```

---

## 核心工作流程

### 選擇內容版面配置

```bash
veles init                  # default: Karpathy-style LLM wiki (sources/ + wiki/)
veles init --layout notes   # a single flat notes/ directory
veles init --layout bare    # no content scaffold — code repos, free-form work
```

代理自身的記憶（`.veles/` 中的洞見、規則、工作階段摘要）在每一種版面配置下運作方式都完全相同。自訂套件就是 `~/.veles/layouts/<name>/` 中的一個 `layout.toml`。

### 建立知識庫（llm-wiki 版面配置）

```bash
veles add paper.pdf                   # read a source → write a wiki page
veles add https://example.com/post    # web pages, PDFs, plain text

veles run "What do we know about the authentication design?"
veles curate                          # explicit session → memory consolidation
```

<p align="center">
  <img src="docs/assets/kb-ingest.gif" alt="Veles 知識庫 — 將一個來源攝取成 wiki 頁面，接著提出問題並獲得引用該來源的回答" width="800">
</p>

策展器會在工作階段結束後自動執行。洞見擷取會捕捉像「always prefer X」或「never do Y」這類語句，並將它們寫成持久的專案洞見。

### 深度研究

```bash
veles research "What are the trade-offs between SQLite and PostgreSQL for this use case?"
```

將問題分解成並行的子問題，逐一探索，並綜合出一份結構化的報告。

### 長時程目標

```bash
veles goal start "Migrate auth module to the new provider" --max-cost-usd 2.00
veles goal list
veles goal checkpoint <id> "Completed step 1: identified all call sites"
```

### 排程工作

```bash
veles job add --name "weekly-review" --schedule "0 9 * * 1" --prompt "Generate a weekly progress summary"
veles job list
```

---

## 模型路由（集成）

將不同的任務類型路由到不同的模型——設定一次便不再操心。

**透過 CLI：**
```bash
veles route show                                          # current routing table
veles route set compressor anthropic/claude-haiku-4-5    # typed override
veles route reset compressor                             # back to default
```

**透過 `AGENTS.md` 中的自然語言：**
```markdown
## Routing
Use Opus for planning and architecture decisions.
Haiku is fine for compression and insight extraction.
```

```bash
veles route refresh    # parse the NL hints; typed overrides always win
```

---

## 技能與模組

**技能（Skills）** 是可重複使用的提示區塊（`SKILL.md`），會自動變成代理工具。

```bash
veles skill add https://github.com/org/skill-repo    # install from git
veles skill add ./local-skill-dir                    # or from local path
veles skill list                                     # list with telemetry
veles skill promote my-skill                         # copy to ~/.veles/skills (global)
veles skill dedup                                    # find near-duplicates
veles skill suggest-promote --save                   # propose promotions based on usage
```

**模組（Modules）** 是 Python 外掛，可掛入代理生命週期（`pre_turn`、`post_turn`、`pre_tool_call`、`post_tool_call`）並否決工具的派發。

```bash
veles module add https://github.com/org/module-repo
veles module list
```

---

## 互動式工作階段（REPL）

```bash
veles                        # new session (bare `veles` launches the interactive REPL)
veles --resume <id>      # continue a session
```

<p align="center">
  <img src="docs/assets/tui-tour.gif" alt="Veles TUI — 斜線檢視器（/status、/context）、模式切換與命令面板" width="800">
</p>

斜線命令會即時呈現一切——`/status`、`/tokens`、`/context`、`/mode`、`/help`——而 `Shift+Tab` 會循環切換模式（auto／planning／writing／goal）。

| 按鍵 | 動作 |
|---|---|
| `Enter` | 送出訊息 |
| `Shift+Enter` | 在編輯器中換行 |
| `Ctrl+I` | 切換工具活動檢視器 |
| `Ctrl+R` | 工作階段挑選器疊層 |
| `Ctrl+G` | 對目前草稿開啟 `$EDITOR` |
| `Tab` | 斜線命令自動完成 |
| `Ctrl+D` | 退出 |

斜線命令：`/help` · `/model` · `/mode` · `/status` · `/tokens` · `/context` · `/wiki` · `/save <slug>` · `/history` · `/insights` · `/rules` · `/daemon` 以及更多。

---

## 常駐程式 + Telegram

以持久常駐程式（daemon）的形式執行 Veles，並提供 HTTP／WebSocket API。在一個全新的專案目錄中，`veles daemon start` 會帶你完成設定——初始化專案、啟用常駐程式，並**連接一個頻道**：首先選擇頻道*類型*（目前唯一的平台是 Telegram，但這個挑選器正是新頻道註冊的接縫），然後填入該頻道的欄位（bot token、白名單）。無須先開啟 TUI。

<p align="center">
  <img src="docs/assets/daemon-setup.gif" alt="veles daemon start — 啟動常駐程式並連接 Telegram 頻道的精靈（先選頻道類型，再填 token 與白名單）" width="800">
</p>

```bash
veles daemon start                        # wizard (fresh dir) → starts on 127.0.0.1:8765
veles daemon status                       # is it running?
veles daemon list                         # daemons across all projects
```

直接執行 `veles daemon` 會開啟一個即時控制面板——一棵「專案 → 常駐程式 → 頻道」的樹狀結構。你可以啟動、停止、重新啟動或刪除常駐程式，並跨每一個專案新增／移除頻道（同樣是先選頻道類型的流程，按鍵 `c`），全部都用鍵盤完成：

<p align="center">
  <img src="docs/assets/daemon-panel.gif" alt="veles daemon — 控制面板 TUI：一棵「專案 → 常駐程式 → 頻道」樹，附帶啟動／停止／重啟／刪除及內嵌頻道管理" width="800">
</p>

同樣的頻道精靈也可在一個已在執行的專案上獨立使用（`veles channel add`）。

API 端點：`POST /v1/runs` 提交提示、`WS /v1/runs/{id}/events` 串流回應、`GET /v1/sessions` 列出工作階段。除了 `GET /v1/health` 之外的所有端點都需要 `Authorization: Bearer <token>`（用 `veles daemon token add <name>` 鑄造一個）。

每位 Telegram 使用者都會獲得一個持久的工作階段。使用 `veles channel list-sessions`／`reset-session` 來管理對應關係。

---

## 多專案

```bash
veles project list                       # registered projects
veles project switch <slug>              # print the absolute path
cd $(veles project switch <slug>)        # jump to a project

veles subproject init frontend           # create a child project
veles subproject suggest --save          # agent-detected topic clusters → proposals
```

---

## 信任與安全

每一次敏感工具呼叫（shell 執行、檔案寫入、URL 擷取）都會提示：

```
Tool 'run_shell' wants to execute. Allow?
  [1] Once  [2] Always for this project  [3] Always everywhere  [4] Refuse
```

為 CI 或延伸的自主執行預先授權：

```bash
veles trust set run_shell --scope project   # pre-grant for this project
veles autopilot enable --until +2h          # temporary trust bypass (audit-logged)
veles autopilot disable
```

代理只看得到目前作用中的專案目錄——其他專案、符號連結逃逸與 `..` 路徑穿越都會被封鎖。

---

## 匯出／匯入

```bash
veles export full ./backup.tar.gz        # full backup: memory, sessions, telemetry
veles export template ./template.tar.gz  # sanitised template (no sources/sessions/PII)
veles import ./backup.tar.gz --into ./new-dir
```

---

## CLI 參考

| 命令 | 用途 |
|---|---|
| `veles init [name]` | 建立新專案 |
| `veles run "<prompt>"` | 單回合代理執行 |
| `veles` | 互動式 REPL |
| `veles add <file\|url>` | 攝取一個來源 → wiki 頁面 |
| `veles research "<question>"` | 深度多角度研究 |
| `veles curate` | 將工作階段整併進 wiki |
| `veles sessions {list,show,delete,search}` | 工作階段管理 |
| `veles skill {list,add,remove,promote,demote,dedup,suggest-promote}` | 技能管理 |
| `veles tool {list,show,promote}` | 工具管理 |
| `veles module {list,add,remove}` | 外掛管理 |
| `veles route {show,set,reset,refresh}` | 模型路由 |
| `veles goal {list,show,start,checkpoint,pause,resume,done,cancel}` | 長時程目標 |
| `veles job {list,add,show,pause,resume,trigger,remove,history}` | 排程工作 |
| `veles dream` | 背景記憶整併循環 |
| `veles project {list,add,remove,switch}` | 多專案登錄 |
| `veles subproject {init,list,switch,remove,suggest}` | 子專案 |
| `veles trust {list,set,revoke,clear}` | 信任授權 |
| `veles autopilot {enable,disable,status}` | 暫時性信任繞過 |
| `veles secret {set,get,list,delete}` | 作業系統金鑰圈祕密 |
| `veles daemon {start,stop,status,list,restart,delete,session,token}` | HTTP/WS 常駐程式 |
| `veles channel {run,list-sessions,reset-session}` | 外部頻道閘道 |
| `veles mcp {list,test}` | 外部 MCP 伺服器 |
| `veles models <provider>` | 列出供應商模型 |
| `veles doctor` | 健康檢查 |
| `veles export / import` | 專案備份與轉移 |

每個命令都有 `--help`。

---

## 文件

完整文件——以 Diátaxis 方式組織（教學 · 操作指南 · 參考 · 解說）：

- **繁體中文：** [`docs/zh-TW/index.md`](docs/zh-TW/index.md)

其他語言：使用任意文件頁面頂部的 🌐 切換器。

---

## 貢獻

非常歡迎貢獻——Veles **天生就是為了被擴充**而打造。核心保持精簡（代理迴圈 + 專案記憶 + 供應商協定）；幾乎其他所有東西都是可插拔的擴充點，因此新增一項能力鮮少需要動到核心：

- **供應商轉接器**（`src/veles/adapters/`）——接上一個新的模型後端。
- **技能**——具備 `extends:` 繼承的可重複使用提示區塊與工具，可從專案提升為使用者全域。
- **工具**——代理自行撰寫並重複使用的具型別 Python，位於 `<project>/.veles/tools/`。
- **版面配置套件**——`~/.veles/layouts/<name>/` 中的單一 `layout.toml` 即可定義一整套內容版面配置。
- **模組掛鉤**——透過 `pre_turn`／`post_turn` 掛鉤（`src/veles/core/modules.py`）實現可觀測性、記錄與政策。
- **頻道與 MCP 伺服器**——新的閘道與外部工具來源。
- **語系**——位於 `src/veles/locales/` 的翻譯。

```bash
git clone https://github.com/denisotree/veles.git && cd veles
uv sync                              # runtime + dev dependencies
uv run pytest                        # the full suite (3200+ tests, no network)
uv run ruff check src tests && uv run mypy
```

這份程式碼基底是刻意分解的——單一職責、沒有巨型檔案。在提出 PR 之前，請閱讀 [`CONTRIBUTING.md`](CONTRIBUTING.md) 了解慣例，以及 [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md)。適合入門的貢獻：供應商轉接器、工作流程技能、模組掛鉤，以及語系檔案。

---

## 授權

Apache 2.0 並附帶專利授權——詳見 [`LICENSE`](LICENSE) 與 [`NOTICE`](NOTICE)。

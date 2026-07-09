# 環境變數

> 🌐 **語言：** [English](../../en/reference/environment-variables.md) · [简体中文](../../zh-CN/reference/environment-variables.md) · **繁體中文** · [日本語](../../ja/reference/environment-variables.md) · [한국어](../../ko/reference/environment-variables.md) · [Español](../../es/reference/environment-variables.md) · [Français](../../fr/reference/environment-variables.md) · [Italiano](../../it/reference/environment-variables.md) · [Português (BR)](../../pt-BR/reference/environment-variables.md) · [Português (PT)](../../pt-PT/reference/environment-variables.md) · [Русский](../../ru/reference/environment-variables.md) · [العربية](../../ar/reference/environment-variables.md) · [हिन्दी](../../hi/reference/environment-variables.md) · [বাংলা](../../bn/reference/environment-variables.md) · [Tiếng Việt](../../vi/reference/environment-variables.md)

Veles 會在執行期讀取以下變數。API 金鑰與權杖最好存放在 OS 鑰匙圈中（`veles secret set …`）；環境變數是退路，也是覆寫的途徑。

## 供應商 API 金鑰

API 金鑰的查詢串接順序：OS 鑰匙圈（專案範圍）→ OS 鑰匙圈（預設範圍）→ 環境變數。

| 變數 | 供應商 | 備註 |
|---|---|---|
| `OPENROUTER_API_KEY` | openrouter | 預設供應商 |
| `ANTHROPIC_API_KEY` | anthropic | Anthropic 直連 API |
| `OPENAI_API_KEY` | openai | OpenAI 直連 API |
| `GEMINI_API_KEY` | gemini | Google Gemini 的主要金鑰 |
| `GOOGLE_API_KEY` | gemini | Google Gemini 的退路金鑰 |

`claude-cli` 與 `gemini-cli` 透過各自的執行檔進行驗證——不需環境變數。

## 本機供應商

| 變數 | 預設 | 用途 |
|---|---|---|
| `OLLAMA_BASE_URL` | `http://localhost:11434/v1` | Ollama 端點 |
| `OLLAMA_HOST` | 跟隨 `OLLAMA_BASE_URL` | 用於 embedding 的 Ollama 主機 |
| `LLAMACPP_BASE_URL` | `http://localhost:8080/v1` | llama.cpp 伺服器端點 |
| `OPENAI_COMPAT_BASE_URL` | —（必填） | `openai-compat` 供應商的端點 |
| `VELES_LOCAL_TOOLS` | 關閉 | 在本機供應商上啟用工具呼叫（`1`/`true`） |
| `VELES_OLLAMA_EMBED_MODEL` | 供應商預設 | 覆寫 Ollama 的 embedding 模型 |

## Channel 與 daemon

| 變數 | 預設 | 用途 |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | — | 供 `veles channel run --channel telegram` 使用的 Telegram 機器人權杖 |
| `VELES_DAEMON_URL` | `http://127.0.0.1:8765` | channel 閘道使用的 daemon 基底 URL |
| `VELES_DAEMON_TOKEN` | — | daemon 驗證用的 bearer 權杖 |

## 路徑與語系

| 變數 | 預設 | 用途 |
|---|---|---|
| `VELES_USER_HOME` | `~` | 覆寫存放 `~/.veles/`（狀態、快取、鑰匙圈索引）的家目錄 |
| `VELES_REGISTRY_PATH` | `~/.veles/…` | 覆寫多專案登錄庫路徑 |
| `VELES_LOCALE` | `[user] language` 或 `en` | 為單次執行覆寫作用中的 UI 語系 |
| `VELES_LOG_LEVEL` | `INFO` | daemon／log 的詳盡程度（`DEBUG`/`INFO`/`WARNING`/`ERROR`） |

## 行為與功能旗標

| 變數 | 預設 | 用途 |
|---|---|---|
| `VELES_NO_WIZARD` | 關閉 | 跳過首次執行精靈（同時也需 TTY） |
| `VELES_MANAGER_MODE` | 關閉 | 為 `veles run` 強制啟用多代理 manager（`1` 開啟／`0` 終止開關） |
| `VELES_VERIFY_MODE` | 關閉 | 為 `veles run` 強制啟用 verify→升級流程（`1` 開啟／`0` 終止開關） |
| `VELES_FENCED_TOOLS` | 關閉 | 在隔離／沙箱化的執行路徑中執行工具 |
| `VELES_TRUST_AUTO_ALLOW` | 關閉 | 繞過信任階梯（CI／autopilot／已預先授權的子代理） |
| `VELES_SANDBOX_ROOTS` | 專案 ＋ `~/.veles` | 以 `:` 分隔的讀寫沙箱根目錄覆寫 |
| `VELES_FETCH_ALLOW_PRIVATE` | 關閉 | 允許工具抓取 RFC-1918／私有位址 |
| `VELES_MEMORY_RERANK` | 開啟 | 對記憶召回做向量重排序（`0`/`false` 停用） |
| `VELES_WEB_SEARCH_BACKEND` | 自動 | `research` 與 `web_search` 的網路搜尋後端 |

## 登錄庫

| 變數 | 用途 |
|---|---|
| `VELES_SKILLS_REGISTRY_URL` | `veles browse skills` 的來源 |
| `VELES_MODULES_REGISTRY_URL` | `veles browse modules` 的來源 |

## 內部／測試

| 變數 | 用途 |
|---|---|
| `VELES_BUNDLE_VERSION` | 內部用途；你不應需要設定它 |
| `VELES_REPL_SIMPLE` | 設為 `1` 可強制使用純以行為單位的 REPL 迴圈，取代全螢幕的 `prompt_toolkit` 應用（為受限終端機提供的退路） |

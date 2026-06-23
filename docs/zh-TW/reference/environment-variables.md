# 環境變數

> 🌐 **語言：** **English** · [Русский](../../ru/reference/environment-variables.md)

Veles 會在執行期讀取這些變數。API 金鑰與 token 最好存放在作業系統的
keychain 中（`veles secret set …`）；環境變數則是退路與覆寫手段。

## Provider API 金鑰

API 金鑰查找串接順序：OS keychain（專案範圍）→ OS keychain（預設範圍）
→ 環境變數。

| Variable | Provider | Notes |
|---|---|---|
| `OPENROUTER_API_KEY` | openrouter | 預設 provider |
| `ANTHROPIC_API_KEY` | anthropic | 直連 Anthropic API |
| `OPENAI_API_KEY` | openai | 直連 OpenAI API |
| `GEMINI_API_KEY` | gemini | Google Gemini 的主要金鑰 |
| `GOOGLE_API_KEY` | gemini | Google Gemini 的備用金鑰 |

`claude-cli` 與 `gemini-cli` 透過各自的執行檔進行驗證——不需環境變數。

## 本機 provider

| Variable | Default | Purpose |
|---|---|---|
| `OLLAMA_BASE_URL` | `http://localhost:11434/v1` | Ollama 端點 |
| `OLLAMA_HOST` | follows `OLLAMA_BASE_URL` | 用於 embeddings 的 Ollama 主機 |
| `LLAMACPP_BASE_URL` | `http://localhost:8080/v1` | llama.cpp 伺服器端點 |
| `OPENAI_COMPAT_BASE_URL` | — (required) | `openai-compat` provider 的端點 |
| `VELES_LOCAL_TOOLS` | off | 在本機 provider 上啟用 tool calling（`1`/`true`） |
| `VELES_OLLAMA_EMBED_MODEL` | provider default | 覆寫 Ollama 的 embedding 模型 |

## Channels 與 daemon

| Variable | Default | Purpose |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | — | 供 `veles channel run --channel telegram` 使用的 Telegram bot token |
| `VELES_DAEMON_URL` | `http://127.0.0.1:8765` | channel gateway 所用的 daemon 基礎 URL |
| `VELES_DAEMON_TOKEN` | — | daemon 驗證用的 bearer token |

## 路徑與 locale

| Variable | Default | Purpose |
|---|---|---|
| `VELES_USER_HOME` | `~` | 覆寫存放 `~/.veles/` 的家目錄（狀態、快取、keychain 索引） |
| `VELES_HOME` | — | `VELES_USER_HOME` 的舊式別名 |
| `VELES_REGISTRY_PATH` | `~/.veles/…` | 覆寫多專案 registry 路徑 |
| `VELES_LOCALE` | `[user] language` or `en` | 為單次執行覆寫使用中的 UI locale |
| `VELES_LOG_LEVEL` | `INFO` | daemon／日誌詳細度（`DEBUG`/`INFO`/`WARNING`/`ERROR`） |
| `VELES_CONFIG_FILENAME` | `config.toml` | 覆寫設定檔名（測試用） |

## 行為與功能旗標

| Variable | Default | Purpose |
|---|---|---|
| `VELES_NO_WIZARD` | off | 跳過首次執行精靈（同時需要 TTY） |
| `VELES_MANAGER_MODE` | off | 為 `veles run` 強制使用 multi-agent manager（`1` 開啟／`0` 終止開關） |
| `VELES_FENCED_TOOLS` | off | 在 fenced／沙箱化的執行路徑中執行 tools |
| `VELES_TRUST_AUTO_ALLOW` | off | 略過 trust ladder（CI／autopilot／已預先授權的 sub-agent） |
| `VELES_SANDBOX_ROOTS` | project + `~/.veles` | 以 `:` 分隔，覆寫讀／寫沙箱的根目錄 |
| `VELES_FETCH_ALLOW_PRIVATE` | off | 允許 tools 抓取 RFC-1918／私有位址 |
| `VELES_MEMORY_RERANK` | on | 對記憶 recall 進行向量重排（`0`/`false` 表停用） |
| `VELES_WEB_SEARCH_BACKEND` | auto | `research` 與 `web_search` 所用的網路搜尋後端 |

## Registries

| Variable | Purpose |
|---|---|
| `VELES_SKILLS_REGISTRY_URL` | `veles browse skills` 的來源 |
| `VELES_MODULES_REGISTRY_URL` | `veles browse modules` 的來源 |

## 內部／測試

`VELES_BUNDLE_VERSION`、`VELES_CACHE_BREAKPOINT` — 內部使用；你不應需要
設定這些。

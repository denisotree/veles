# 环境变量

> 🌐 **语言：** [English](../../en/reference/environment-variables.md) · **简体中文** · [繁體中文](../../zh-TW/reference/environment-variables.md) · [日本語](../../ja/reference/environment-variables.md) · [한국어](../../ko/reference/environment-variables.md) · [Español](../../es/reference/environment-variables.md) · [Français](../../fr/reference/environment-variables.md) · [Italiano](../../it/reference/environment-variables.md) · [Português (BR)](../../pt-BR/reference/environment-variables.md) · [Português (PT)](../../pt-PT/reference/environment-variables.md) · [Русский](../../ru/reference/environment-variables.md) · [العربية](../../ar/reference/environment-variables.md) · [हिन्दी](../../hi/reference/environment-variables.md) · [বাংলা](../../bn/reference/environment-variables.md) · [Tiếng Việt](../../vi/reference/environment-variables.md)

Veles 在运行时读取这些变量。API key 和 token 最好存放在操作系统钥匙串中（`veles secret set …`）；环境变量作为回退和覆盖手段。

## 提供方 API key

API key 的查找级联：操作系统钥匙串（项目作用域）→ 操作系统钥匙串（默认作用域）→ 环境变量。

| 变量 | 提供方 | 备注 |
|---|---|---|
| `OPENROUTER_API_KEY` | openrouter | 默认提供方 |
| `ANTHROPIC_API_KEY` | anthropic | Anthropic 直连 API |
| `OPENAI_API_KEY` | openai | OpenAI 直连 API |
| `GEMINI_API_KEY` | gemini | Google Gemini 的主 key |
| `GOOGLE_API_KEY` | gemini | Google Gemini 的回退 key |

`claude-cli` 和 `gemini-cli` 通过各自的二进制程序进行认证——无需环境变量。

## 本地提供方

| 变量 | 默认值 | 用途 |
|---|---|---|
| `OLLAMA_BASE_URL` | `http://localhost:11434/v1` | Ollama 端点 |
| `OLLAMA_HOST` | 跟随 `OLLAMA_BASE_URL` | 用于 embeddings 的 Ollama 主机 |
| `LLAMACPP_BASE_URL` | `http://localhost:8080/v1` | llama.cpp 服务器端点 |
| `OPENAI_COMPAT_BASE_URL` | —（必填） | `openai-compat` 提供方的端点 |
| `VELES_LOCAL_TOOLS` | 关闭 | 在本地提供方上启用 tool 调用（`1`/`true`） |
| `VELES_OLLAMA_EMBED_MODEL` | 提供方默认值 | 覆盖 Ollama 的 embedding 模型 |

## Channels 与 daemon

| 变量 | 默认值 | 用途 |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | — | `veles channel run --channel telegram` 使用的 Telegram bot token |
| `VELES_DAEMON_URL` | `http://127.0.0.1:8765` | channel 网关使用的 daemon 基础 URL |
| `VELES_DAEMON_TOKEN` | — | daemon 认证用的 bearer token |

## 路径与本地化

| 变量 | 默认值 | 用途 |
|---|---|---|
| `VELES_USER_HOME` | `~` | 覆盖存放 `~/.veles/`（状态、缓存、钥匙串索引）的 home 目录 |
| `VELES_REGISTRY_PATH` | `~/.veles/…` | 覆盖多项目注册表路径 |
| `VELES_LOCALE` | `[user] language` 或 `en` | 为单次运行覆盖当前 UI 语言 |
| `VELES_LOG_LEVEL` | `INFO` | Daemon/日志详细级别（`DEBUG`/`INFO`/`WARNING`/`ERROR`） |

## 行为与功能开关

| 变量 | 默认值 | 用途 |
|---|---|---|
| `VELES_NO_WIZARD` | 关闭 | 跳过首次运行的向导（同样需要 TTY） |
| `VELES_MANAGER_MODE` | 关闭 | 为 `veles run` 强制启用多 agent manager（`1` 开启 / `0` 强制关闭） |
| `VELES_VERIFY_MODE` | 关闭 | 为 `veles run` 强制启用验证→升级流程（`1` 开启 / `0` 强制关闭） |
| `VELES_FENCED_TOOLS` | 关闭 | 在受隔离/沙箱化的执行路径中运行 tools |
| `VELES_TRUST_AUTO_ALLOW` | 关闭 | 绕过信任阶梯（CI / autopilot / 已预授权的子 agent） |
| `VELES_SANDBOX_ROOTS` | 项目 + `~/.veles` | 以 `:` 分隔的读写沙箱根目录覆盖 |
| `VELES_FETCH_ALLOW_PRIVATE` | 关闭 | 允许 tools 获取 RFC-1918 / 私有地址 |
| `VELES_MEMORY_RERANK` | 开启 | 对记忆召回进行向量重排序（`0`/`false` 禁用） |
| `VELES_WEB_SEARCH_BACKEND` | auto | `research` 和 `web_search` 使用的网络搜索后端 |

## 注册表

| 变量 | 用途 |
|---|---|
| `VELES_SKILLS_REGISTRY_URL` | `veles browse skills` 的来源 |
| `VELES_MODULES_REGISTRY_URL` | `veles browse modules` 的来源 |

## 内部 / 测试

| 变量 | 用途 |
|---|---|
| `VELES_BUNDLE_VERSION` | 内部使用；你应该不需要设置它 |
| `VELES_REPL_SIMPLE` | 设为 `1` 可强制使用基于行的简易 REPL 循环，而非全屏的 `prompt_toolkit` 应用（受限终端的回退方案） |

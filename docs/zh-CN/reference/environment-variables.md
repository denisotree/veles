# 环境变量

> 🌐 **Languages:** [English](../../en/reference/environment-variables.md) · [Русский](../../ru/reference/environment-variables.md) · **简体中文**

Veles 在运行时读取这些变量。API 密钥和令牌最好存储在操作系统的钥匙串中
（`veles secret set …`）；环境变量是回退方案，也是覆盖手段。

## 提供商 API 密钥

API 密钥查找的级联顺序：操作系统钥匙串（项目作用域）→ 操作系统钥匙串（默认作用域）
→ 环境变量。

| 变量 | 提供商 | 说明 |
|---|---|---|
| `OPENROUTER_API_KEY` | openrouter | 默认提供商 |
| `ANTHROPIC_API_KEY` | anthropic | 直连 Anthropic API |
| `OPENAI_API_KEY` | openai | 直连 OpenAI API |
| `GEMINI_API_KEY` | gemini | Google Gemini 的主密钥 |
| `GOOGLE_API_KEY` | gemini | Google Gemini 的回退密钥 |

`claude-cli` 和 `gemini-cli` 通过各自的二进制文件进行认证——无需环境变量。

## 本地提供商

| 变量 | 默认值 | 用途 |
|---|---|---|
| `OLLAMA_BASE_URL` | `http://localhost:11434/v1` | Ollama 端点 |
| `OLLAMA_HOST` | 跟随 `OLLAMA_BASE_URL` | 用于嵌入向量的 Ollama 主机 |
| `LLAMACPP_BASE_URL` | `http://localhost:8080/v1` | llama.cpp 服务器端点 |
| `OPENAI_COMPAT_BASE_URL` | —（必填） | `openai-compat` 提供商的端点 |
| `VELES_LOCAL_TOOLS` | 关闭 | 在本地提供商上启用工具调用（`1`/`true`） |
| `VELES_OLLAMA_EMBED_MODEL` | 提供商默认值 | 覆盖 Ollama 嵌入模型 |

## 通道与守护进程

| 变量 | 默认值 | 用途 |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | — | 供 `veles channel run --channel telegram` 使用的 Telegram 机器人令牌 |
| `VELES_DAEMON_URL` | `http://127.0.0.1:8765` | 通道网关使用的守护进程基础 URL |
| `VELES_DAEMON_TOKEN` | — | 守护进程认证使用的 Bearer 令牌 |

## 路径与语言环境

| 变量 | 默认值 | 用途 |
|---|---|---|
| `VELES_USER_HOME` | `~` | 覆盖存放 `~/.veles/`（状态、缓存、钥匙串索引）的主目录 |
| `VELES_HOME` | — | `VELES_USER_HOME` 的旧别名 |
| `VELES_REGISTRY_PATH` | `~/.veles/…` | 覆盖多项目注册表路径 |
| `VELES_LOCALE` | `[user] language` 或 `en` | 为单次运行覆盖当前 UI 语言环境 |
| `VELES_LOG_LEVEL` | `INFO` | 守护进程/日志详细程度（`DEBUG`/`INFO`/`WARNING`/`ERROR`） |
| `VELES_CONFIG_FILENAME` | `config.toml` | 覆盖配置文件名（测试用） |

## 行为与功能开关

| 变量 | 默认值 | 用途 |
|---|---|---|
| `VELES_NO_WIZARD` | 关闭 | 跳过首次运行向导（同时需要 TTY） |
| `VELES_MANAGER_MODE` | 关闭 | 为 `veles run` 强制启用多智能体管理器（`1` 开启 / `0` 紧急关闭） |
| `VELES_FENCED_TOOLS` | 关闭 | 在隔离/沙箱执行路径中运行工具 |
| `VELES_TRUST_AUTO_ALLOW` | 关闭 | 绕过信任阶梯（CI / 自动驾驶 / 预授权子智能体） |
| `VELES_SANDBOX_ROOTS` | 项目 + `~/.veles` | 以 `:` 分隔的读写沙箱根目录覆盖 |
| `VELES_FETCH_ALLOW_PRIVATE` | 关闭 | 允许工具获取 RFC-1918 / 私有地址 |
| `VELES_MEMORY_RERANK` | 开启 | 对记忆召回进行向量重排序（`0`/`false` 可禁用） |
| `VELES_WEB_SEARCH_BACKEND` | auto | 供 `research` 和 `web_search` 使用的网页搜索后端 |

## 注册表

| 变量 | 用途 |
|---|---|
| `VELES_SKILLS_REGISTRY_URL` | `veles browse skills` 的来源 |
| `VELES_MODULES_REGISTRY_URL` | `veles browse modules` 的来源 |

## 内部 / 测试

`VELES_BUNDLE_VERSION`、`VELES_CACHE_BREAKPOINT`——内部使用；你应该不需要
设置这些。

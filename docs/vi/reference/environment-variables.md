# Biến môi trường

> 🌐 **Ngôn ngữ:** [English](../../en/reference/environment-variables.md) · **Tiếng Việt**

Veles đọc các biến này trong thời gian chạy. API key và token nên được lưu trong
keychain của hệ điều hành (`veles secret set …`); biến môi trường là phương án dự
phòng và để ghi đè.

## API key của provider

Thứ tự tra cứu API key: keychain hệ điều hành (phạm vi dự án) → keychain hệ điều hành
(phạm vi mặc định) → biến môi trường.

| Biến | Provider | Ghi chú |
|---|---|---|
| `OPENROUTER_API_KEY` | openrouter | Provider mặc định |
| `ANTHROPIC_API_KEY` | anthropic | API Anthropic trực tiếp |
| `OPENAI_API_KEY` | openai | API OpenAI trực tiếp |
| `GEMINI_API_KEY` | gemini | Khóa chính cho Google Gemini |
| `GOOGLE_API_KEY` | gemini | Khóa dự phòng cho Google Gemini |

`claude-cli` và `gemini-cli` xác thực thông qua binary riêng của chúng — không cần biến môi trường.

## Provider cục bộ

| Biến | Mặc định | Mục đích |
|---|---|---|
| `OLLAMA_BASE_URL` | `http://localhost:11434/v1` | Endpoint Ollama |
| `OLLAMA_HOST` | follows `OLLAMA_BASE_URL` | Host Ollama cho embedding |
| `LLAMACPP_BASE_URL` | `http://localhost:8080/v1` | Endpoint máy chủ llama.cpp |
| `OPENAI_COMPAT_BASE_URL` | — (required) | Endpoint cho provider `openai-compat` |
| `VELES_LOCAL_TOOLS` | off | Bật tool calling trên các provider cục bộ (`1`/`true`) |
| `VELES_OLLAMA_EMBED_MODEL` | provider default | Ghi đè model embedding của Ollama |

## Kênh & daemon

| Biến | Mặc định | Mục đích |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | — | Bot token Telegram cho `veles channel run --channel telegram` |
| `VELES_DAEMON_URL` | `http://127.0.0.1:8765` | URL gốc của daemon, dùng bởi các gateway kênh |
| `VELES_DAEMON_TOKEN` | — | Bearer token để xác thực daemon |

## Đường dẫn & locale

| Biến | Mặc định | Mục đích |
|---|---|---|
| `VELES_USER_HOME` | `~` | Ghi đè thư mục home chứa `~/.veles/` (trạng thái, cache, chỉ mục keychain) |
| `VELES_HOME` | — | Bí danh cũ của `VELES_USER_HOME` |
| `VELES_REGISTRY_PATH` | `~/.veles/…` | Ghi đè đường dẫn registry đa dự án |
| `VELES_LOCALE` | `[user] language` or `en` | Ghi đè locale giao diện đang hoạt động cho một lần chạy |
| `VELES_LOG_LEVEL` | `INFO` | Mức độ chi tiết của daemon/log (`DEBUG`/`INFO`/`WARNING`/`ERROR`) |
| `VELES_CONFIG_FILENAME` | `config.toml` | Ghi đè tên tệp cấu hình (dùng cho kiểm thử) |

## Cờ hành vi & tính năng

| Biến | Mặc định | Mục đích |
|---|---|---|
| `VELES_NO_WIZARD` | off | Bỏ qua wizard chạy lần đầu (cũng cần một TTY) |
| `VELES_MANAGER_MODE` | off | Buộc dùng manager đa agent cho `veles run` (`1` bật / `0` công tắc tắt) |
| `VELES_FENCED_TOOLS` | off | Chạy công cụ theo đường thực thi fenced/sandbox |
| `VELES_TRUST_AUTO_ALLOW` | off | Bỏ qua thang trust (CI / autopilot / sub-agent đã được cấp quyền trước) |
| `VELES_SANDBOX_ROOTS` | project + `~/.veles` | Ghi đè (ngăn cách bằng `:`) các root sandbox đọc/ghi |
| `VELES_FETCH_ALLOW_PRIVATE` | off | Cho phép công cụ tải các địa chỉ RFC-1918 / riêng tư |
| `VELES_MEMORY_RERANK` | on | Rerank bằng vector cho việc recall bộ nhớ (`0`/`false` để tắt) |
| `VELES_WEB_SEARCH_BACKEND` | auto | Backend tìm kiếm web cho `research` và `web_search` |

## Registry

| Biến | Mục đích |
|---|---|
| `VELES_SKILLS_REGISTRY_URL` | Nguồn cho `veles browse skills` |
| `VELES_MODULES_REGISTRY_URL` | Nguồn cho `veles browse modules` |

## Nội bộ / kiểm thử

`VELES_BUNDLE_VERSION`, `VELES_CACHE_BREAKPOINT` — nội bộ; bạn không cần thiết lập
các biến này.

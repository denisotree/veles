# Biến môi trường

> 🌐 **Ngôn ngữ:** [English](../../en/reference/environment-variables.md) · [简体中文](../../zh-CN/reference/environment-variables.md) · [繁體中文](../../zh-TW/reference/environment-variables.md) · [日本語](../../ja/reference/environment-variables.md) · [한국어](../../ko/reference/environment-variables.md) · [Español](../../es/reference/environment-variables.md) · [Français](../../fr/reference/environment-variables.md) · [Italiano](../../it/reference/environment-variables.md) · [Português (BR)](../../pt-BR/reference/environment-variables.md) · [Português (PT)](../../pt-PT/reference/environment-variables.md) · [Русский](../../ru/reference/environment-variables.md) · [العربية](../../ar/reference/environment-variables.md) · [हिन्दी](../../hi/reference/environment-variables.md) · [বাংলা](../../bn/reference/environment-variables.md) · **Tiếng Việt**

Veles đọc các biến này lúc chạy. API key và token tốt nhất nên được lưu trong
keychain của hệ điều hành (`veles secret set …`); biến môi trường là phương án
dự phòng và để ghi đè.

## API key của nhà cung cấp

Chuỗi cascade tra cứu API key: keychain hệ điều hành (phạm vi dự án) → keychain
hệ điều hành (phạm vi default) → biến môi trường.

| Biến | Nhà cung cấp | Ghi chú |
|---|---|---|
| `OPENROUTER_API_KEY` | openrouter | Nhà cung cấp mặc định |
| `ANTHROPIC_API_KEY` | anthropic | API Anthropic trực tiếp |
| `OPENAI_API_KEY` | openai | API OpenAI trực tiếp |
| `GEMINI_API_KEY` | gemini | Key chính cho Google Gemini |
| `GOOGLE_API_KEY` | gemini | Phương án dự phòng cho Google Gemini |

`claude-cli` và `gemini-cli` xác thực qua binary của riêng chúng — không có biến môi trường.

## Nhà cung cấp cục bộ

| Biến | Mặc định | Mục đích |
|---|---|---|
| `OLLAMA_BASE_URL` | `http://localhost:11434/v1` | Endpoint Ollama |
| `OLLAMA_HOST` | theo `OLLAMA_BASE_URL` | Host Ollama cho embedding |
| `LLAMACPP_BASE_URL` | `http://localhost:8080/v1` | Endpoint máy chủ llama.cpp |
| `OPENAI_COMPAT_BASE_URL` | — (bắt buộc) | Endpoint cho nhà cung cấp `openai-compat` |
| `VELES_LOCAL_TOOLS` | tắt | Bật gọi tool trên các nhà cung cấp cục bộ (`1`/`true`) |
| `VELES_OLLAMA_EMBED_MODEL` | mặc định của nhà cung cấp | Ghi đè model embedding của Ollama |

## Channels & daemon

| Biến | Mặc định | Mục đích |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | — | Token bot Telegram cho `veles channel run --channel telegram` |
| `VELES_DAEMON_URL` | `http://127.0.0.1:8765` | URL cơ sở của daemon mà các gateway channel dùng |
| `VELES_DAEMON_TOKEN` | — | Bearer token để xác thực daemon |

## Đường dẫn & locale

| Biến | Mặc định | Mục đích |
|---|---|---|
| `VELES_USER_HOME` | `~` | Ghi đè thư mục home chứa `~/.veles/` (trạng thái, cache, chỉ mục keychain) |
| `VELES_HOME` | — | Bí danh cũ cho `VELES_USER_HOME` |
| `VELES_REGISTRY_PATH` | `~/.veles/…` | Ghi đè đường dẫn registry đa dự án |
| `VELES_LOCALE` | `[user] language` hoặc `en` | Ghi đè locale UI đang hoạt động cho một lần chạy |
| `VELES_LOG_LEVEL` | `INFO` | Mức chi tiết log/daemon (`DEBUG`/`INFO`/`WARNING`/`ERROR`) |
| `VELES_CONFIG_FILENAME` | `config.toml` | Ghi đè tên file config (kiểm thử) |

## Cờ hành vi & tính năng

| Biến | Mặc định | Mục đích |
|---|---|---|
| `VELES_NO_WIZARD` | tắt | Bỏ qua trình thiết lập lần đầu (cũng cần một TTY) |
| `VELES_MANAGER_MODE` | tắt | Bắt buộc dùng manager đa-agent cho `veles run` (`1` bật / `0` công tắc tắt) |
| `VELES_VERIFY_MODE` | tắt | Bắt buộc lượt verify→escalate cho `veles run` (`1` bật / `0` công tắc tắt) |
| `VELES_FENCED_TOOLS` | tắt | Chạy tool theo đường thực thi fenced/sandbox |
| `VELES_TRUST_AUTO_ALLOW` | tắt | Bỏ qua trust ladder (CI / autopilot / các sub-agent đã được cấp quyền trước) |
| `VELES_SANDBOX_ROOTS` | dự án + `~/.veles` | Ghi đè (phân tách bằng `:`) các thư mục gốc đọc/ghi của sandbox |
| `VELES_FETCH_ALLOW_PRIVATE` | tắt | Cho phép tool truy cập các địa chỉ RFC-1918 / riêng tư |
| `VELES_MEMORY_RERANK` | bật | Rerank vector cho việc recall bộ nhớ (`0`/`false` để tắt) |
| `VELES_WEB_SEARCH_BACKEND` | auto | Backend tìm kiếm web cho `research` và `web_search` |

## Registry

| Biến | Mục đích |
|---|---|
| `VELES_SKILLS_REGISTRY_URL` | Nguồn cho `veles browse skills` |
| `VELES_MODULES_REGISTRY_URL` | Nguồn cho `veles browse modules` |

## Nội bộ / kiểm thử

| Biến | Mục đích |
|---|---|
| `VELES_BUNDLE_VERSION` | Nội bộ; bạn không cần phải đặt biến này |
| `VELES_REPL_SIMPLE` | Đặt `1` để bắt buộc dùng vòng lặp REPL đơn giản theo từng dòng thay vì ứng dụng `prompt_toolkit` toàn màn hình (phương án dự phòng cho các terminal hạn chế) |

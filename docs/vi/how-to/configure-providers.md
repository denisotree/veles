# Cách cấu hình nhà cung cấp

> 🌐 **Ngôn ngữ:** [English](../../en/how-to/configure-providers.md) · [简体中文](../../zh-CN/how-to/configure-providers.md) · [繁體中文](../../zh-TW/how-to/configure-providers.md) · [日本語](../../ja/how-to/configure-providers.md) · [한국어](../../ko/how-to/configure-providers.md) · [Español](../../es/how-to/configure-providers.md) · [Français](../../fr/how-to/configure-providers.md) · [Italiano](../../it/how-to/configure-providers.md) · [Português (BR)](../../pt-BR/how-to/configure-providers.md) · [Português (PT)](../../pt-PT/how-to/configure-providers.md) · [Русский](../../ru/how-to/configure-providers.md) · [العربية](../../ar/how-to/configure-providers.md) · [हिन्दी](../../hi/how-to/configure-providers.md) · [বাংলা](../../bn/how-to/configure-providers.md) · **Tiếng Việt**

Chuyển Veles giữa OpenRouter, Anthropic, OpenAI, Gemini, các model cục bộ, hoặc
một gói đăng ký CLI. Danh sách nhà cung cấp đầy đủ: [tham khảo nhà cung cấp](../reference/providers.md).

## Chọn một nhà cung cấp theo từng lệnh

```bash
veles run --provider anthropic --model claude-sonnet-4.6 "..."
veles run --provider openai     --model gpt-4o            "..."
veles run --provider gemini     --model gemini-2.5-pro    "..."
```

## Đặt mặc định cho dự án

Đặt một giá trị cơ sở trong `<project>/.veles/config.toml`:

```toml
[engine]
provider = "openrouter"                 # provider name
model = "anthropic/claude-sonnet-4.6"  # model id
```

Hoặc một giá trị mặc định user-global trong `~/.veles/config.toml`:

```toml
[user]
default_provider = "openrouter"
default_model = "anthropic/claude-sonnet-4.6"
```

## Cung cấp API key

Các nhà cung cấp đám mây cần một key. Lưu nó một lần trong keychain của hệ điều hành:

```bash
veles secret set OPENROUTER_API_KEY
veles secret set ANTHROPIC_API_KEY
```

…hoặc export [biến môi trường](../reference/environment-variables.md):

```bash
export OPENROUTER_API_KEY=sk-or-v1-...
```

Thứ tự tra cứu: keychain (phạm vi dự án) → keychain (default) → biến môi trường.
Các key **không bao giờ** được ghi vào file config.

## Dùng một model hoàn toàn cục bộ (không cần key)

Cài [Ollama](https://ollama.com), pull một model, và trỏ Veles tới nó:

```bash
ollama pull qwen3:4b-instruct
veles models ollama                     # confirm it's listed
veles run --provider ollama --model qwen3:4b-instruct "Hello"
```

Gọi tool **mặc định bị tắt** trên các nhà cung cấp cục bộ. Bật nó khi bạn đã chọn
một model hỗ trợ tool:

```bash
export VELES_LOCAL_TOOLS=1
```

Ghi đè endpoint nếu máy chủ của bạn không ở cổng mặc định:

```bash
export OLLAMA_BASE_URL=http://localhost:11434/v1
export LLAMACPP_BASE_URL=http://localhost:8080/v1
export OPENAI_COMPAT_BASE_URL=http://my-host:8000/v1   # required for openai-compat
```

## Ủy thác cho một gói đăng ký CLI Claude / Gemini

Nếu bạn đã xác thực CLI `claude` hoặc `gemini`, Veles có thể điều khiển nó:

```bash
veles run --provider claude-cli "..."
veles run --provider gemini-cli "..."
```

Không cần API key — CLI tự lo việc xác thực.

## Liệt kê các model có sẵn

```bash
veles models openrouter            # cloud: cached 24h
veles models openrouter --refresh  # force re-fetch
veles models ollama                # local: always live
```

## Tiếp theo

- [Định tuyến các tác vụ khác nhau tới các model khác nhau](per-task-routing.md) —
  model rẻ cho nén, model mạnh cho lập kế hoạch.

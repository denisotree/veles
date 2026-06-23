# Cách cấu hình provider

> 🌐 **Ngôn ngữ:** [English](../../en/how-to/configure-providers.md) · **Tiếng Việt**

Chuyển Veles giữa OpenRouter, Anthropic, OpenAI, Gemini, các model cục bộ, hay một
subscription CLI. Danh sách provider đầy đủ: [tham chiếu provider](../reference/providers.md).

## Chọn provider theo từng lệnh

```bash
veles run --provider anthropic --model claude-sonnet-4.6 "..."
veles run --provider openai     --model gpt-4o            "..."
veles run --provider gemini     --model gemini-2.5-pro    "..."
```

## Đặt mặc định cho dự án

Đặt một giá trị cơ sở trong `<project>/.veles/config.toml`:

```toml
[provider]
default = "openrouter:anthropic/claude-sonnet-4.6"
```

Hoặc một mặc định toàn cục theo người dùng trong `~/.veles/config.toml`:

```toml
[user]
default_provider = "openrouter"
default_model = "anthropic/claude-sonnet-4.6"
```

## Cung cấp API key

Các provider trên cloud cần một key. Lưu nó một lần vào keychain của hệ điều hành:

```bash
veles secret set OPENROUTER_API_KEY
veles secret set ANTHROPIC_API_KEY
```

…hoặc export [biến môi trường](../reference/environment-variables.md):

```bash
export OPENROUTER_API_KEY=sk-or-v1-...
```

Thứ tự tra cứu: keychain (phạm vi dự án) → keychain (mặc định) → biến môi trường.
Key **không bao giờ** được ghi vào các tệp config.

## Dùng một model hoàn toàn cục bộ (không cần key)

Cài [Ollama](https://ollama.com), pull một model, và trỏ Veles tới nó:

```bash
ollama pull qwen3:4b-instruct
veles models ollama                     # xác nhận nó đã được liệt kê
veles run --provider ollama --model qwen3:4b-instruct "Hello"
```

Việc gọi công cụ (tool calling) **mặc định tắt** trên các provider cục bộ. Bật nó
khi bạn đã chọn một model có khả năng dùng công cụ:

```bash
export VELES_LOCAL_TOOLS=1
```

Ghi đè các endpoint nếu server của bạn không ở cổng mặc định:

```bash
export OLLAMA_BASE_URL=http://localhost:11434/v1
export LLAMACPP_BASE_URL=http://localhost:8080/v1
export OPENAI_COMPAT_BASE_URL=http://my-host:8000/v1   # bắt buộc cho openai-compat
```

## Ủy quyền cho subscription CLI Claude / Gemini

Nếu bạn đã xác thực CLI `claude` hoặc `gemini`, Veles có thể điều khiển nó:

```bash
veles run --provider claude-cli "..."
veles run --provider gemini-cli "..."
```

Không cần API key — CLI tự xử lý việc xác thực.

## Liệt kê các model khả dụng

```bash
veles models openrouter            # cloud: cache 24h
veles models openrouter --refresh  # buộc lấy lại
veles models ollama                # cục bộ: luôn lấy trực tiếp
```

## Tiếp theo

- [Định tuyến các tác vụ khác nhau tới các model khác nhau](per-task-routing.md) —
  model rẻ cho nén, model mạnh cho lập kế hoạch.

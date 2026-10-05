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

Gọi tool được **phát hiện** từ những gì máy chủ công bố. Buộc bật bằng
`VELES_LOCAL_TOOLS=1` (hoặc buộc tắt bằng `=0`).

Ghi đè endpoint nếu máy chủ của bạn không ở cổng mặc định:

```bash
export OLLAMA_BASE_URL=http://localhost:11434/v1
export LLAMACPP_BASE_URL=http://localhost:8080/v1
export OPENAI_COMPAT_BASE_URL=http://my-host:8000/v1   # required for openai-compat
```

## Thêm nhà cung cấp của riêng bạn

Bất kỳ API tương thích OpenAI được lưu trữ sẵn nào, hoặc một máy chủ do bạn chạy, đều
trở thành nhà cung cấp chỉ với một mục trong `~/.veles/providers.toml` — không cần
code. Id là tên bảng:

```toml
[providers.groq]
kind = "openai-api"                          # a hosted API; needs a key
label = "Groq"                               # shown in the wizards (optional)
base_url = "https://api.groq.com/openai/v1"
key_env = ["GROQ_API_KEY"]

[providers.lmstudio]
kind = "local"                               # a server you run; a key is optional
base_url = "http://localhost:1234/v1"
```

Sau đó dùng nó như mọi nhà cung cấp tích hợp sẵn:

```bash
veles secret set GROQ_API_KEY      # into the keychain, where the groq entry reads it
veles models groq
veles run --provider groq --model llama-3.3-70b-versatile "..."
```

| Key | Ý nghĩa |
|---|---|
| `kind` | `openai-api` (một API được lưu trữ sẵn) hoặc `local` (một máy chủ do bạn chạy) |
| `base_url` | endpoint tương thích OpenAI, kết thúc bằng `/v1` (hoặc tương đương của nhà cung cấp) |
| `base_url_env` | một biến môi trường ghi đè `base_url` khi được đặt |
| `key_env` | tên các biến môi trường mà key được đọc từ đó; keychain được thử trước |
| `label`, `tagline` | cách các trình thiết lập hiển thị nó |
| `tools` | `auto` (mặc định), `on` hoặc `off` — model có được dùng lời gọi tool hay không |

Một mục có id tích hợp sẵn (`[providers.ollama]`) thay đổi cài đặt của nhà cung cấp
đó — ví dụ `base_url` — nhưng không đổi loại (kind). Một file hỏng chỉ được báo một
lần, và Veles tiếp tục với các nhà cung cấp tích hợp sẵn; `veles doctor` liệt kê
những gì sai trong đó.

Điểm khởi đầu cho các API phổ biến — **chưa được đội Veles kiểm chứng**, hãy xem tài
liệu của nhà cung cấp để biết endpoint hiện hành:

| id | `base_url` | `key_env` |
|---|---|---|
| `groq` | `https://api.groq.com/openai/v1` | `GROQ_API_KEY` |
| `deepseek` | `https://api.deepseek.com/v1` | `DEEPSEEK_API_KEY` |
| `mistral` | `https://api.mistral.ai/v1` | `MISTRAL_API_KEY` |
| `together` | `https://api.together.xyz/v1` | `TOGETHER_API_KEY` |
| `xai` | `https://api.x.ai/v1` | `XAI_API_KEY` |
| `fireworks` | `https://api.fireworks.ai/inference/v1` | `FIREWORKS_API_KEY` |
| `deepinfra` | `https://api.deepinfra.com/v1/openai` | `DEEPINFRA_API_KEY` |
| `nebius` | `https://api.studio.nebius.com/v1` | `NEBIUS_API_KEY` |
| `cerebras` | `https://api.cerebras.ai/v1` | `CEREBRAS_API_KEY` |
| `zai` | `https://api.z.ai/api/paas/v4` | `ZAI_API_KEY` |
| `moonshot` | `https://api.moonshot.ai/v1` | `MOONSHOT_API_KEY` |
| `lmstudio` (`local`) | `http://localhost:1234/v1` | — |
| `vllm` (`local`) | `http://localhost:8000/v1` | — |

## Ủy thác cho một gói đăng ký Claude / Google

Nếu bạn đã xác thực CLI `claude`, Veles có thể điều khiển nó:

```bash
veles run --provider claude-cli "..."
```

Với gói đăng ký Google, hãy cài và đăng nhập Antigravity CLI (`agy`) một lần, rồi gọi
tên nhà cung cấp của nó — module `antigravity-cli` tự cài từ các registry đã kết nối
của bạn ngay ở lần chạy đó:

```bash
veles run --provider antigravity-cli --model gemini-3.8-flash-high "..."
veles models antigravity-cli
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

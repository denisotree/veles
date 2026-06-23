# Provider

> 🌐 **Ngôn ngữ:** [English](../../en/reference/providers.md) · **Tiếng Việt**

Veles không phụ thuộc vào provider cụ thể. Truyền `--provider <name>` cho bất kỳ
lệnh agent nào, hoặc đặt mặc định trong cấu hình. ID của model dùng quy ước đặt tên
riêng của từng provider.

| Provider | Loại | API key | Ghi chú |
|---|---|---|---|
| `openrouter` | Cổng cloud | `OPENROUTER_API_KEY` | **Mặc định.** Chuyển tiếp hàng trăm model; ID model như `anthropic/claude-sonnet-4.6` |
| `anthropic` | Cloud trực tiếp | `ANTHROPIC_API_KEY` | Claude Messages API, prompt caching |
| `openai` | Cloud trực tiếp | `OPENAI_API_KEY` | GPT chat completions |
| `gemini` | Cloud trực tiếp | `GEMINI_API_KEY` / `GOOGLE_API_KEY` | Google Gemini |
| `claude-cli` | Subprocess | — (CLI session) | Ủy thác cho CLI `claude` cục bộ ở chế độ JSON-stream |
| `gemini-cli` | Subprocess | — (CLI session) | Ủy thác cho CLI `gemini` cục bộ |
| `ollama` | Cục bộ | none | `OLLAMA_BASE_URL` (mặc định `http://localhost:11434/v1`) |
| `llamacpp` | Cục bộ | none | `LLAMACPP_BASE_URL` (mặc định `http://localhost:8080/v1`) |
| `openai-compat` | Cục bộ/tùy chỉnh | none | `OPENAI_COMPAT_BASE_URL` (bắt buộc, không có mặc định) |

Mặc định: provider `openrouter`, model `anthropic/claude-sonnet-4.6`, compressor
`anthropic/claude-haiku-4.5`.

## Provider cục bộ

`ollama`, `llamacpp`, và `openai-compat` không cần API key. Liệt kê các model đã cài
bằng `veles models <provider>` (luôn lấy trực tiếp đối với các provider cục bộ).

**Tool calling mặc định tắt** trên các provider cục bộ — nhiều model cục bộ phát ra
tool call sai định dạng. Bật nó lên một khi bạn đã chọn được một model có khả năng
gọi công cụ:

```bash
export VELES_LOCAL_TOOLS=1
veles run --provider ollama --model qwen3:4b-instruct "..."
```

Ghi đè endpoint bằng các biến môi trường `*_BASE_URL` (xem
[biến môi trường](environment-variables.md)).

## Ủy thác CLI (`claude-cli`, `gemini-cli`)

Nếu bạn có gói đăng ký Claude hoặc Gemini CLI, Veles có thể chạy binary đó ở chế độ
JSON-streaming và đóng vai trò điều phối viên — giữ vòng lặp ưu tiên cục bộ mà không
cần một API key riêng. Các công cụ của Veles chỉ tiếp cận được subprocess khi đã
cấu hình một cầu nối MCP.

## Trạng thái đa phương thức (vision / speech-to-text)

Veles định nghĩa một `VisionAdapter` và một protocol STT adapter (`modules/vision.py`,
`modules/stt.py`) cùng với một registry toàn cục cấp tiến trình, **nhưng không có
adapter cụ thể nào được ship và không có gì đăng ký adapter khi daemon khởi động**.
Vì vậy một bức ảnh hoặc tin nhắn thoại gửi tới một kênh hiện tại sẽ trả về thông báo
"not configured" thay vì được phân tích. Tác vụ routing `vision` tồn tại sẵn cho khi
một adapter được nối vào. Xem
[kết nối Telegram](../how-to/connect-telegram.md#multimodal-limitation).

## Chọn một model

```bash
veles models openrouter            # cached 24h
veles models openrouter --refresh  # bypass cache
veles models ollama                # always live
```

Để dùng các model khác nhau cho các công việc khác nhau (model rẻ cho nén, model mạnh
cho lập kế hoạch), xem [routing theo tác vụ](../how-to/per-task-routing.md).

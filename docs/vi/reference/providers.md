# Nhà cung cấp

> 🌐 **Languages:** **English** · [Русский](../../ru/reference/providers.md)

Veles không phụ thuộc vào nhà cung cấp nào. Truyền `--provider <name>` cho bất kỳ
lệnh agent nào, hoặc đặt một giá trị mặc định trong config. ID model dùng quy ước
đặt tên của chính nhà cung cấp.

| Nhà cung cấp | Loại | API key | Ghi chú |
|---|---|---|---|
| `openrouter` | Cổng đám mây | `OPENROUTER_API_KEY` | **Mặc định.** Chuyển tiếp hàng trăm model; ID model như `anthropic/claude-sonnet-4.6` |
| `anthropic` | Đám mây trực tiếp | `ANTHROPIC_API_KEY` | Claude Messages API, prompt caching |
| `openai` | Đám mây trực tiếp | `OPENAI_API_KEY` | GPT chat completions |
| `gemini` | Đám mây trực tiếp | `GEMINI_API_KEY` / `GOOGLE_API_KEY` | Google Gemini |
| `claude-cli` | Tiến trình con | — (session CLI) | Ủy thác cho CLI `claude` cục bộ ở chế độ JSON-stream |
| `gemini-cli` | Tiến trình con | — (session CLI) | Ủy thác cho CLI `gemini` cục bộ |
| `ollama` | Cục bộ | không | `OLLAMA_BASE_URL` (mặc định `http://localhost:11434/v1`) |
| `llamacpp` | Cục bộ | không | `LLAMACPP_BASE_URL` (mặc định `http://localhost:8080/v1`) |
| `openai-compat` | Cục bộ/tùy chỉnh | không | `OPENAI_COMPAT_BASE_URL` (bắt buộc, không có mặc định) |

Nhà cung cấp mặc định: `openrouter`. **Không có model mặc định cứng** — hãy đặt
một model qua trình thiết lập, qua `[provider] model`, hoặc qua `--model` (nếu
không agent sẽ báo "no model configured"). Các route theo tác vụ kế thừa
`[provider]` làm cơ sở trừ khi được ghi đè trong `[routing.tasks]` — xem
[định tuyến theo tác vụ](../how-to/per-task-routing.md).

## Nhà cung cấp cục bộ

`ollama`, `llamacpp`, và `openai-compat` không cần API key. Liệt kê các model đã
cài bằng `veles models <provider>` (luôn trực tiếp với các nhà cung cấp cục bộ).

**Gọi tool mặc định bị tắt** trên các nhà cung cấp cục bộ — nhiều model cục bộ
phát ra các lời gọi tool sai định dạng. Bật nó khi bạn đã chọn một model hỗ trợ
tool:

```bash
export VELES_LOCAL_TOOLS=1
veles run --provider ollama --model qwen3:4b-instruct "..."
```

Ghi đè endpoint bằng các biến môi trường `*_BASE_URL` (xem
[biến môi trường](environment-variables.md)).

## Ủy thác CLI (`claude-cli`, `gemini-cli`)

Nếu bạn có gói đăng ký CLI Claude hoặc Gemini, Veles có thể chạy binary đó ở chế
độ JSON-streaming và đóng vai trò điều phối — giữ vòng lặp ưu tiên cục bộ mà
không cần API key riêng. Các tool của Veles chỉ tiếp cận được tiến trình con khi
một cầu nối MCP được cấu hình.

## Trạng thái đa phương thức (vision / chuyển giọng nói thành văn bản)

Veles định nghĩa một `VisionAdapter` và một protocol adapter STT
(`modules/vision.py`, `modules/stt.py`) cùng một registry toàn cục theo tiến
trình, **nhưng không có adapter cụ thể nào được ship và không có gì đăng ký một
adapter khi daemon khởi động**. Vì vậy, một ảnh hoặc tin nhắn thoại gửi tới một
channel hiện tại sẽ trả về một thông báo "not configured" thay vì được phân tích.
Tác vụ định tuyến `vision` tồn tại để dùng khi một adapter được kết nối. Xem
[kết nối Telegram](../how-to/connect-telegram.md#multimodal-limitation).

## Chọn một model

```bash
veles models openrouter            # cached 24h
veles models openrouter --refresh  # bypass cache
veles models ollama                # always live
```

Để dùng các model khác nhau cho các công việc khác nhau (model rẻ cho nén, model
mạnh cho lập kế hoạch), xem [định tuyến theo tác vụ](../how-to/per-task-routing.md).

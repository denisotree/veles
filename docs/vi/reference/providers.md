# Nhà cung cấp

> 🌐 **Ngôn ngữ:** [English](../../en/reference/providers.md) · [简体中文](../../zh-CN/reference/providers.md) · [繁體中文](../../zh-TW/reference/providers.md) · [日本語](../../ja/reference/providers.md) · [한국어](../../ko/reference/providers.md) · [Español](../../es/reference/providers.md) · [Français](../../fr/reference/providers.md) · [Italiano](../../it/reference/providers.md) · [Português (BR)](../../pt-BR/reference/providers.md) · [Português (PT)](../../pt-PT/reference/providers.md) · [Русский](../../ru/reference/providers.md) · [العربية](../../ar/reference/providers.md) · [हिन्दी](../../hi/reference/providers.md) · [বাংলা](../../bn/reference/providers.md) · **Tiếng Việt**

Veles không phụ thuộc vào nhà cung cấp nào. Truyền `--provider <id>` cho bất kỳ
lệnh agent nào, hoặc đặt một giá trị mặc định trong config. ID model dùng quy ước
đặt tên của chính nhà cung cấp.

## Danh mục nhà cung cấp

Mọi nhà cung cấp mà Veles biết đều là một mục trong một danh mục duy nhất, được xây
dựng từ ba nguồn:

1. **Tích hợp sẵn** — bảng bên dưới, đi kèm Veles.
2. **Của bạn** — `~/.veles/providers.toml`: thêm một mục để dùng một API tương thích
   OpenAI được lưu trữ sẵn hoặc một máy chủ do bạn chạy (xem
   [thêm nhà cung cấp của riêng bạn](../how-to/configure-providers.md#thêm-nhà-cung-cấp-của-riêng-bạn)).
   Một mục có id tích hợp sẵn sẽ ghi đè cài đặt của nhà cung cấp đó (ví dụ `base_url`).
3. **Module** — một module registry đóng góp một nhà cung cấp (`antigravity-cli`). Gọi
   tên nó trong `[engine] provider`, một route hoặc `--provider` sẽ cài nó từ các
   registry đã kết nối của bạn ở lần chạy kế tiếp, giống như một channel đã khai báo.

`--provider`, `veles models`, các trình thiết lập, định tuyến và `veles doctor` đều đọc
danh mục, nên một nhà cung cấp từ bất kỳ nguồn nào cũng dùng được ở mọi nơi như một
nhà cung cấp tích hợp sẵn. Một id không xác định là lỗi một dòng liệt kê những gì hiện
có; `veles doctor` cũng kiểm tra `~/.veles/providers.toml` và mọi nhà cung cấp mà các
route của bạn nêu tên.

| Nhà cung cấp | Loại | API key | Ghi chú |
|---|---|---|---|
| `openrouter` | Cổng đám mây | `OPENROUTER_API_KEY` | **Mặc định.** Chuyển tiếp hàng trăm model; ID model như `anthropic/claude-sonnet-4.6` |
| `anthropic` | Đám mây trực tiếp | `ANTHROPIC_API_KEY` | Claude Messages API, prompt caching |
| `openai` | Đám mây trực tiếp | `OPENAI_API_KEY` | GPT chat completions |
| `gemini` | Đám mây trực tiếp | `GEMINI_API_KEY` / `GOOGLE_API_KEY` | Google Gemini |
| `claude-cli` | CLI ủy thác | — (session CLI) | Ủy thác cho CLI `claude` cục bộ ở chế độ JSON-stream |
| `ollama` | Cục bộ | không | `OLLAMA_BASE_URL` (mặc định `http://localhost:11434/v1`) |
| `llamacpp` | Cục bộ | không | `LLAMACPP_BASE_URL` (mặc định `http://localhost:8080/v1`) |
| `openai-compat` | Cục bộ/tùy chỉnh | tùy chọn `OPENAI_COMPAT_API_KEY` | `OPENAI_COMPAT_BASE_URL` (bắt buộc, không có mặc định) |

`gemini-cli` đã bị gỡ bỏ ở 1.2.6 — Google không còn cung cấp Gemini CLI cho tài khoản
cá nhân. Hãy dùng `gemini` với một API key, hoặc module `antigravity-cli`.

Nhà cung cấp mặc định: `openrouter`. **Không có model mặc định cứng** — hãy đặt
một model qua trình thiết lập, qua `[engine] model`, hoặc qua `--model` (nếu
không agent sẽ báo "no model configured"). Các route theo tác vụ kế thừa
`[engine]` làm cơ sở trừ khi được ghi đè trong `[routing.tasks]` — xem
[định tuyến theo tác vụ](../how-to/per-task-routing.md).

## Nhà cung cấp cục bộ

`ollama`, `llamacpp`, và `openai-compat` không cần API key. Liệt kê các model đã
cài bằng `veles models <provider>` (luôn trực tiếp với các nhà cung cấp cục bộ).

**Gọi tool được phát hiện** từ những gì backend công bố: ollama báo khả năng của từng
model, còn máy chủ llama.cpp báo khả năng của chat template. `VELES_LOCAL_TOOLS=1`
buộc bật gọi tool, `=0` buộc tắt; để trống nghĩa là tự phát hiện.

```bash
veles run --provider ollama --model qwen3:4b-instruct "..."
```

Ghi đè endpoint bằng các biến môi trường `*_BASE_URL` (xem
[biến môi trường](environment-variables.md)).

## Ủy thác CLI (`claude-cli`, `antigravity-cli`)

Nếu bạn có gói đăng ký Claude hoặc Google, Veles có thể chạy CLI của nó ở chế độ
headless và đóng vai trò điều phối — không cần API key riêng. `claude-cli` là bản
tích hợp sẵn; `antigravity-cli` (CLI `agy`) là một module registry, tự cài đặt khi bạn
gọi tên nó.

Bên được ủy thác chỉ đóng vai trò model: các tool của Veles tiếp cận nó qua một cầu
nối MCP, và mọi lời gọi đều đi qua thang tin cậy của Veles. Config của cầu nối nằm
trong một thư mục của tiến trình đang chạy, `.veles/tmp/delegate-<pid>/`, được xóa
khi tiến trình thoát. `agy` chạy ở đó trong một workspace tạm, không phải trong dự
án của bạn, sau một cổng chặn shell và các tool tệp của chính nó.

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

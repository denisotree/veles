# Tổng quan kiến trúc

> 🌐 **Ngôn ngữ:** [English](../../en/explanation/architecture.md) · [简体中文](../../zh-CN/explanation/architecture.md) · [繁體中文](../../zh-TW/explanation/architecture.md) · [日本語](../../ja/explanation/architecture.md) · [한국어](../../ko/explanation/architecture.md) · [Español](../../es/explanation/architecture.md) · [Français](../../fr/explanation/architecture.md) · [Italiano](../../it/explanation/architecture.md) · [Português (BR)](../../pt-BR/explanation/architecture.md) · [Português (PT)](../../pt-PT/explanation/architecture.md) · [Русский](../../ru/explanation/architecture.md) · [العربية](../../ar/explanation/architecture.md) · [हिन्दी](../../hi/explanation/architecture.md) · [বাংলা](../../bn/explanation/architecture.md) · **Tiếng Việt**

Trang này giải thích Veles *là gì* và các thành phần của nó ghép lại với nhau ra
sao, để phần còn lại của tài liệu trở nên dễ hiểu. Để xem tầm nhìn sản phẩm chính
thức, hãy đọc `VISION.md` ở thư mục gốc của repo.

## Ý đồ thiết kế

Veles được thiết kế có chủ đích là **tối giản và phân tách rõ ràng** — các module
đơn-trách-nhiệm, không có god-file. Nó **ưu tiên cục bộ (local-first)**: bạn chạy
nó trên một thư mục trên máy của mình, và nó giữ bộ nhớ có cấu trúc của riêng nó
ngay tại đó.

## Năm trụ cột (phần lõi)

Mọi thứ trong phần lõi đều phục vụ một trong năm nhiệm vụ:

1. **Bộ nhớ dự án (project memory)** — một artefact có cấu trúc (tách biệt khỏi nội
   dung của bạn) chứa nhật ký phiên làm việc, các quy tắc/insight đã học, bản đồ
   tệp dự án, và các registry kỹ năng/công cụ kèm telemetry. Xem [bộ nhớ dự án & vòng lặp học](project-memory-and-learning-loop.md).
2. **Vòng lặp học (learning loop)** — curator, bộ trích xuất insight, và quá trình
   dreaming giúp bộ nhớ luôn mới mẻ và biến kinh nghiệm thành các quy tắc tái sử dụng được.
3. **Điều phối đa tác tử (multi-agent orchestration)** — một manager phân rã tác vụ
   và sinh ra các worker chuyên biệt. Xem [điều phối đa tác tử](multi-agent-orchestration.md).
4. **Giao thức nhà cung cấp (provider protocol)** — một giao diện duy nhất cho nhiều
   backend LLM (cloud, local, ủy thác CLI). Xem [providers](../reference/providers.md).
5. **Công cụ & kỹ năng tối thiểu** — một tập khởi động nhỏ và **tích lũy dần** khi
   Veles tự viết công cụ của riêng nó và hình thức hóa các quy trình lặp lại thành
   kỹ năng. Xem [kỹ năng & công cụ](skills-and-tools.md).

## Mọi thứ khác đều là module tùy chọn

Gateway/kênh, daemon, scheduler, TUI, vision/STT — tất cả đều **cắm-rút được
(pluggable)** và chỉ nạp khi được sử dụng. Veles khởi động với phần tối thiểu và
mở rộng theo nhu cầu, nhờ vậy một lệnh `veles run` đơn giản vẫn giữ được sự đơn giản.

## Một lượt tương tác diễn ra như thế nào

```
your prompt
   │
   ▼
context: AGENTS.md (small) + on-demand recall from project memory
   │
   ▼
agent loop  ──►  provider (routed per task)  ──►  tool calls
   │                                               │
   │            (trust ladder gates sensitive tools)
   ▼
response  ──►  saved to memory  ──►  learning triggers (insights, curator)
```

Tệp ngữ cảnh (`AGENTS.md`) được giữ nhỏ một cách có chủ đích; các kiến thức phụ trợ
(trang wiki, bản đồ tệp dự án, các lượt trao đổi liên quan trong quá khứ) được kéo
vào **theo nhu cầu** thay vì đổ hết vào ngay từ đầu.

## Trạng thái được lưu ở đâu

- `<project>/.veles/` — bộ nhớ, cấu hình, kỹ năng/công cụ cục bộ của dự án này.
- `~/.veles/` — cấu hình toàn cục theo người dùng, kỹ năng/công cụ liên-dự-án, cache, trust.
- `<project>/AGENTS.md`, `wiki/`, `sources/` — nội dung của bạn (bố cục LLM-Wiki).

Xem [bố cục dự án](../reference/project-layout.md).

## Đa dự án trong một vòng lặp

Một vòng lặp tác tử duy nhất phục vụ nhiều dự án. Mỗi dự án có thư mục riêng với
ngữ cảnh và bộ nhớ riêng; `AGENTS.md` được symlink sang `CLAUDE.md`/`GEMINI.md` để
một CLI ngoài được khởi chạy ở đó thấy được cùng một ngữ cảnh. Xem
[nhiều dự án](../how-to/multi-project-and-subprojects.md).

## Các mặt tương tác (surfaces)

- **CLI** (`veles run`, `veles add`, …) — dùng một lần và dùng trong script.
- **TUI** (`veles tui`) — REPL tương tác với [các chế độ chạy](modes.md).
- **Daemon + kênh** — API không giao diện, Telegram, các tác vụ theo lịch.

Cả ba đều điều khiển cùng một vòng lặp tác tử lõi.

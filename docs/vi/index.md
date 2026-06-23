# Tài liệu Veles

> 🌐 **Ngôn ngữ:** [English](../en/index.md) · [简体中文](../zh-CN/index.md) · [繁體中文](../zh-TW/index.md) · [日本語](../ja/index.md) · [한국어](../ko/index.md) · [Español](../es/index.md) · [Français](../fr/index.md) · [Italiano](../it/index.md) · [Português (BR)](../pt-BR/index.md) · [Português (PT)](../pt-PT/index.md) · [Русский](../ru/index.md) · [العربية](../ar/index.md) · [हिन्दी](../hi/index.md) · [বাংলা](../bn/index.md) · **Tiếng Việt**

Veles là một framework agent CLI tối giản, ưu tiên cục bộ. Bạn trỏ nó vào một thư
mục dự án; nó duy trì một **bộ nhớ dự án** có cấu trúc, **học hỏi** từ các session
của bạn, chạy bất kỳ nhà cung cấp LLM nào (đám mây hoặc cục bộ), và tích lũy các
**skill** và **tool** có thể tái sử dụng khi nó làm việc.

Tài liệu này tuân theo mô hình [Diátaxis](https://diataxis.fr/). Hãy chọn góc phần
tư phù hợp với điều bạn cần ngay lúc này.

## Bắt đầu tại đây

Nếu bạn chưa bao giờ chạy Veles, hãy làm hai hướng dẫn theo thứ tự:

1. **[Bắt đầu](tutorials/getting-started.md)** — cài đặt Veles, thiết lập một API
   key, tạo dự án đầu tiên, và chạy prompt đầu tiên.
2. **[Xây dựng một cơ sở tri thức](tutorials/building-a-knowledge-base.md)** — nạp
   các nguồn vào LLM-Wiki, đặt câu hỏi, và củng cố các session.

## Hướng dẫn (Tutorials) — học qua thực hành

- [Bắt đầu](tutorials/getting-started.md)
- [Xây dựng một cơ sở tri thức](tutorials/building-a-knowledge-base.md)

## Hướng dẫn thao tác (How-to) — hoàn thành một tác vụ

- [Cấu hình nhà cung cấp (đám mây & cục bộ)](how-to/configure-providers.md)
- [Định tuyến các tác vụ khác nhau tới các model khác nhau](how-to/per-task-routing.md)
- [Chạy Veles như một daemon](how-to/run-as-daemon.md)
- [Kết nối một channel Telegram](how-to/connect-telegram.md)
- [Quản lý skills, tools, và modules](how-to/manage-skills-and-tools.md)
- [Làm việc với nhiều dự án và subproject](how-to/multi-project-and-subprojects.md)
- [Bảo mật: trust, autopilot, secrets](how-to/security-and-permissions.md)
- [Tác vụ chạy lâu: goals, jobs, dreaming, research](how-to/long-running-tasks.md)
- [Kết nối máy chủ MCP bên ngoài](how-to/external-mcp-servers.md)
- [Sao lưu và chia sẻ một dự án](how-to/backup-and-share.md)

## Tham chiếu (Reference) — tra cứu

- [Tham chiếu lệnh CLI](reference/cli.md)
- [Cấu hình (`config.toml`)](reference/configuration.md)
- [Biến môi trường](reference/environment-variables.md)
- [Nhà cung cấp](reference/providers.md)
- [Phím tắt TUI & lệnh slash](reference/tui.md)
- [Bố cục & trạng thái dự án](reference/project-layout.md)

## Giải thích (Explanation) — hiểu thiết kế

- [Tổng quan kiến trúc](explanation/architecture.md)
- [Bộ nhớ dự án & vòng lặp học hỏi](explanation/project-memory-and-learning-loop.md)
- [Skills & tools như năng lực tích lũy](explanation/skills-and-tools.md)
- [Chế độ chạy](explanation/modes.md)
- [Điều phối đa agent](explanation/multi-agent-orchestration.md)
- [Gói layout & LLM-Wiki](explanation/layout-packs-and-llm-wiki.md)
- [Trust & sandbox](explanation/trust-and-sandbox.md)

---

Để biết tầm nhìn sản phẩm và lý do thiết kế, xem `VISION.md` (ở thư mục gốc của
repo); để biết toàn bộ lịch sử triển khai, xem `MILESTONES.md`. Những tài liệu đó
hướng tới nhà phát triển — tài liệu này dành cho việc **sử dụng** Veles.

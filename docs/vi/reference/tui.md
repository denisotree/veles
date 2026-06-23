# Phím tắt TUI & lệnh slash

> 🌐 **Ngôn ngữ:** [English](../../en/reference/tui.md) · [简体中文](../../zh-CN/reference/tui.md) · [繁體中文](../../zh-TW/reference/tui.md) · [日本語](../../ja/reference/tui.md) · [한국어](../../ko/reference/tui.md) · [Español](../../es/reference/tui.md) · [Français](../../fr/reference/tui.md) · [Italiano](../../it/reference/tui.md) · [Português (BR)](../../pt-BR/reference/tui.md) · [Português (PT)](../../pt-PT/reference/tui.md) · [Русский](../../ru/reference/tui.md) · [العربية](../../ar/reference/tui.md) · [हिन्दी](../../hi/reference/tui.md) · [বাংলা](../../bn/reference/tui.md) · **Tiếng Việt**

`veles tui` (hoặc `veles` đơn thuần) mở REPL tương tác. Đây là một khung chat có
thể cuộn lại với composer nhiều dòng, một thanh trạng thái, và một trình kiểm tra
có thể thu gọn.

## Phím tắt

| Phím | Hành động |
|---|---|
| `Ctrl+D` | Thoát |
| `Ctrl+C` | Sao chép phản hồi cuối cùng của trợ lý; nhấn hai lần trong 1.5 giây để thoát |
| `Ctrl+V` | Dán từ clipboard |
| `Ctrl+Shift+C` / `⌘C` | Sao chép vùng chọn hiện tại (OSC52). Trên Terminal.app của macOS, kéo chọn gốc + ⌘C hoạt động trực tiếp |
| `Ctrl+I` | Bật/tắt trình kiểm tra (lý luận, hoạt động tool, nhật ký token/lỗi) |
| `Ctrl+R` | Mở trình chọn session (tiếp tục một session đã qua) |
| `Ctrl+T` | Mở trình chọn giao diện |
| `Shift+Tab` | Luân chuyển chế độ chạy: `auto → planning → writing → goal` |
| `Tab` | Luân chuyển các gợi ý hoàn thành lệnh slash |
| `Up` / `Down` | Lịch sử (và lấy ra các prompt đang xếp hàng) |

Các chế độ chạy được giải thích trong [Chế độ chạy](../explanation/modes.md).

## Lệnh slash

Gõ `/` trong composer; `Tab` để hoàn thành. Các lệnh đã đăng ký là:

| Lệnh | Mục đích |
|---|---|
| `/help` | Liệt kê các lệnh có sẵn |
| `/quit`, `/q`, `/exit` | Thoát REPL |
| `/clear` | Xóa nhật ký chat |
| `/model` | Mở trình chọn model |
| `/mode` | Chuyển chế độ chạy (auto/planning/writing/goal) |
| `/session` | Mở trình chọn session (tiếp tục) |
| `/save` | Lưu / đặt tên session hiện tại |
| `/history` | Hiển thị lịch sử session |
| `/tokens` | Mức sử dụng token (vào / ra / mỗi lượt / mỗi session) |
| `/context` | Kích thước ngữ cảnh hiện tại so với giới hạn |
| `/status` | Ảnh chụp nhanh: model, nhà cung cấp, chế độ, session, trạng thái bận, hàng đợi |
| `/insights` | Hiển thị các insight đã học cho dự án |
| `/rules` | Hiển thị bản tóm tắt các quy tắc của dự án |
| `/schema` | Kiểm tra / sửa `AGENTS.md` |
| `/wiki` | Các thao tác wiki cho layout đang hoạt động |
| `/daemon` | Mở bảng điều khiển daemon (dự án → daemon → channel) |

> Bộ lệnh slash là như nhau dù bạn khởi chạy TUI trực tiếp hay đẩy nó từ một màn
> hình khác. Các channel (ví dụ Telegram) phơi bày bộ lệnh riêng, tách biệt của
> chúng.

## Giao diện

Các giao diện tích hợp sẵn: `everforest` (mặc định), `dracula`, `gruvbox`,
`tokyo-night`, `catppuccin`. Chọn một giao diện bằng `Ctrl+T`,
`veles tui --theme <name>`, hoặc `[user] tui_theme` trong `~/.veles/config.toml`.

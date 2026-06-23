# Cách kết nối một kênh Telegram

> 🌐 **Ngôn ngữ:** [English](../../en/how-to/connect-telegram.md) · [简体中文](../../zh-CN/how-to/connect-telegram.md) · [繁體中文](../../zh-TW/how-to/connect-telegram.md) · [日本語](../../ja/how-to/connect-telegram.md) · [한국어](../../ko/how-to/connect-telegram.md) · [Español](../../es/how-to/connect-telegram.md) · [Français](../../fr/how-to/connect-telegram.md) · [Italiano](../../it/how-to/connect-telegram.md) · [Português (BR)](../../pt-BR/how-to/connect-telegram.md) · [Português (PT)](../../pt-PT/how-to/connect-telegram.md) · [Русский](../../ru/how-to/connect-telegram.md) · [العربية](../../ar/how-to/connect-telegram.md) · [हिन्दी](../../hi/how-to/connect-telegram.md) · [বাংলা](../../bn/how-to/connect-telegram.md) · **Tiếng Việt**

Trò chuyện với một dự án Veles từ Telegram. Một kênh (channel) là một gateway
chuyển tiếp tin nhắn tới một [daemon](run-as-daemon.md) và stream các phản hồi trở
lại. Mỗi cuộc trò chuyện có phiên hội thoại riêng của nó.

## Điều kiện tiên quyết

- Một daemon đang chạy (xem [chạy như một daemon](run-as-daemon.md)).
- Một token bot Telegram từ [@BotFather](https://t.me/BotFather).

## Phương án A — gắn qua wizard (khuyến nghị)

Từ trong dự án, chạy wizard cho kênh; nó sẽ ghi config và lưu token vào keychain
của hệ điều hành:

```bash
veles channel add --channel telegram
```

Hoặc gắn vào một phiên daemon có tên cụ thể:

```bash
veles channel add --channel telegram --session api
```

Bạn cũng có thể làm việc này từ [TUI chọn daemon](run-as-daemon.md#the-daemon-picker-tui):
nhấn `c` trên một daemon và làm theo hướng dẫn.

Việc này tạo ra một khối config:

```toml
[channels.telegram]            # hoặc [daemon.api.channels.telegram]
enabled = true
whitelist = ["@alice", "123456789"]
```

**Whitelist** giới hạn ai mà bot trả lời (`@username` Telegram hoặc id người dùng
dạng số). Để trống nếu muốn trả lời tất cả mọi người — không khuyến nghị, vì mỗi tin
nhắn đều tiêu tốn token của model.

Khởi động lại daemon để áp dụng:

```bash
veles daemon restart
```

## Phương án B — chạy một gateway độc lập

Nếu bạn thích một tiến trình riêng (thay vì kênh nằm trong daemon), hãy chạy:

```bash
export TELEGRAM_BOT_TOKEN=123456:ABC...
veles channel run --channel telegram \
  --daemon-url http://127.0.0.1:8765 \
  --daemon-token "$(veles daemon token add tg)"
```

## Quản lý các phiên trò chuyện

```bash
veles channel list                       # các nền tảng đã đăng ký + số lượng phiên
veles channel list-sessions              # ánh xạ chat_id → session_id
veles channel reset-session <chat_id>    # tin nhắn tiếp theo từ chat đó bắt đầu mới
veles channel remove telegram            # bỏ liên kết kênh
```

## Hạn chế đa phương thức (multimodal)

Việc gửi một **ảnh hoặc tin nhắn thoại** hiện trả về thông báo "not configured".
Veles có định nghĩa các protocol adapter `VisionAdapter` / STT và một registry
(`modules/vision.py`, `modules/stt.py`), nhưng **không có adapter cụ thể nào được
ship và không có cái nào được đăng ký lúc daemon khởi động**, nên ảnh và âm thanh
chưa được phân tích. Trò chuyện văn bản hoạt động đầy đủ. Xem
[tham chiếu provider](../reference/providers.md#multimodal-status-vision--speech-to-text).

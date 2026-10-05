# Cách kết nối một kênh Telegram

> 🌐 **Ngôn ngữ:** [English](../../en/how-to/connect-telegram.md) · [简体中文](../../zh-CN/how-to/connect-telegram.md) · [繁體中文](../../zh-TW/how-to/connect-telegram.md) · [日本語](../../ja/how-to/connect-telegram.md) · [한국어](../../ko/how-to/connect-telegram.md) · [Español](../../es/how-to/connect-telegram.md) · [Français](../../fr/how-to/connect-telegram.md) · [Italiano](../../it/how-to/connect-telegram.md) · [Português (BR)](../../pt-BR/how-to/connect-telegram.md) · [Português (PT)](../../pt-PT/how-to/connect-telegram.md) · [Русский](../../ru/how-to/connect-telegram.md) · [العربية](../../ar/how-to/connect-telegram.md) · [हिन्दी](../../hi/how-to/connect-telegram.md) · [বাংলা](../../bn/how-to/connect-telegram.md) · **Tiếng Việt**

Trò chuyện với một dự án Veles từ Telegram. Một kênh (channel) là một gateway
chuyển tiếp tin nhắn tới một [daemon](run-as-daemon.md) và stream các phản hồi trở
lại. Mỗi cuộc trò chuyện có phiên hội thoại riêng của nó.

Telegram là một module từ registry mở rộng chính thức (`official/telegram`), không thuộc
lõi Veles. Bạn không cần cài thủ công: `veles channel add` sẽ đề nghị cài, và một khối
`[channels.telegram]` trong cấu hình sẽ cài nó ở lần `veles daemon start` kế tiếp — bạn đã
khai báo kênh, nên đó chính là sự đồng ý. Nó chỉ được cài từ các registry bạn đã kết nối.

## Điều kiện tiên quyết

- Một dự án Veles (daemon chỉ khởi động với một kênh hoạt động — đây là một kênh như vậy).
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

Khởi động (hoặc khởi động lại) daemon để áp dụng:

```bash
veles daemon start      # or: veles daemon restart
```

Viết khối bằng tay cũng hoạt động tương tự. Hãy đặt token vào keychain bằng
`veles channel add`, hoặc vào khối dưới dạng `bot_token = "…"`; nếu thiếu token, daemon
từ chối khởi động và nêu tên lệnh để khắc phục.

## Phương án B — chạy một gateway độc lập

Nếu bạn thích một tiến trình riêng (thay vì kênh nằm trong daemon), hãy chạy:

```bash
export TELEGRAM_BOT_TOKEN=123456:ABC...   # or pass --secret
veles channel run --channel telegram \
  --daemon-url http://127.0.0.1:8765 \
  --daemon-token "$(veles daemon token add tg)"
```

`veles channel run --channel telegram` sẽ cài module trước nếu nó chưa có.

Daemon mà nó kết nối tới chỉ khởi động khi có sẵn một channel riêng của nó, nên cách này phù hợp với một daemon đã host một channel khác. Đừng chạy cùng một bot ở cả hai nơi: Telegram chỉ giao các cập nhật của một bot cho một poller, nên cái thứ hai sẽ thất bại.

## Quản lý các phiên trò chuyện

```bash
veles channel list                       # các nền tảng đã đăng ký + số lượng phiên
veles channel list-sessions              # ánh xạ chat_id → session_id
veles channel reset-session <chat_id>    # tin nhắn tiếp theo từ chat đó bắt đầu mới
veles channel remove telegram            # bỏ liên kết kênh
```

## Chế độ của agent trong cuộc trò chuyện

`/mode` chuyển chế độ của agent trong cuộc trò chuyện: `default` (agent trả lời
trực tiếp, như trước khi chuyển), `auto` (với mỗi tin nhắn tự quyết có lập kế
hoạch trước không), `planning` (chỉ lập kế hoạch, không thay đổi gì) và `writing`
(hành động bằng công cụ của nó). Chế độ hiện tại được đánh dấu. Lựa chọn có hiệu
lực đến khi daemon khởi động lại. Dòng trạng thái của chế độ, ví dụ
*auto → plan*, hiện phía trên câu trả lời.

`/goal <nhiệm vụ>` chạy một mục tiêu ngay trong cuộc trò chuyện. Agent hỏi những
gì nó cần biết và cho xem kế hoạch sẽ làm theo. Khi bạn trả lời `yes`, nó tự làm
và gửi một dòng sau mỗi bước, cho đến khi đạt mục tiêu hoặc hết ngân sách. Yêu cầu
phê duyệt vẫn đến dưới dạng nút bấm. `/goal` cho xem tiến độ, `/goal cancel` dừng
sau bước hiện tại, còn `/goal resume` tiếp tục một mục tiêu đã dừng.

Khi agent cần một chi tiết mà chỉ bạn biết, nó sẽ hỏi trong cuộc trò chuyện.
Chạm vào một câu trả lời gợi ý hoặc tự nhập câu trả lời. Nếu bạn không trả lời
trong năm phút, nó tiếp tục theo giả định hợp lý nhất và nói rõ đã giả định gì.

`/settings` hiển thị trong một tin nhắn model (cố định theo cấu hình của daemon), phiên của
cuộc trò chuyện, mức dùng token và các nút chế độ. `/tokens` hiển thị mức dùng token của phiên
kể từ khi daemon khởi động; `/context` cho biết cửa sổ ngữ cảnh của model đã đầy đến đâu.

## Hạn chế đa phương thức (multimodal)

Việc gửi một **ảnh hoặc tin nhắn thoại** hiện trả về thông báo "not configured".
Veles có định nghĩa các protocol adapter `VisionAdapter` / STT và một registry
(`modules/vision.py`, `modules/stt.py`), nhưng **không có adapter cụ thể nào được
ship và không có cái nào được đăng ký lúc daemon khởi động**, nên ảnh và âm thanh
chưa được phân tích. Trò chuyện văn bản hoạt động đầy đủ. Xem
[tham chiếu provider](../reference/providers.md#multimodal-status-vision--speech-to-text).

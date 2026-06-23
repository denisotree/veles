# Cách chạy Veles dưới dạng daemon

> 🌐 **Ngôn ngữ:** [English](../../en/how-to/run-as-daemon.md) · [简体中文](../../zh-CN/how-to/run-as-daemon.md) · [繁體中文](../../zh-TW/how-to/run-as-daemon.md) · [日本語](../../ja/how-to/run-as-daemon.md) · [한국어](../../ko/how-to/run-as-daemon.md) · [Español](../../es/how-to/run-as-daemon.md) · [Français](../../fr/how-to/run-as-daemon.md) · [Italiano](../../it/how-to/run-as-daemon.md) · [Português (BR)](../../pt-BR/how-to/run-as-daemon.md) · [Português (PT)](../../pt-PT/how-to/run-as-daemon.md) · [Русский](../../ru/how-to/run-as-daemon.md) · [العربية](../../ar/how-to/run-as-daemon.md) · [हिन्दी](../../hi/how-to/run-as-daemon.md) · [বাংলা](../../bn/how-to/run-as-daemon.md) · **Tiếng Việt**

Daemon là một máy chủ HTTP+WS tùy chọn chạy lâu dài, phơi bày agent dưới dạng một
API — nền tảng cho [channels](connect-telegram.md) (Telegram, …), các
[job](long-running-tasks.md) được lên lịch, và việc dùng từ xa/headless.

## Khởi động và dừng

```bash
veles daemon start              # detaches by default; binds 127.0.0.1:8765
veles daemon status             # is it running?
veles daemon stop               # SIGTERM via the pid file
```

`start` tách tiến trình và trả lại shell cho bạn. Để có một tiến trình foreground
(systemd `Type=simple`, Docker, gỡ lỗi) hãy truyền `--foreground`. Ghi đè bind:

```bash
veles daemon start --host 0.0.0.0 --port 9000
```

Model và nhà cung cấp của daemon lấy từ config dự án và **cố định trong suốt vòng
đời của nó** — hãy đặt chúng trước khi khởi động:

```toml
# <project>/.veles/config.toml
[provider]
default = "ollama"            # provider name
model = "qwen3:4b-instruct"   # model id
```

## Token xác thực

Client API xác thực bằng một bearer token:

```bash
veles daemon token add tui-client     # mint a token
veles daemon token list               # list (masked)
veles daemon token remove tui-client
```

## Trình chọn daemon (TUI)

Chạy `veles daemon` không kèm lệnh con để mở bảng điều khiển — một cây gồm các
daemon của dự án và các channel của từng daemon:

```
Project: my-project
  default   running  pid=…  up 1.2h  qwen3:4b-instruct
    chan: telegram
  api       stopped
Other projects
  other-proj  running
```

Các phím: `Enter` mở log của một daemon; `s`/`t`/`r` start/stop/restart; `d`
xóa; `c`/`x` thêm/gỡ một channel; `q` thoát.

## Nhiều daemon cho mỗi dự án (session có tên)

Một dự án có thể chạy đồng thời nhiều daemon với các model/cổng khác nhau. Khai
báo một session có tên, rồi khởi động nó:

```bash
veles daemon session create api --port 8801 --provider anthropic --model claude-opus-4.8
veles daemon start --name api
veles daemon session list
```

Mỗi session có tên có khối config `[daemon.<name>]` riêng và các channel riêng
(`[daemon.<name>.channels.*]`).

## Liệt kê các daemon trên các dự án

```bash
veles daemon list
veles daemon restart <project-or-slug>
veles daemon delete  <project-or-slug>
```

## Tiếp theo

- [Kết nối một channel Telegram](connect-telegram.md)
- [Lên lịch các job](long-running-tasks.md)

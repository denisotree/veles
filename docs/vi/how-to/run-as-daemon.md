# Cách chạy Veles dưới dạng daemon

> 🌐 **Ngôn ngữ:** [English](../../en/how-to/run-as-daemon.md) · **Tiếng Việt**

Daemon là một máy chủ HTTP+WS tùy chọn, chạy lâu dài, đưa agent ra ngoài dưới dạng
API — nền tảng cho các [kênh](connect-telegram.md) (Telegram, …), các
[tác vụ](long-running-tasks.md) được lên lịch, cũng như việc sử dụng từ xa/headless.

## Khởi động và dừng

```bash
veles daemon start              # detaches by default; binds 127.0.0.1:8765
veles daemon status             # is it running?
veles daemon stop               # SIGTERM via the pid file
```

`start` tách tiến trình ra nền và trả lại shell cho bạn. Để chạy ở tiền cảnh
(systemd `Type=simple`, Docker, gỡ lỗi) hãy truyền `--foreground`. Ghi đè địa chỉ bind:

```bash
veles daemon start --host 0.0.0.0 --port 9000
```

Model và provider của daemon được lấy từ cấu hình dự án và **cố định trong suốt
vòng đời** của nó — hãy thiết lập chúng trước khi khởi động:

```toml
# <project>/.veles/config.toml
[provider]
default = "ollama:qwen3:4b-instruct"
```

## Token xác thực

Các client API xác thực bằng bearer token:

```bash
veles daemon token add tui-client     # mint a token
veles daemon token list               # list (masked)
veles daemon token remove tui-client
```

## Bộ chọn daemon (TUI)

Chạy `veles daemon` không kèm subcommand để mở bảng điều khiển — một cây liệt kê
các daemon của dự án và các kênh của từng daemon:

```
Project: my-project
  default   running  pid=…  up 1.2h  qwen3:4b-instruct
    chan: telegram
  api       stopped
Other projects
  other-proj  running
```

Phím: `Enter` mở log của daemon; `s`/`t`/`r` start/stop/restart; `d` xóa;
`c`/`x` thêm/gỡ một kênh; `q` thoát.

## Nhiều daemon cho mỗi dự án (named session)

Một dự án có thể chạy đồng thời nhiều daemon với các model/cổng khác nhau. Khai báo
một named session, rồi khởi động nó:

```bash
veles daemon session create api --port 8801 --provider anthropic --model claude-opus-4.8
veles daemon start --name api
veles daemon session list
```

Mỗi named session có khối cấu hình `[daemon.<name>]` riêng và các kênh riêng
(`[daemon.<name>.channels.*]`).

## Liệt kê daemon trên nhiều dự án

```bash
veles daemon list
veles daemon restart <project-or-slug>
veles daemon delete  <project-or-slug>
```

## Tiếp theo

- [Kết nối kênh Telegram](connect-telegram.md)
- [Lên lịch tác vụ](long-running-tasks.md)

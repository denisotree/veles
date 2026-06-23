# Cách quản lý bảo mật: trust, autopilot, secret

> 🌐 **Ngôn ngữ:** [English](../../en/how-to/security-and-permissions.md) · **Tiếng Việt**

Veles kiểm soát các hành động nguy hiểm thông qua một **thang trust**, đặt việc
truy cập tệp trong sandbox, và giữ secret trong keychain của hệ điều hành. Để hiểu
lý do, xem [trust & sandbox](../explanation/trust-and-sandbox.md).

## Thang trust

Các công cụ nhạy cảm (`run_shell`, `write_file`, `fetch_url`, …) sẽ hỏi trước khi
chạy. Bạn chọn: cho phép **một lần**, **luôn luôn cho dự án này**, **luôn luôn ở mọi
nơi**, hoặc **từ chối**. Các quyền được cấp sẽ được lưu lại nên bạn không bị hỏi lại.

Quản lý các quyền đã cấp mà không cần đợi lời nhắc:

```bash
veles trust list                          # current grants (user + project)
veles trust set run_shell --scope project # pre-grant for this project
veles trust set write_file --scope user   # pre-grant everywhere
veles trust revoke run_shell              # remove a grant
veles trust clear --scope all             # wipe everything
```

Một số hành động **luôn được xác nhận lại** ngay cả khi đã được cấp quyền — xóa
tệp, tải URL, cài đặt một skill/tool/module mới, kết nối một kênh, và ghi
ra ngoài phạm vi dự án.

## Autopilot — bỏ qua trong khung thời gian giới hạn

Đối với một lần chạy không giám sát (một batch chạy qua đêm), hãy mở một khung thời
gian mà các lời nhắc trust được tự động cho phép:

```bash
veles autopilot enable --until +2h
veles autopilot enable --until 2026-12-31T23:00:00Z
veles autopilot status
veles autopilot disable
```

Mọi hành động autopilot đều được ghi log để xem lại sau. Các ngữ cảnh không tương
tác (daemon, batch) mặc định từ chối, trừ khi autopilot đang bật.

## Secret

API key và bot token nằm trong keychain của hệ điều hành, không bao giờ nằm trong
các tệp cấu hình:

```bash
veles secret set OPENROUTER_API_KEY       # prompts (or pipe via stdin)
veles secret list                         # which secrets are configured
veles secret get OPENROUTER_API_KEY --reveal
veles secret delete OPENROUTER_API_KEY
```

Việc tra cứu sẽ dự phòng về [biến môi trường](../reference/environment-variables.md)
tương ứng, trừ khi bạn truyền `--no-env-fallback`.

## Sandbox

Các công cụ có thể đọc bên trong dự án đang hoạt động và `~/.veles/`, và chỉ ghi
được vào các vùng cho phép ghi của layout (mặc định là `wiki/`, `.veles/`). Ghi đè
các root cho những thiết lập nâng cao bằng `VELES_SANDBOX_ROOTS` (ngăn cách bằng
`:`). Việc tải URL duy trì một danh sách chặn SSRF; `VELES_FETCH_ALLOW_PRIVATE=1`
gỡ bỏ chặn mạng riêng (private network).

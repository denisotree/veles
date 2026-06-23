# Tin cậy & sandbox

> 🌐 **Ngôn ngữ:** [English](../../en/explanation/trust-and-sandbox.md) · [简体中文](../../zh-CN/explanation/trust-and-sandbox.md) · [繁體中文](../../zh-TW/explanation/trust-and-sandbox.md) · [日本語](../../ja/explanation/trust-and-sandbox.md) · [한국어](../../ko/explanation/trust-and-sandbox.md) · [Español](../../es/explanation/trust-and-sandbox.md) · [Français](../../fr/explanation/trust-and-sandbox.md) · [Italiano](../../it/explanation/trust-and-sandbox.md) · [Português (BR)](../../pt-BR/explanation/trust-and-sandbox.md) · [Português (PT)](../../pt-PT/explanation/trust-and-sandbox.md) · [Русский](../../ru/explanation/trust-and-sandbox.md) · [العربية](../../ar/explanation/trust-and-sandbox.md) · [हिन्दी](../../hi/explanation/trust-and-sandbox.md) · [বাংলা](../../bn/explanation/trust-and-sandbox.md) · **Tiếng Việt**

Veles chạy một agent tự chủ trên máy của bạn, nên nó giới hạn những gì agent đó có
thể làm. Hai cơ chế phối hợp với nhau: một **bậc thang tin cậy** (trust ladder) cho
các hành động nhạy cảm và một **sandbox** cho hệ thống tệp. Để biết các lệnh, xem
[bảo mật & quyền hạn](../how-to/security-and-permissions.md).

## Bậc thang tin cậy

Không phải công cụ nào cũng như nhau. Đọc một tệp là vô hại; chạy một lệnh shell
hay ghi lên đĩa thì không. Các công cụ nhạy cảm (`run_shell`, `write_file`,
`fetch_url`, …) sẽ dừng lại và hỏi trước khi chạy, cung cấp bốn lựa chọn:

- **Once** — cho phép đúng một lần gọi này.
- **Always for this project** — lưu một quyền cấp ở phạm vi dự án.
- **Always everywhere** — lưu một quyền cấp ở phạm vi người dùng.
- **Refuse** — từ chối.

Các quyền cấp được lưu lại để bạn không bị hỏi lại. Điều này cho bạn quyền kiểm
soát theo cấp độ: tin cậy một công cụ một lần, trong một dự án, hay trên toàn cục —
tùy bạn chọn, ngay lần đầu nó trở nên quan trọng.

### Các hành động luôn xác nhận

Một số thao tác đủ rủi ro để Veles xác nhận chúng **ngay cả khi đã có quyền cấp**:
xóa tệp, lấy nội dung từ URL, cài đặt một kỹ năng/công cụ/module mới, kết nối một
kênh, và ghi ra ngoài phạm vi dự án. Đây là những hành động hướng ra ngoài hoặc khó
hoàn tác, nên một quyền cấp thường trực không nên âm thầm bao trùm chúng.

### An toàn ở chế độ không tương tác

Trong một daemon, batch, hay ngữ cảnh không-TTY khác, không có con người để hỏi,
nên Veles mặc định **từ chối** các hành động nhạy cảm — một luồng stdin lạc lối
không thể lén lút chèn vào một sự phê duyệt. Để cố ý chạy không giám sát, hãy mở một
cửa sổ [autopilot](../how-to/security-and-permissions.md#autopilot--a-time-boxed-bypass);
mọi hành động autopilot đều được ghi log để xem lại.

## Sandbox cho hệ thống tệp

Một bộ canh đường dẫn (path guard) giới hạn nơi công cụ có thể đọc và ghi:

- **Đọc** — bên trong dự án đang hoạt động (và các subproject của nó) cộng với
  `~/.veles/`.
- **Ghi** — chỉ trong các vùng ghi được của layout (ví dụ `wiki/`); `.veles/` luôn
  ghi được để lưu trạng thái máy.

Các symlink thoát khỏi sandbox sẽ bị từ chối, và việc duyệt `..` bị từ chối trước
khi resolve. Việc lấy nội dung URL duy trì một danh sách chặn SSRF. Các thiết lập
nâng cao có thể ghi đè các gốc bằng `VELES_SANDBOX_ROOTS`, hoặc gỡ bỏ chặn mạng nội
bộ bằng `VELES_FETCH_ALLOW_PRIVATE=1` — cả hai đều phải bật thủ công (opt-in).

## Vì sao thiết kế như vậy

Mục tiêu là **tự chủ hữu ích mà không có những bất ngờ khó chịu**: agent có thể làm
việc thực sự mà không cần hỏi ở mỗi lần đọc, nhưng bất cứ điều gì có thể gây hại cho
máy, tiêu tốn tiền, hay rời khỏi máy đều được kiểm soát — một lần, rồi được ghi nhớ
theo ý thích của bạn.

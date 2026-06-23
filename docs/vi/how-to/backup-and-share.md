# Cách sao lưu và chia sẻ một dự án

> 🌐 **Ngôn ngữ:** [English](../../en/how-to/backup-and-share.md) · [简体中文](../../zh-CN/how-to/backup-and-share.md) · [繁體中文](../../zh-TW/how-to/backup-and-share.md) · [日本語](../../ja/how-to/backup-and-share.md) · [한국어](../../ko/how-to/backup-and-share.md) · [Español](../../es/how-to/backup-and-share.md) · [Français](../../fr/how-to/backup-and-share.md) · [Italiano](../../it/how-to/backup-and-share.md) · [Português (BR)](../../pt-BR/how-to/backup-and-share.md) · [Português (PT)](../../pt-PT/how-to/backup-and-share.md) · [Русский](../../ru/how-to/backup-and-share.md) · [العربية](../../ar/how-to/backup-and-share.md) · [हिन्दी](../../hi/how-to/backup-and-share.md) · [বাংলা](../../bn/how-to/backup-and-share.md) · **Tiếng Việt**

Các dự án Veles có thể di chuyển được. Hãy export một dự án thành một gói `.tar.gz`
duy nhất để sao lưu hoặc di trú, hoặc thành một template đã được làm sạch để chia sẻ
mà không rò rỉ dữ liệu của bạn.

## Sao lưu đầy đủ

Đóng gói toàn bộ dự án (`.veles/` + `AGENTS.md`), trừ các thứ tạm thời lúc chạy
(lock, trạng thái ngân sách):

```bash
veles export full ./my-project-backup.tar.gz
```

Khôi phục ở bất cứ đâu:

```bash
veles import ./my-project-backup.tar.gz                # vào thư mục hiện tại
veles import ./my-project-backup.tar.gz --into ./restored
veles import ./my-project-backup.tar.gz --force        # ghi đè .veles/ đang có
```

Một gói đầy đủ bao gồm cả `memory.db` của bạn (phiên làm việc, insight), nên hãy đối
xử với nó như dữ liệu riêng tư.

## Template chia sẻ được

Chỉ đóng gói phần khung tái sử dụng được — schema, kỹ năng, module, và các trang
wiki không thuộc phiên. Nó **loại bỏ** `memory.db`, `sources/`, `sessions/`, các
quyền tin cậy, và che (PII-redact) văn bản:

```bash
veles export template ./my-template.tar.gz
```

Đưa template cho một đồng nghiệp; họ chạy `veles import` và nhận được cấu trúc cùng
kỹ năng của bạn mà không có lịch sử hội thoại hay nguồn thô của bạn.

## Nên dùng cái nào

| Mục tiêu | Lệnh |
|---|---|
| Sao lưu / di chuyển nguyên vẹn một dự án | `veles export full` |
| Chia sẻ cấu trúc + kỹ năng, không phải dữ liệu | `veles export template` |

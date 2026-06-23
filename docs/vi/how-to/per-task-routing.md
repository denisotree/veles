# Cách định tuyến tác vụ tới các model khác nhau

> 🌐 **Ngôn ngữ:** [English](../../en/how-to/per-task-routing.md) · [Русский](../../ru/how-to/per-task-routing.md) · **Tiếng Việt**

Veles không bị gắn chặt với một model duy nhất. Mỗi **tác vụ (task)** nội bộ có thể sử dụng một
`provider:model` khác nhau — một model rẻ cho việc nén ngữ cảnh, một model mạnh cho
agent chính, một model vision cho hình ảnh. Đây là hệ thống *định tuyến ensemble (ensemble routing)*.

## Các loại tác vụ

| Tác vụ | Dùng cho |
|---|---|
| `default` | Vòng lặp agent chính |
| `curator` | Củng cố session → wiki |
| `compressor` | Nén ngữ cảnh theo cửa sổ trượt |
| `insights` | Trích xuất insight sau khi chạy |
| `skills` | Thực thi skill |
| `advisor` | Tự kiểm tra `advisor_review` |
| `vision` | `image_describe` (khi một adapter vision được kết nối) |
| `embedding` | Tính tương đồng cho `veles skill dedup` |

## Xem định tuyến hiện tại

```bash
veles route show
```

Lệnh này in ra `provider:model` đã được phân giải cho mỗi tác vụ và một nhãn `source`
cho biết lớp nào đã quyết định nó.

## Gắn một tác vụ với một model

```bash
veles route set compressor openrouter:anthropic/claude-haiku-4.5
veles route set advisor    openrouter:anthropic/claude-opus-4.8
veles route set vision     openai:gpt-4o
```

Các lệnh này ghi `[routing.tasks]` vào `<project>/.veles/config.toml`:

```toml
[routing.tasks]
compressor = "openrouter:anthropic/claude-haiku-4.5"
advisor    = "openrouter:anthropic/claude-opus-4.8"
vision     = "openai:gpt-4o"
```

## Đặt lại

```bash
veles route reset compressor   # one task back to default
veles route reset              # all tasks back to default
```

## Gợi ý bằng ngôn ngữ tự nhiên trong AGENTS.md

Bạn có thể diễn đạt định tuyến bằng văn xuôi trong `AGENTS.md` (ví dụ "use a cheap model for
compression"). Veles phân tích cú pháp những gợi ý này thành một tệp `routing.nl.toml` được tạo tự động:

```bash
veles route refresh            # re-parse AGENTS.md hints
veles route refresh --force    # even if AGENTS.md hasn't changed
```

Các mục `[routing.tasks]` được khai báo tường minh luôn thắng các gợi ý NL.

## Thứ tự phân giải

Đối với mỗi tác vụ, lớp đầu tiên cho ra một spec sẽ thắng:

1. `[routing.tasks][task]` của dự án
2. `[routing.tasks].default` của dự án
3. gợi ý NL của dự án (`routing.nl.toml`)
4. nền tảng `[provider]` của dự án
5. `[routing.tasks][task]` / `.default` của người dùng
6. `[user] default_provider` + `default_model` của người dùng
7. mặc định tích hợp sẵn cho tác vụ đó

(`embedding` bỏ qua các lớp dự phòng tổng quát — một chat model không phải là một embedding model.)

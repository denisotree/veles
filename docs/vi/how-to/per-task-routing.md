# Cách định tuyến các tác vụ tới các model khác nhau

> 🌐 **Languages:** **English** · [Русский](../../ru/how-to/per-task-routing.md)

Veles không bị ghim vào một model duy nhất. Mỗi **tác vụ** nội bộ có thể dùng một
`provider:model` khác nhau — một model rẻ cho việc nén ngữ cảnh, một model mạnh
cho agent chính, một model vision cho ảnh. Đây là hệ thống *định tuyến ensemble*.

## Các loại tác vụ

| Tác vụ | Dùng cho |
|---|---|
| `default` | Vòng lặp agent chính |
| `curator` | Củng cố session → wiki |
| `compressor` | Nén ngữ cảnh kiểu sliding-window |
| `insights` | Trích xuất insight sau khi chạy |
| `skills` | Thực thi skill |
| `advisor` | Tự kiểm tra `advisor_review` |
| `vision` | `image_describe` (khi một vision adapter được kết nối) |
| `embedding` | Tính tương đồng cho `veles skill dedup` |

## Xem định tuyến hiện tại

```bash
veles route show
```

Lệnh này in ra `provider:model` đã được giải quyết cho mỗi tác vụ và một nhãn
`source` cho biết lớp nào đã quyết định nó.

## Ghim một tác vụ vào một model

```bash
veles route set compressor openrouter:anthropic/claude-haiku-4.5
veles route set advisor    openrouter:anthropic/claude-opus-4.8
veles route set vision     openai:gpt-4o
```

Các lệnh này ghi `[routing.tasks]` trong `<project>/.veles/config.toml`:

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

Bạn có thể diễn đạt việc định tuyến bằng văn xuôi trong `AGENTS.md` (ví dụ "dùng
một model rẻ cho việc nén"). Veles phân tích các gợi ý này thành một
`routing.nl.toml` tự sinh:

```bash
veles route refresh            # re-parse AGENTS.md hints
veles route refresh --force    # even if AGENTS.md hasn't changed
```

Các mục `[routing.tasks]` tường minh luôn thắng các gợi ý NL.

## Thứ tự giải quyết

Với mỗi tác vụ, lớp đầu tiên cho ra một spec sẽ thắng:

1. `[routing.tasks][task]` của dự án
2. `[routing.tasks].default` của dự án
3. gợi ý NL của dự án (`routing.nl.toml`)
4. `[provider]` cơ sở của dự án
5. `[routing.tasks][task]` / `.default` của user
6. `[user] default_provider` + `default_model` của user

Nếu không lớp nào giải quyết được, **không có fallback cứng** — tác vụ được để
trống và bên gọi nó suy giảm chức năng (bỏ qua tính năng) hoặc báo lỗi rõ ràng,
thay vì âm thầm với tới một model đám mây.

(`embedding` bỏ qua các lớp catch-all — một chat model không phải là một embedding
model — nên chỉ một `[routing.tasks].embedding` tường minh mới đáp ứng được nó.)

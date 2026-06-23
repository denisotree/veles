# Cách làm việc với nhiều dự án và dự án con

> 🌐 **Ngôn ngữ:** [English](../../en/how-to/multi-project-and-subprojects.md) · [Русский](../../ru/how-to/multi-project-and-subprojects.md) · **Tiếng Việt**

Veles chạy nhiều dự án trong một vòng lặp agent. Mỗi dự án có bộ nhớ, skill, và tool
riêng. **Dự án con (subprojects)** là các dự án lồng bên trong một dự án cha — hữu ích để
phân rã một monorepo hoặc cơ sở tri thức lớn thành các bộ nhớ có phạm vi.

## Projects

Veles phát hiện dự án đang hoạt động bằng cách đi ngược lên từ thư mục làm việc hiện tại (cwd) của bạn đến một thư mục `.veles/`
(giống như `git`). Quản lý registry:

```bash
veles project list                  # registered projects, most-recent first
veles project add /path/to/project  # register an existing project
veles project add /path --slug web  # with a custom slug
veles project remove <slug>         # unregister (files untouched)
```

`switch` in ra một đường dẫn, để bạn có thể `cd` vào một dự án:

```bash
cd "$(veles project switch web)"
```

Chạy một lệnh trên một dự án ở nơi khác mà không cần `cd`:

```bash
veles run --project-root /path/to/project "..."
```

## Subprojects

Một subproject là một dự án Veles con nằm bên trong một dự án cha. Tạo một dự án con:

```bash
veles subproject init frontend --description "the web client"
veles subproject list
cd "$(veles subproject switch frontend)"
veles subproject remove frontend    # unregister (files untouched)
```

### Để Veles đề xuất cách phân tách

Khi wiki của một dự án phình to, Veles có thể phát hiện các cụm chủ đề và đề xuất chúng
dưới dạng các dự án con:

```bash
veles subproject suggest            # print candidates
veles subproject suggest --save     # save each to .veles/memory/proposals/ for recall
```

## Khi nào dùng cái nào

- **Dự án riêng biệt** — các cơ sở tri thức / codebase không liên quan đến nhau.
- **Dự án con** — các phần của một thực thể lớn hơn được hưởng lợi từ bộ nhớ có phạm vi nhưng
  chia sẻ một ngữ cảnh cha.

Xem [kiến trúc](../explanation/architecture.md) để biết cách ngữ cảnh đa dự án được
nạp theo nhu cầu thay vì như một khối nguyên khối duy nhất.

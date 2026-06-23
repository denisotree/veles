# Cách quản lý skills, tools, và modules

> 🌐 **Ngôn ngữ:** [English](../../en/how-to/manage-skills-and-tools.md) · [Русский](../../ru/how-to/manage-skills-and-tools.md) · **Tiếng Việt**

Veles tích lũy năng lực theo thời gian. **Skills** là các quy trình làm việc có thể tái sử dụng,
**tools** là các hành động có thể thực thi, **modules** là các plug-in tùy chọn. Mỗi loại tồn tại ở
hai phạm vi: cục bộ theo dự án (`<project>/.veles/`) và toàn cục theo người dùng (`~/.veles/`). Về
các khái niệm, xem [skills & tools](../explanation/skills-and-tools.md).

## Skills

Một skill là một tệp `SKILL.md` (frontmatter + phần thân prompt) mà agent có thể gọi như một
công cụ.

```bash
veles skill list                          # installed skills + telemetry
veles skill show <name>                   # print its SKILL.md
veles skill add https://github.com/org/skill.git
veles skill add ./local-skill --scope user   # install user-global
veles skill remove <name>
```

### Thăng cấp / hạ cấp giữa các phạm vi

Một skill chứng tỏ hữu ích trong một dự án có thể được chuyển sang phạm vi người dùng để mọi dự án
đều thấy nó (hoặc ngược lại):

```bash
veles skill promote <name>     # project → ~/.veles/skills/
veles skill demote  <name>     # user → this project
```

### Tìm các bản trùng lặp và các ứng viên để thăng cấp

```bash
veles skill dedup                         # near-duplicate skills (embedding/TF-IDF)
veles skill suggest-promote --save        # skills that meet the auto-promote bar
```

## Tools

Các tool được lập danh mục trong `memory.db` của dự án kèm theo dữ liệu telemetry về cách sử dụng. Veles có thể
tự viết các tool của riêng nó trong khi làm việc; bạn quản lý chúng bằng:

```bash
veles tool list                # tools in this project
veles tool show <name>         # manifest + telemetry
veles tool promote <name>      # move to ~/.veles/tools/ (cross-project)
```

Các tool nhạy cảm (`run_shell`, `write_file`, `fetch_url`, …) được kiểm soát bởi
[thang tin cậy](security-and-permissions.md).

## Modules

Modules bổ sung các năng lực tùy chọn (embeddings, vision, STT) mà không làm phình to phần
lõi. Việc cài đặt một module yêu cầu xác nhận theo mặc định.

```bash
veles module list
veles module add https://github.com/org/module.git
veles module remove <name>
```

## Khám phá thêm

Duyệt qua các registry được tuyển chọn:

```bash
veles browse skills [query]
veles browse modules [query]
```

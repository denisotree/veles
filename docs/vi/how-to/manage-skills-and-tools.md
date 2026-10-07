# Cách quản lý skills, tools, và modules

> 🌐 **Ngôn ngữ:** [English](../../en/how-to/manage-skills-and-tools.md) · [简体中文](../../zh-CN/how-to/manage-skills-and-tools.md) · [繁體中文](../../zh-TW/how-to/manage-skills-and-tools.md) · [日本語](../../ja/how-to/manage-skills-and-tools.md) · [한국어](../../ko/how-to/manage-skills-and-tools.md) · [Español](../../es/how-to/manage-skills-and-tools.md) · [Français](../../fr/how-to/manage-skills-and-tools.md) · [Italiano](../../it/how-to/manage-skills-and-tools.md) · [Português (BR)](../../pt-BR/how-to/manage-skills-and-tools.md) · [Português (PT)](../../pt-PT/how-to/manage-skills-and-tools.md) · [Русский](../../ru/how-to/manage-skills-and-tools.md) · [العربية](../../ar/how-to/manage-skills-and-tools.md) · [हिन्दी](../../hi/how-to/manage-skills-and-tools.md) · [বাংলা](../../bn/how-to/manage-skills-and-tools.md) · **Tiếng Việt**

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

Một module là mã Python (`module.toml` + một entrypoint) chạy bên trong Veles — bổ sung
các năng lực tùy chọn (memory provider, embeddings, vision, STT) mà không làm phình to
phần lõi. Việc cài đặt một module yêu cầu xác nhận theo mặc định, và nó chỉ được nạp
ở mỗi lần chạy khi các tệp của nó vẫn khớp với những gì bạn đã duyệt (xem [giữ các
bản cài đặt trung thực](../../en/how-to/extension-registries.md#keep-installs-honest)).

```bash
veles module list                              # cả hai phạm vi, kèm cột `scope`
veles module add https://github.com/org/module.git
veles module add ./local-module --user          # cài vào ~/.veles/modules/, dùng cho mọi dự án
veles module show <name> [--user]             # manifest + sha256 của các tệp
veles module remove <name> [--user]
veles module approve <name> [--user]          # gõ `yes` trong terminal
veles module approve <name> --sha256 <hash>   # không có terminal: hash bạn đã xem lại
```

Modules nằm ở hai phạm vi, giống skills và tools: cục bộ theo dự án
(`<project>/.veles/modules/`) và toàn cục theo người dùng (`~/.veles/modules/`, được
nạp ở mọi dự án). Một module cấp người dùng đi qua cùng cổng phê duyệt như module của
dự án, và cổng này chạy trước khi so sánh tên. Nếu một module dự án và một module
người dùng trùng tên, module dự án đã duyệt sẽ được nạp và Veles cảnh báo module cấp
người dùng bị che khuất; module dự án chưa duyệt bị bỏ qua (cảnh báo nêu thư mục của
nó) và module người dùng được nạp. Hai module đã duyệt cùng phạm vi trùng tên — module
đầu tiên (sắp theo thư mục) được nạp, các module còn lại cảnh báo và bị bỏ qua. `veles
module {show,approve,remove}` nhận tên trong manifest (cái `list` hiển thị) và từ chối
một tên được nhiều hơn một thư mục trong phạm vi khai báo, đồng thời liệt kê chúng;
`veles module add` từ chối cài một module có tên mà một thư mục khác trong phạm vi đã
khai báo.

### Viết một module thêm memory provider

Entrypoint `register(api)` của module có thể gọi
`api.add_memory_provider(name, factory)` để cắm một nguồn bộ nhớ bên ngoài vào recall.
`name` phải khớp với một mục `[memory.external.<name>]` trong `~/.veles/config.toml`;
`factory` được gọi với mục đó (một `dict`) và phải trả về một đối tượng cài đặt giao
thức `MemoryProvider` của Veles (`veles.core.memory.provider`), hoặc `None` để bỏ qua
provider:

```toml
# module.toml
[module]
name = "my-provider"
description = "Recalls memories from my external store."
entrypoint = "my_provider.py:register"
version = "0.1.0"
```

```python
# my_provider.py
from veles.core.memory.provider import RecallHit


class MyProvider:
    name = "my-provider"

    def recall(self, query: str, *, limit: int) -> list[RecallHit]:
        ...  # query the external store, return RecallHit objects


def _build(cfg: dict) -> MyProvider | None:
    api_key = cfg.get("api_key")
    return MyProvider() if api_key else None


def register(api) -> None:
    api.add_memory_provider("my-provider", _build)
```

```toml
# ~/.veles/config.toml
[memory.external.my-provider]
api_key = "..."
```

Một provider cài đặt thêm `ingest(title, body, *, insight_id) ->
bool` (giao thức `IngestingMemoryProvider`) sẽ nhận cả các lần ghi của Veles, không
chỉ đọc. Nếu hai module đăng ký cùng một tên provider, việc nạp module thứ hai thất
bại — nó bị bỏ qua kèm cảnh báo, không để lại gì đăng ký dở dang. Một mục cấu hình
trong `config.toml` mà module của nó chưa được cài sẽ in một cảnh báo kèm lệnh cài
đặt; recall vẫn hoạt động mà không có nó.

Registry cung cấp sẵn Honcho, Mem0 và Supermemory dưới dạng các module provider — cài
bằng `veles registry install --user {honcho,mem0,supermemory}`, rồi chạy lệnh `uv tool
install veles-ai --with '<package>'` mà bước cài in ra (mỗi module khai báo một SDK —
`mem0ai>=2.0`, `honcho-ai>=2.5`, `supermemory>=3.62` — mà Veles không bao giờ cài giúp
bạn), và điền vào mục `[memory.external.<name>]` tương ứng:

- **mem0**: `api_key`, `user_id`, tùy chọn `agent_id` (cũng recall bộ nhớ của agent đó)
  và `host`. Telemetry của SDK mặc định tắt; mỗi lần recall gửi thêm một request
  `GET /v1/ping/`.
- **supermemory**: `api_key`, tùy chọn `user_id` (gửi dưới dạng `container_tag` của
  lần tìm kiếm) và `base_url`.
- **honcho**: `api_key`, `workspace_id`, tùy chọn `peer_id` (chỉ tìm trong tin nhắn của
  peer đó) và `base_url`. Mỗi lần recall thực hiện get-or-create workspace — nó tạo
  `workspace_id` nếu chưa tồn tại.

## Khám phá thêm

Tìm kiếm trong các registry đã kết nối:

```bash
veles registry search [query] [--kind module|skill|layout|mcp]
```

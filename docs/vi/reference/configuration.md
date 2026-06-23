# Tham khảo cấu hình

> 🌐 **Languages:** **English** · [Русский](../../ru/reference/configuration.md)

Veles được cấu hình bởi hai file TOML và một tập các thư mục trạng thái. Các
secret (API key, bot token) **không bao giờ** được ghi vào những file này — chúng
nằm trong keychain của hệ điều hành hoặc trong biến môi trường (xem [biến môi trường](environment-variables.md)).

## Trạng thái được lưu ở đâu

| Đường dẫn | Phạm vi | Nội dung |
|---|---|---|
| `~/.veles/` | User-global | `config.toml`, các cấp quyền trust, skills/tools dùng chung nhiều dự án, cache model, locale, registry |
| `<project>/.veles/` | Cục bộ theo dự án | `project.toml`, `config.toml`, `memory.db`, skills/tools của dự án, plan, các file tạm lúc chạy |
| `<project>/AGENTS.md` | Dự án | File ngữ cảnh được chèn vào agent (symlink tới `CLAUDE.md` / `GEMINI.md`) |
| `<project>/wiki/`, `sources/` | Dự án | Nội dung của người dùng (layout LLM-Wiki mặc định) |

`VELES_USER_HOME` chuyển hướng `~` (nên trạng thái user nằm tại `<override>/.veles/`).
Xem [layout dự án](project-layout.md) để biết cây thư mục đầy đủ.

---

## Config của user — `~/.veles/config.toml`

Được trình thiết lập lần đầu ghi ra; có thể chỉnh tay an toàn.

```toml
[user]
language = "en"                  # "en" | "ru" — UI string locale
default_provider = "openrouter"  # default provider for new projects
default_model = "anthropic/claude-sonnet-4.6"
first_project_name = "myorg"     # recorded by the wizard
tui_theme = "everforest"         # everforest | dracula | gruvbox | tokyo-night | catppuccin

[permissions]                    # optional per-tool policy
fetch_url  = "approval_required" # allow | approval_required | always_confirm
write_file = "always_confirm"

[routing.tasks]                  # optional user-scope routing (see below)
compressor = "openrouter:anthropic/claude-haiku-4.5"

[mcp.servers.my-server]          # optional user-scope MCP servers
transport = "stdio"
command = "python"               # executable only — arguments go in `args`
args = ["-m", "my_mcp_server"]
```

| Khóa | Kiểu | Mục đích |
|---|---|---|
| `[user] language` | `"en"` \| `"ru"` | Locale cho chuỗi UI (có thể ghi đè qua `VELES_LOCALE`) |
| `[user] default_provider` | string | Nhà cung cấp dùng khi không chỉ định |
| `[user] default_model` | string | Model dùng khi không chỉ định |
| `[user] tui_theme` | string | Chủ đề màu TUI mặc định |
| `[permissions] <tool>` | policy | Chính sách quyền theo từng tool (xem [trust & sandbox](../explanation/trust-and-sandbox.md)) |

---

## Config của dự án — `<project>/.veles/config.toml`

```toml
[provider]
default = "openrouter"                               # provider name for the main agent + routing base
model = "anthropic/claude-sonnet-4.6"                # model id (omit to require --model or the user default_model)

[routing.tasks]                  # per-task overrides (highest priority below explicit flags)
default    = "openrouter:anthropic/claude-sonnet-4.6"
compressor = "openrouter:anthropic/claude-haiku-4.5"
insights   = "openrouter:anthropic/claude-haiku-4.5"
advisor    = "openrouter:anthropic/claude-opus-4.8"
vision     = "openai:gpt-4o"
embedding  = "openai:text-embedding-3-small"

[daemon]                         # the unnamed/"default" daemon
enabled = true
host = "127.0.0.1"
port = 8765
autostart = false

[daemon.api]                     # a named daemon session ("api")
provider = "anthropic"
model = "claude-opus-4.8"
host = "127.0.0.1"
port = 8801
mode = "auto"

[channels.telegram]              # global channels (served by the unnamed daemon)
enabled = true
whitelist = ["@alice", "123456789"]

[daemon.api.channels.telegram]   # channels bound to a named daemon session
enabled = true
whitelist = ["@bob"]

[mcp.servers.github]             # external MCP servers (project scope)
transport = "stdio"             # stdio | http | sse
command = "npx"                  # executable only — arguments go in `args`
args = ["-y", "@modelcontextprotocol/server-github"]
env = { GITHUB_TOKEN = "${GITHUB_TOKEN}" }   # ${VAR} interpolates from the environment
```

### Các mục

| Mục | Mục đích |
|---|---|
| `[provider]` | Nhà cung cấp cơ sở (`default` = tên nhà cung cấp) + model (`model` = id model) cho agent chính và chuỗi cascade định tuyến |
| `[routing.tasks]` | Ghi đè `provider:model` theo từng tác vụ — xem [định tuyến theo tác vụ](../how-to/per-task-routing.md) |
| `[permissions]` | Chính sách quyền theo từng tool (phạm vi dự án) |
| `[daemon]` | Bind + autostart của daemon không tên/"default" |
| `[daemon.<name>]` | Một session daemon có tên (model/provider/host/port/mode riêng) |
| `[channels.<type>]` | Một channel do daemon không tên phục vụ (ví dụ `telegram`) |
| `[daemon.<name>.channels.<type>]` | Một channel gắn với một session daemon có tên |
| `[mcp.servers.<name>]` | Một máy chủ MCP bên ngoài (nguồn tool) |

Các loại tác vụ cho `[routing.tasks]`: `default`, `curator`, `compressor`,
`insights`, `skills`, `advisor`, `vision`, `embedding`.

> Các gợi ý định tuyến bằng ngôn ngữ tự nhiên trong `AGENTS.md` được phân tích
> thành một `routing.nl.toml` tự sinh; các mục `[routing.tasks]` tường minh luôn
> thắng. Chạy `veles route refresh` để phân tích lại. Xem
> [định tuyến theo tác vụ](../how-to/per-task-routing.md).

### `project.toml`

`<project>/.veles/project.toml` chứa siêu dữ liệu bất biến của dự án (`name`,
`created_at`, `schema_version`, `layout`). Thông thường bạn không chỉnh tay file này.

---

## AGENTS.md

File ngữ cảnh của dự án nằm ở thư mục gốc dự án. Nó được chèn vào system prompt
của agent khi khởi động và được symlink tới `CLAUDE.md` và `GEMINI.md` để một CLI
`claude` hoặc `gemini` khởi chạy trong thư mục đó nhận được cùng ngữ cảnh.

Giữ nó nhỏ gọn — các file `.md` phụ trợ (ví dụ `wiki/INDEX.md`) được nạp theo
nhu cầu. Kiểm tra các mục bắt buộc bằng `veles schema validate`. Xem
[gói layout & LLM-Wiki](../explanation/layout-packs-and-llm-wiki.md).

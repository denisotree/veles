# Tài liệu tham khảo cấu hình

> 🌐 **Ngôn ngữ:** [English](../../en/reference/configuration.md) · **Tiếng Việt**

Veles được cấu hình bằng hai tệp TOML và một tập hợp các thư mục lưu trạng thái.
Secret (API key, bot token) **không bao giờ** được ghi vào các tệp này — chúng nằm
trong keychain của hệ điều hành hoặc trong biến môi trường (xem
[biến môi trường](environment-variables.md)).

## Trạng thái được lưu ở đâu

| Đường dẫn | Phạm vi | Nội dung |
|---|---|---|
| `~/.veles/` | Toàn cục cấp người dùng | `config.toml`, các quyền trust, skill/tool dùng chung giữa các dự án, model cache, locale, registry |
| `<project>/.veles/` | Cục bộ trong dự án | `project.toml`, `config.toml`, `memory.db`, skill/tool của dự án, plan, các artefact thời gian chạy |
| `<project>/AGENTS.md` | Dự án | Tệp ngữ cảnh được tiêm vào agent (symlink tới `CLAUDE.md` / `GEMINI.md`) |
| `<project>/wiki/`, `sources/` | Dự án | Nội dung của người dùng (layout LLM-Wiki mặc định) |

`VELES_USER_HOME` chuyển hướng `~` (để trạng thái cấp người dùng nằm tại
`<override>/.veles/`). Xem [bố cục dự án](project-layout.md) để biết toàn bộ cây thư mục.

---

## Cấu hình người dùng — `~/.veles/config.toml`

Được tạo bởi wizard chạy lần đầu; có thể chỉnh sửa bằng tay an toàn.

```toml
[user]
language = "en"                  # "en" | "ru" — UI string locale
default_provider = "openrouter"  # default provider for new projects
default_model = "anthropic/claude-sonnet-4.6"
first_project_name = "myorg"     # recorded by the wizard
tui_theme = "everforest"         # everforest | dracula | gruvbox | tokyo-night | catppuccin

[permissions]                    # optional per-tool policy
fetch_url  = "approval_required" # approval_required | always_confirm | always_allow
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
| `[user] language` | `"en"` \| `"ru"` | Locale cho các chuỗi giao diện (có thể ghi đè qua `VELES_LOCALE`) |
| `[user] default_provider` | string | Provider được dùng khi không chỉ định |
| `[user] default_model` | string | Model được dùng khi không chỉ định |
| `[user] tui_theme` | string | Theme màu mặc định cho TUI |
| `[permissions] <tool>` | policy | Chính sách quyền theo từng công cụ (xem [trust & sandbox](../explanation/trust-and-sandbox.md)) |

---

## Cấu hình dự án — `<project>/.veles/config.toml`

```toml
[provider]
default = "openrouter:anthropic/claude-sonnet-4.6"   # base for the main agent + routing

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

### Các phần (section)

| Phần | Mục đích |
|---|---|
| `[provider]` | Provider/model nền cho agent chính và cascade routing |
| `[routing.tasks]` | Ghi đè `provider:model` theo từng tác vụ — xem [routing theo tác vụ](../how-to/per-task-routing.md) |
| `[permissions]` | Chính sách quyền theo từng công cụ (phạm vi dự án) |
| `[daemon]` | Địa chỉ bind + autostart của daemon không tên/"default" |
| `[daemon.<name>]` | Một named daemon session (có model/provider/host/port/mode riêng) |
| `[channels.<type>]` | Một kênh được phục vụ bởi daemon không tên (ví dụ `telegram`) |
| `[daemon.<name>.channels.<type>]` | Một kênh gắn với một named daemon session |
| `[mcp.servers.<name>]` | Một máy chủ MCP bên ngoài (nguồn công cụ) |

Các kiểu tác vụ cho `[routing.tasks]`: `default`, `curator`, `compressor`, `insights`,
`skills`, `advisor`, `vision`, `embedding`.

> Các gợi ý routing bằng ngôn ngữ tự nhiên trong `AGENTS.md` được phân tích thành
> một tệp `routing.nl.toml` tự sinh; các mục `[routing.tasks]` khai báo tường minh
> luôn thắng. Chạy `veles route refresh` để phân tích lại. Xem
> [routing theo tác vụ](../how-to/per-task-routing.md).

### `project.toml`

`<project>/.veles/project.toml` giữ metadata bất biến của dự án (`name`,
`created_at`, `schema_version`, `layout`). Thông thường bạn không chỉnh sửa nó bằng tay.

---

## AGENTS.md

Tệp ngữ cảnh dự án nằm ở thư mục gốc của dự án. Nó được tiêm vào system prompt của
agent khi khởi động và được symlink tới `CLAUDE.md` và `GEMINI.md` để một CLI
`claude` hoặc `gemini` khởi chạy trong thư mục đó nhận được cùng ngữ cảnh.

Giữ nó nhỏ gọn — các tệp `.md` phụ trợ (ví dụ `wiki/INDEX.md`) được nạp theo nhu cầu.
Kiểm tra các phần bắt buộc bằng `veles schema validate`. Xem
[layout pack & LLM-Wiki](../explanation/layout-packs-and-llm-wiki.md).

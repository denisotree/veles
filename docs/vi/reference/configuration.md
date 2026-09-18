# Tham khảo cấu hình

> 🌐 **Ngôn ngữ:** [English](../../en/reference/configuration.md) · [简体中文](../../zh-CN/reference/configuration.md) · [繁體中文](../../zh-TW/reference/configuration.md) · [日本語](../../ja/reference/configuration.md) · [한국어](../../ko/reference/configuration.md) · [Español](../../es/reference/configuration.md) · [Français](../../fr/reference/configuration.md) · [Italiano](../../it/reference/configuration.md) · [Português (BR)](../../pt-BR/reference/configuration.md) · [Português (PT)](../../pt-PT/reference/configuration.md) · [Русский](../../ru/reference/configuration.md) · [العربية](../../ar/reference/configuration.md) · [हिन्दी](../../hi/reference/configuration.md) · [বাংলা](../../bn/reference/configuration.md) · **Tiếng Việt**

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
[engine]
provider = "openrouter"                               # provider name for the main agent + routing base
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
| `[engine]` | Nhà cung cấp cơ sở (`provider` = tên nhà cung cấp) + model (`model` = id model) cho agent chính và chuỗi cascade định tuyến |
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

### Ghim backend và các khoá khác trong thân yêu cầu

`[engine.request.<provider>]` được chuyển **nguyên vẹn** vào thân yêu cầu của nhà
cung cấp đó. Veles không mô hình hoá schema của thượng nguồn, nên bất kỳ tuỳ chọn
nào nhà cung cấp chấp nhận đều dùng được ngay, không phải chờ Veles biết tới nó:

```toml
[engine.request.openrouter.provider]
order = ["GMICloud"]
allow_fallbacks = false

[engine.request.openrouter.reasoning]
enabled = false
```

Mục này lấy **tên nhà cung cấp** làm khoá (`openrouter`, `anthropic`, `openai`,
`gemini`, `ollama`, `llamacpp`, `openai-compat`), nhờ vậy một cấu hình dự án sống
sót qua việc đổi backend: khối `provider` của OpenRouter gửi tới llama.cpp sẽ là
lỗi 400, nên mỗi backend chỉ đọc mục con của chính nó. Khi không khai báo mục
này, các yêu cầu giống hệt trước đây tới từng byte.

**Khi nào cần: các phép đo lặp lại được.** Một relay như OpenRouter phân phối cùng
một mô hình tới nhiều backend với mức lượng tử hoá khác nhau, nên hai lần chạy
trên cùng đầu vào có thể khác nhau vì lý do chẳng liên quan gì tới đầu vào. Định
tuyến dính theo `session_id` giữ một cuộc hội thoại trên một backend, nhưng không
cho biết đó là backend **nào**.

Hãy ghim bằng `order`, đừng ghim bằng `quantizations`. Tính đến 18-09-2026,
`z-ai/glm-5.3-flash` có 29 endpoint: 16 ở `fp8`, 3 ở `fp4`, một `nvfp4`, **9 cái
không khai báo mức lượng tử hoá nào cả**, và không có cái nào ở `bf16`. Vì thế
`quantizations = ["fp8"]` vẫn để lại 16 ứng viên với cửa sổ ngữ cảnh từ 262144 tới
1310720 token, trong khi một `order` chỉ có một phần tử cùng
`allow_fallbacks = false` xác định backend một cách dứt khoát. Liệt kê endpoint
của một mô hình:

```bash
curl -s https://openrouter.ai/api/v1/models/<author>/<slug>/endpoints \
  -H "Authorization: Bearer $OPENROUTER_API_KEY" | jq '.data.endpoints[]
  | {provider_name, quantization, context_length}'
```

Chỉ giữ việc ghim trong dự án đo đạc — môi trường sản xuất cần định tuyến dính,
thứ giữ được tính sẵn sàng và khả năng dự phòng.

**Kiểm tra xem việc ghim có giữ được không.** Mỗi lần gọi mô hình đều ghi cả ý
định lẫn kết quả vào `.veles/traces.jsonl`: `request_extra` là thứ đã gửi đi,
`upstream_provider` là backend đã trả lời. Một dòng là đủ:

```bash
jq -r 'select(.session_id=="<sid>") | .upstream_provider' .veles/traces.jsonl | sort -u
```

Nhiều hơn một dòng nghĩa là lần chạy đó đã trộn lẫn các backend. Cùng các bản ghi
ấy còn mang `reasoning_tokens` (phần ngân sách dành cho suy luận) và
`est_cost_usd` (chi phí thực mà thượng nguồn tính, khi nó báo cáo).

**Lỗi được làm cho ồn ào một cách cố ý.** Tên nhà cung cấp viết sai, hay sai đường
dẫn mục (`[engine.reqest.…]`), sẽ dừng lần chạy bằng một `ConfigError` nêu rõ tệp
và danh sách nhà cung cấp đã biết: một lần ghim chưa bao giờ tới được đường
truyền sẽ âm thầm làm hỏng chính phép đo mà nó được viết ra để phục vụ. Veles
không kiểm tra các khoá *bên trong* mục con, vì thượng nguồn đã làm việc đó:
OpenRouter trả `400 provider: Unrecognized key: "quantization"` cho khoá lạ và
`404 No endpoints found …` cho giá trị không khớp thứ gì.

### Bản ghi hội thoại được giữ bao lâu

```toml
[memory]
turn_retention_days = 90   # 0 giữ mọi thứ mãi mãi
```

Các lượt hội thoại thô bị xoá sau số ngày này; còn các **insight** và quy tắc rút
ra từ chúng thì được giữ mãi mãi. Bản ghi là nguyên liệu thô, insight mới là thứ
người ta đọc nó để có — nhờ vậy `memory.db` thôi phình ra vô hạn trong khi tác tử
vẫn giữ được những gì đã học.

Một bản ghi chỉ bị bỏ khi **cả hai** điều kiện cùng đúng: cũ hơn cửa sổ lưu trữ
**và** bộ biên tập đã xử lý phiên đó. Phiên mà bộ biên tập chưa chạm tới thì không
bao giờ bị xoá, dù cũ đến đâu — nếu không, bản ghi sẽ bị huỷ trước khi học được
điều gì từ nó.

Cái giá thấy rõ: `veles sessions search` chỉ tìm được văn bản trong cửa sổ.
`veles sessions list` vẫn hiện các lần chạy cũ, vì các dòng phiên (id, tiêu đề,
mốc thời gian) được giữ lại — chỉ phần thân tin nhắn mất đi. Việc dọn dẹp diễn ra
trong `veles dream`, sau bước rút trích insight.

### Xoay vòng nhật ký

`traces.jsonl` và `events.jsonl` xoay vòng ở mốc 50 MB thành `<tên>.<unix_ts>`, và
**10** bản xoay vòng mới nhất được giữ lại — những bản cũ hơn bị xoá ở lần xoay
vòng kế tiếp. Trước đây chúng được giữ mãi mãi.

Ở mức dùng thông thường thì không cần cấu hình gì: với ~530 byte mỗi bản ghi trace
và ~1,1 KB sự kiện mỗi lượt của tác tử, lần xoay vòng đầu tiên còn cách nhiều năm.
Tuỳ chọn này tồn tại vì tăng trưởng vô hạn mà không có chính sách là một chỗ rò rỉ
mà người tiếp quản cỗ máy sẽ phải tự phát hiện ra.

### Hình ảnh

Ảnh gửi vào một kênh được mô tả trước khi lượt bắt đầu, dùng mô hình mà
`[routing.tasks].vision` trỏ tới — nếu không có tuyến rõ ràng thì đó chính là mô
hình `[engine]` của bạn. Vì vậy một engine đa phương thức không cần cấu hình gì
cả.

`[vision] mode` chọn quy trình:

- `model` (mặc định) — mô hình thị giác mô tả ảnh.
- `ocr` — chỉ Tesseract. Cục bộ, miễn phí, không gọi LLM; hợp với ảnh quét văn
  bản.
- `ocr+model` — trước là văn bản nguyên văn, sau là mô tả của mô hình.
- `off` — không đọc gì cả; tệp vẫn được lưu và tác tử có thể tự gọi
  `image_describe` / `image_ocr` nếu muốn.

Hãy đặt `[vision] model` khi engine chỉ xử lý văn bản. Bất kỳ nhà cung cấp nào có
khả năng thị giác đều dùng được, kể cả máy chủ cục bộ: `ollama:llava`,
`llamacpp:…`, `openai-compat:…`.

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

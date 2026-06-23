# Tham chiếu CLI

> 🌐 **Ngôn ngữ:** [English](../../en/reference/cli.md) · [Русский](../../ru/reference/cli.md)

Toàn bộ lệnh, lệnh con và cờ của Veles. Chạy `veles <command> --help` để xem
chữ ký lệnh chính thức, luôn được cập nhật — trang này phản chiếu các bộ phân tích
tham số trong `src/veles/cli/_parsers/`.

```
veles [--no-wizard] <command> [subcommand] [options]
```

- `--no-wizard` — bỏ qua trình hướng dẫn thiết lập lần đầu ngay cả khi
  `~/.veles/config.toml` chưa tồn tại (cũng phụ thuộc vào TTY và `VELES_NO_WIZARD=1`).
- Khi không có tham số nào, `veles` khởi chạy [TUI](tui.md) tương tác.

Hầu hết các lệnh agent đều chấp nhận [các cờ vòng lặp agent dùng chung](#shared-agent-loop-flags)
và [tên nhà cung cấp](#provider-names) liệt kê ở cuối trang.

---

## Vòng đời dự án

### `veles init [name]`
Tạo một dự án Veles mới trong thư mục hiện tại (một thư mục trạng thái `.veles/`
+ `AGENTS.md` + khung nội dung của gói layout đã chọn).

| Cờ | Mặc định | Mục đích |
|---|---|---|
| `name` (vị trí) | basename của cwd | Tên dự án |
| `--layout <name>` | `llm-wiki` | Gói layout cho khung nội dung (`llm-wiki`, `notes`, `bare`, hoặc một gói tùy chỉnh từ `~/.veles/layouts/`) |
| `--force` | tắt | Tạo lại `.veles/` ngay cả khi nó đã tồn tại |

### `veles schema {validate,edit,fix}`
Kiểm tra hoặc chỉnh sửa `AGENTS.md` (tệp ngữ cảnh dự án).

- `validate` — kiểm tra các phần H2 bắt buộc.
- `edit` — mở `AGENTS.md` trong `$EDITOR` (mặc định `vi`), kiểm tra khi thoát.
- `fix` — thêm các phần bị thiếu một cách tương tác qua trình hướng dẫn LLM.

### `veles self-doc [refresh|show]`
Tạo và hiển thị tài liệu tự mô tả của dự án (`wiki/self-doc/overview.md`).
`veles self-doc` đơn thuần hiển thị trang hiện tại; `refresh` tạo lại nó.

### `veles doctor`
Chạy các kiểm tra sức khỏe trên trạng thái toàn cục người dùng và dự án đang hoạt
động. Hoạt động dù có hay không có dự án đang hoạt động.

| Cờ | Mặc định | Mục đích |
|---|---|---|
| `--json` | tắt | Xuất báo cáo JSON |
| `--strict` | tắt | Thoát với mã khác 0 nếu có bất kỳ cảnh báo nào (dùng cho cổng CI) |

### `veles export {full,template} <path>`
Đóng gói dự án thành một bó `.tar.gz`. Xem [Sao lưu và chia sẻ](../how-to/backup-and-share.md).

- `full <path>` — toàn bộ dự án (`.veles/` + `AGENTS.md`), trừ dữ liệu tạm thời lúc chạy.
- `template <path>` — tập con đã được làm sạch (schema + skills + modules + các
  trang wiki không phải session); loại bỏ `memory.db`, `sources/`, `sessions/`,
  các cấp quyền `trust`, và biên tập PII trong văn bản.

### `veles import <path>`
Khôi phục một bó được tạo bởi `veles export`.

| Cờ | Mặc định | Mục đích |
|---|---|---|
| `path` (vị trí) | — | Đường dẫn bó (`.tar.gz`) |
| `--into <dir>` | cwd | Thư mục đích |
| `--force` | tắt | Ghi đè `.veles/` đã tồn tại tại đích |

---

## Chạy agent

### `veles run "<prompt>"`
Chạy một prompt từ đầu đến cuối với việc lưu trữ bộ nhớ và các trigger
curator/học hỏi. Chấp nhận tất cả [các cờ vòng lặp agent dùng chung](#shared-agent-loop-flags) cùng với:

| Cờ | Mặc định | Mục đích |
|---|---|---|
| `--resume <session_id>` | session mới | Tiếp tục một session đã có |
| `--manager` | tắt | Phân rã qua trình quản lý đa agent (cũng dùng `VELES_MANAGER_MODE=1`) |
| `--plan` | tắt | Chế độ lập kế hoạch: cho phép đọc/tìm/soạn thảo, chặn các thay đổi |
| `--no-agents-md` | tắt | Không chèn `AGENTS.md` vào system prompt |
| `--no-index` | tắt | Không chèn `wiki/INDEX.md` |
| `--no-compress` | tắt | Tắt nén ngữ cảnh cửa sổ trượt |
| `--no-curator` | tắt | Tắt các trigger curator cho lần chạy này |
| `--no-insights` | tắt | Tắt trích xuất insight sau khi chạy |
| `--no-proposer` | tắt | Tắt tự động kích hoạt trình đề xuất subproject |
| `--no-route-refresh` | tắt | Tắt làm mới định tuyến NL từ `AGENTS.md` |
| `--no-suggest-promote` | tắt | Tắt trình gợi ý tự động thăng cấp |
| `--compressor-model <id>` | theo định tuyến | Ghi đè model nén |
| `--compress-threshold-tokens <n>` | `50000` | Kích thước lịch sử kích hoạt nén |

### `veles tui`
Mở REPL tương tác. Xem [tham chiếu TUI](tui.md). Chấp nhận các cờ vòng lặp agent
dùng chung, `--resume`, các cờ chèn/nén `--no-*` ở trên, và:

| Cờ | Mặc định | Mục đích |
|---|---|---|
| `--theme <name>` | config hoặc `everforest` | Giao diện màu (everforest, dracula, gruvbox, tokyo-night, catppuccin) |

### `veles add <source>`
Đọc một nguồn (tệp cục bộ hoặc URL `http(s)://`) và tổng hợp nó thành một trang
wiki. Chấp nhận các cờ vòng lặp agent dùng chung.

### `veles curate`
Chạy một lượt curator: nén các session chưa xử lý thành các trang `wiki/sessions/`.

| Cờ | Mặc định | Mục đích |
|---|---|---|
| `--limit <n>` | một giá trị mặc định nhỏ | Số session tối đa xử lý trong lần chạy này |

Cùng với các cờ vòng lặp agent dùng chung.

### `veles research "<question>"`
Nghiên cứu sâu: phân rã thành các câu hỏi con → khám phá web song song →
tổng hợp một báo cáo có trích dẫn.

| Cờ | Mặc định | Mục đích |
|---|---|---|
| `--max-subquestions <n>` | `4` | Số góc nghiên cứu song song |

Cùng với các cờ vòng lặp agent dùng chung.

### `veles dream`
Chạy một chu kỳ củng cố bộ nhớ nền (insights → khử trùng lặp skill → gợi ý
thăng cấp → lint wiki, tùy chọn củng cố bằng LLM).

| Cờ | Mặc định | Mục đích |
|---|---|---|
| `--include-consolidation` | tắt | Chạy bước củng cố LLM tốn kém (cần API key) |
| `--dry-run` | tắt | Chạy tất cả các bước nhưng bỏ qua việc ghi `wiki/state` |
| `--skip-insights` / `--skip-dedup` / `--skip-promote` / `--skip-lint` | tắt | Bỏ qua từng bước riêng lẻ |
| `--consolidation-model <id>` | `anthropic/claude-haiku-4.5` | Ghi đè model củng cố |
| `--provider <name>` | `openrouter` | Nhà cung cấp cho sub-agent củng cố |
| `--project-root <path>` | tự dò | Ghi đè dự án |

---

## Tri thức: skills, tools, modules

### `veles skill {list,show,add,remove,promote,demote,dedup,suggest-promote}`

| Lệnh con | Mục đích |
|---|---|
| `list` | Liệt kê các skill trong dự án đang hoạt động (kèm telemetry) |
| `show <name>` | In `SKILL.md` của một skill |
| `add <source> [--name N] [--scope project\|user] [-y]` | Cài đặt từ URL git hoặc đường dẫn cục bộ |
| `remove <name> [--scope project\|user] [-y]` | Xóa một skill đã cài |
| `promote <name> [--keep-telemetry]` | Sao chép một skill cấp dự án sang phạm vi người dùng (`~/.veles/skills/`) |
| `demote <name> [-y]` | Sao chép một skill người dùng vào dự án đang hoạt động |
| `dedup [--mode auto\|embedding\|tfidf] [--embedding-threshold f] [--tfidf-threshold f]` | Tìm các skill gần như trùng lặp |
| `suggest-promote [--save] [--min-uses n] [--min-success-rate f]` | Liệt kê các skill đạt ngưỡng tự động thăng cấp |

### `veles tool {list,show,promote}`

| Lệnh con | Mục đích |
|---|---|
| `list` | Liệt kê các tool được lập danh mục trong `memory.db` của dự án này |
| `show <name>` | In manifest + telemetry của một tool |
| `promote <name> [-y]` | Chuyển một tool cấp dự án sang `~/.veles/tools/` (dùng chung giữa các dự án) |

### `veles module {list,show,add,remove}`

| Lệnh con | Mục đích |
|---|---|
| `list` | Liệt kê các module đã cài |
| `show <name>` | In manifest của một module |
| `add <source> [--name N] [-y]` | Cài đặt một module từ URL git hoặc đường dẫn cục bộ |
| `remove <name> [-y]` | Xóa một module đã cài |

### `veles browse {modules,skills} [query]`
Duyệt các registry đã được tuyển chọn.

| Cờ | Mặc định | Mục đích |
|---|---|---|
| `query` (vị trí) | `""` | Lọc theo chuỗi con |
| `--source <url>` | chuẩn | Ghi đè nguồn registry |
| `--json` | tắt | Xuất JSON |

---

## Sessions & bộ nhớ

### `veles sessions {list,show,delete,search}`

| Lệnh con | Mục đích |
|---|---|
| `list [--limit n]` | Liệt kê các session gần đây (mặc định 20) |
| `show <session_id>` | In toàn bộ lịch sử lượt của một session |
| `delete <session_id>` | Xóa một session và các lượt của nó |
| `search "<query>" [--limit n] [--role user\|assistant\|both\|all] [--since 7d]` | Tìm kiếm toàn văn (FTS5) trên nội dung các lượt |

---

## Đa dự án

### `veles project {list,add,remove,switch}`

| Lệnh con | Mục đích |
|---|---|
| `list` | Liệt kê các dự án đã đăng ký, gần đây nhất trước |
| `add <path> [--slug S]` | Đăng ký một thư mục dự án đã có |
| `remove <slug>` | Hủy đăng ký một dự án (không động đến tệp) |
| `switch <slug>` | In đường dẫn tuyệt đối của dự án (dùng `cd $(veles project switch <slug>)`) |

### `veles subproject {init,list,switch,remove,suggest}`

| Lệnh con | Mục đích |
|---|---|
| `init <subdir> [--name N] [--description D]` | Tạo + đăng ký một subproject |
| `list` | Liệt kê các subproject của dự án đang hoạt động |
| `switch <slug>` | In đường dẫn tuyệt đối của một subproject |
| `remove <slug>` | Hủy đăng ký một subproject |
| `suggest [--save] [--min-pages n] [--min-similarity f]` | Phát hiện các cụm theo chủ đề và đề xuất subproject |

---

## Định tuyến & models

### `veles route {show,set,reset,refresh}`
Định tuyến ensemble theo từng tác vụ — `provider:model` nào xử lý từng loại tác vụ
(`default`, `curator`, `compressor`, `insights`, `skills`, `advisor`, `vision`,
`embedding`). Xem [định tuyến theo tác vụ](../how-to/per-task-routing.md).

| Lệnh con | Mục đích |
|---|---|
| `show` | In bảng định tuyến đã giải quyết cho dự án đang hoạt động |
| `set <task> <provider:model>` | Ghim một tác vụ vào một spec |
| `reset [task]` | Đặt lại một tác vụ (hoặc tất cả) về mặc định |
| `refresh [--force]` | Phân tích lại các gợi ý định tuyến ngôn ngữ tự nhiên từ `AGENTS.md` |

### `veles models <provider>`
Liệt kê các model của một nhà cung cấp. Các nhà cung cấp đám mây
(openrouter/openai/gemini) được cache 24h; các nhà cung cấp cục bộ luôn trực tiếp.

| Cờ | Mặc định | Mục đích |
|---|---|---|
| `provider` (vị trí) | — | Một trong [tên nhà cung cấp](#provider-names) |
| `--refresh` | tắt | Bỏ qua cache trên đĩa (chỉ đám mây) |
| `--json` | tắt | Xuất `{provider, source, models}` dưới dạng JSON |

---

## Tác vụ chạy lâu

### `veles goal {list,show,start,checkpoint,pause,resume,done,cancel}`
Các mục tiêu dài hạn với ngân sách và checkpoint.

| Lệnh con | Mục đích |
|---|---|
| `list [--status active\|paused\|completed\|blocked\|cancelled]` | Liệt kê các mục tiêu |
| `show <id> [--json]` | Hiển thị một mục tiêu |
| `start "<objective>" [--scope S] [--done-when D] [--max-steps n] [--max-cost-usd f] [--max-wall-time-s n] [--forbid A]… [--approve A]…` | Tạo một mục tiêu |
| `checkpoint <id> "<note>" [--evidence U] [--cost-usd f] [--no-advance]` | Ghi thêm tiến độ |
| `pause <id>` / `resume <id>` | Tạm dừng / tiếp tục |
| `done <id> [--evidence E]` / `cancel <id> [--reason R]` | Hoàn thành / hủy |

### `veles job {add,list,show,pause,resume,trigger,remove,history,tick}`
Các tác vụ agent theo lịch.

| Lệnh con | Mục đích |
|---|---|
| `add --name N --schedule S --prompt P [--repeat n] [--context-from JOB_ID] [--deliver-to TARGET]` | Tạo một job (schedule = cron, `<N><s\|m\|h\|d>`, hoặc dấu thời gian ISO) |
| `list [--json]` / `show <id>` | Kiểm tra các job |
| `pause <id>` / `resume <id>` / `trigger <id>` / `remove <id>` | Vòng đời |
| `history <id> [--limit n]` | Các lần chạy gần đây |
| `tick` | Chạy đồng bộ tất cả các job đến hạn một lần (không cần daemon; nhận các cờ vòng lặp agent) |

---

## Bảo mật & kiểm soát truy cập

### `veles trust {list,set,revoke,clear}`
Các cấp quyền được lưu trữ cho các tool nhạy cảm (`run_shell`, `write_file`,
`fetch_url`, …). Xem [bảo mật](../how-to/security-and-permissions.md).

| Lệnh con | Mục đích |
|---|---|
| `list` | Hiển thị các cấp quyền (phạm vi người dùng + dự án) |
| `set <tool> [--scope project\|user]` | Cấp quyền cho một tool |
| `revoke <tool> [--scope project\|user\|both]` | Gỡ bỏ một cấp quyền |
| `clear [--scope project\|user\|all]` | Xóa sạch các cấp quyền trong một phạm vi |

### `veles autopilot {enable,disable,status}`
Một khung thời gian giới hạn trong đó các lời nhắc trust-ladder tự động cho phép.

| Lệnh con | Mục đích |
|---|---|
| `enable --until <DUR>` | Mở một khung thời gian (`+30m`, `+2h`, `+1d`, hoặc ISO `2026-05-12T18:00:00Z`) |
| `disable` | Đóng khung thời gian ngay bây giờ |
| `status` | Báo cáo xem autopilot có đang hoạt động không |

### `veles secret {set,get,list,delete}`
Các bí mật được hỗ trợ bởi keychain của hệ điều hành (API key, bot token).

| Lệnh con | Mục đích |
|---|---|
| `set <name> [value]` | Lưu trữ (bỏ value để nhập tương tác / qua stdin) |
| `get <name> [--reveal] [--no-env-fallback]` | Tra cứu (mặc định có dự phòng qua env) |
| `list` | Hiển thị các bí mật chuẩn nào đã được cấu hình |
| `delete <name>` | Xóa một bí mật |

---

## Daemon & channels

### `veles daemon [start|stop|status|list|restart|delete|session|token]`
Chạy/điều khiển daemon HTTP+WS. `veles daemon` đơn thuần mở **trình chọn daemon**
TUI (dự án → daemon → channel). Xem [chạy như một daemon](../how-to/run-as-daemon.md).

| Lệnh con | Mục đích |
|---|---|
| `start [--host H] [--port P] [--foreground] [--name N]` | Khởi động một daemon (mặc định chạy nền tách rời) |
| `stop [--name N]` / `status [--name N]` | Dừng / kiểm tra |
| `list` | Liệt kê các daemon trên tất cả các dự án |
| `restart [target] [--name N]` | Dừng + khởi động lại trên cùng host/port |
| `delete <target> [-y]` | Dừng + gỡ khỏi registry |
| `session create <name> [--host H] --port P [--model M] [--provider P] [--mode M]` | Khai báo một session daemon có tên |
| `session list [--all]` / `session delete <name>` | Quản lý các session có tên |
| `token add <name>` / `token list` / `token remove <name>` | CRUD bearer-token |

`start` cũng chấp nhận các cờ vòng lặp agent dùng chung; với daemon, `--model` /
`--provider` mặc định theo config dự án và cố định trong suốt vòng đời của daemon.

### `veles channel {list,run,list-sessions,reset-session,add,remove}`
Các gateway chat bên ngoài (Telegram, …) giao tiếp với một daemon. Xem
[kết nối Telegram](../how-to/connect-telegram.md).

| Lệnh con | Mục đích |
|---|---|
| `list` | Liệt kê các nền tảng channel đã đăng ký + số lượng session |
| `run --channel telegram [--bot-token T] [--daemon-url U] [--daemon-token T]` | Khởi động một gateway ở chế độ tiền cảnh |
| `list-sessions [--channel C]` | Hiển thị các ánh xạ `chat_id → session_id` |
| `reset-session <chat_id> [--channel C]` | Quên một ánh xạ (tin nhắn tiếp theo bắt đầu mới) |
| `add [--channel C] [--session S]` | Gắn một channel vào một daemon (trình hướng dẫn; thông tin xác thực → keychain) |
| `remove <channel> [--session S]` | Gỡ bỏ một ràng buộc channel |

---

## MCP (máy chủ tool bên ngoài)

### `veles mcp {list,test}`
Kiểm tra các máy chủ MCP bên ngoài được cấu hình dưới `[mcp.servers.*]`. Xem
[máy chủ MCP bên ngoài](../how-to/external-mcp-servers.md).

| Lệnh con | Mục đích |
|---|---|
| `list [--connect-timeout f]` | Hiển thị các máy chủ đã cấu hình, trạng thái kết nối, số lượng tool |
| `test <server>` | Kết nối tới một máy chủ và liệt kê các tool của nó |

---

## Các cờ vòng lặp agent dùng chung

Được chấp nhận bởi `run`, `add`, `tui`, `curate`, `research`, `job tick`, và
`daemon start`:

| Cờ | Mặc định | Mục đích |
|---|---|---|
| `--model <id>` | `anthropic/claude-sonnet-4.6` (tui: được lưu) | ID của model |
| `--provider <name>` | `openrouter` | Nhà cung cấp (xem bên dưới) |
| `--max-tokens-total <n>` | `100000` | Ngân sách token tích lũy; `0` để tắt |
| `--max-iterations <n>` | `30` | Số vòng gọi tool tối đa mỗi lượt |
| `--stream` | tắt | Truyền phản hồi theo từng token |
| `--verbose` / `-v` | tắt | Tiến độ theo từng lượt ra stderr |
| `--project-root <path>` | tự dò từ cwd | Thao tác trên một dự án ở nơi khác |

## Tên nhà cung cấp

`openrouter` (mặc định) · `anthropic` · `openai` · `gemini` · `claude-cli` ·
`gemini-cli` · `ollama` · `llamacpp` · `openai-compat`

Các nhà cung cấp cục bộ (`ollama`, `llamacpp`, `openai-compat`) không cần API key.
Xem [tham chiếu nhà cung cấp](providers.md) và [cấu hình nhà cung cấp](../how-to/configure-providers.md).

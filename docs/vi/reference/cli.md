# Tham khảo CLI

> 🌐 **Ngôn ngữ:** [English](../../en/reference/cli.md) · [简体中文](../../zh-CN/reference/cli.md) · [繁體中文](../../zh-TW/reference/cli.md) · [日本語](../../ja/reference/cli.md) · [한국어](../../ko/reference/cli.md) · [Español](../../es/reference/cli.md) · [Français](../../fr/reference/cli.md) · [Italiano](../../it/reference/cli.md) · [Português (BR)](../../pt-BR/reference/cli.md) · [Português (PT)](../../pt-PT/reference/cli.md) · [Русский](../../ru/reference/cli.md) · [العربية](../../ar/reference/cli.md) · [हिन्दी](../../hi/reference/cli.md) · [বাংলা](../../bn/reference/cli.md) · **Tiếng Việt**

Mọi lệnh, lệnh con và cờ của Veles. Chạy `veles <command> --help` để xem chữ
ký lệnh chính xác và luôn cập nhật — trang này phản ánh các bộ phân tích đối số
trong `src/veles/cli/_parsers/`.

```
veles [--no-wizard] <command> [subcommand] [options]
```

- `--no-wizard` — bỏ qua trình thiết lập lần đầu ngay cả khi thiếu
  `~/.veles/config.toml` (cũng phụ thuộc vào TTY và vào `VELES_NO_WIZARD=1`).
- Khi không có đối số, `veles` khởi chạy [TUI](tui.md) tương tác.

Hầu hết các lệnh agent đều chấp nhận [các cờ vòng lặp agent dùng chung](#shared-agent-loop-flags)
và [tên nhà cung cấp](#provider-names) được liệt kê ở cuối trang.

---

## Vòng đời dự án

### `veles init [name]`
Tạo một dự án Veles mới trong thư mục hiện tại (một thư mục trạng thái `.veles/`
+ `AGENTS.md` + bộ khung nội dung của gói layout đã chọn).

| Cờ | Mặc định | Mục đích |
|---|---|---|
| `name` (vị trí) | tên cơ sở của cwd | Tên dự án |
| `--layout <name>` | `llm-wiki` | Gói layout cho bộ khung nội dung (`llm-wiki`, `notes`, `bare`, hoặc một gói tùy chỉnh từ `~/.veles/layouts/`) |
| `--force` | tắt | Tạo lại `.veles/` ngay cả khi nó đã tồn tại |

### `veles schema {validate,edit,fix}`
Kiểm tra hoặc chỉnh sửa `AGENTS.md` (file ngữ cảnh dự án).

- `validate` — kiểm tra các mục H2 bắt buộc.
- `edit` — mở `AGENTS.md` trong `$EDITOR` (mặc định `vi`), kiểm tra khi thoát.
- `fix` — bổ sung tương tác các mục còn thiếu qua một trình hướng dẫn LLM.

### `veles self-doc [refresh|show]`
Tạo và hiển thị tài liệu tự sinh của dự án (`wiki/self-doc/overview.md`).
`veles self-doc` không kèm gì sẽ hiển thị trang hiện tại; `refresh` tạo lại nó.

### `veles doctor`
Chạy các bài kiểm tra sức khỏe trên trạng thái user-global và dự án đang hoạt
động. Hoạt động dù có hay không có dự án đang hoạt động.

| Cờ | Mặc định | Mục đích |
|---|---|---|
| `--json` | tắt | Xuất báo cáo dạng JSON |
| `--strict` | tắt | Thoát với mã khác 0 nếu có bất kỳ cảnh báo nào (gating CI) |
| `--fix` | tắt | Thử sửa an toàn trước khi kiểm tra — hiện tại xây dựng lại một chỉ mục memory-recall (FTS) bị hỏng |

`doctor` cũng kiểm tra các phần liên quan đến bảo mật của `config.toml`
(`[channels.*]`, `[daemon.*]`, `[mcp.servers.*]`) và báo các khóa không xác định
là lỗi — một lỗi gõ như `whitlist` thay cho `whitelist` sẽ âm thầm vô hiệu hóa
một kiểm soát truy cập, nên nó báo lỗi rõ ràng ở đây.

### `veles export {full,template} <path>`
Đóng gói dự án thành một bundle `.tar.gz`. Xem [Sao lưu và chia sẻ](../how-to/backup-and-share.md).

- `full <path>` — toàn bộ dự án (`.veles/` + `AGENTS.md`), trừ các file tạm thời lúc chạy.
- `template <path>` — tập con đã làm sạch (schema + skills + modules + các trang
  wiki không phải session); loại bỏ `memory.db`, `sources/`, `sessions/`, các
  cấp quyền `trust`, và che bớt PII trong văn bản.

### `veles import <path>`
Khôi phục một bundle do `veles export` tạo ra.

| Cờ | Mặc định | Mục đích |
|---|---|---|
| `path` (vị trí) | — | Đường dẫn bundle (`.tar.gz`) |
| `--into <dir>` | cwd | Thư mục đích |
| `--force` | tắt | Ghi đè một `.veles/` đã tồn tại ở đích |

---

## Chạy agent

### `veles run "<prompt>"`
Chạy một prompt đơn lẻ từ đầu đến cuối với lưu trữ bộ nhớ và các trigger
curator/học. Chấp nhận tất cả [các cờ vòng lặp agent dùng chung](#shared-agent-loop-flags) cùng với:

| Cờ | Mặc định | Mục đích |
|---|---|---|
| `--resume <session_id>` | session mới | Tiếp tục một session đang có |
| `--manager` | tắt | Phân rã qua manager đa-agent (cũng dùng `VELES_MANAGER_MODE=1`) |
| `--verify` | tắt | Sau khi chạy, advisor được định tuyến đánh giá câu trả lời; nếu thất bại với độ tin cậy cao, chạy lại trên model mạnh hơn (cũng dùng `VELES_VERIFY_MODE=1`) |
| `--plan` | tắt | Chế độ lập kế hoạch: cho phép đọc/tìm/soạn thảo, chặn các thay đổi |
| `--no-agents-md` | tắt | Không chèn `AGENTS.md` vào system prompt |
| `--no-index` | tắt | Không chèn `wiki/INDEX.md` |
| `--no-compress` | tắt | Tắt nén ngữ cảnh kiểu sliding-window |
| `--no-curator` | tắt | Tắt các trigger curator cho lần chạy này |
| `--no-insights` | tắt | Tắt trích xuất insight sau khi chạy |
| `--no-proposer` | tắt | Tắt trigger tự động của trình đề xuất subproject |
| `--no-route-refresh` | tắt | Tắt làm mới định tuyến NL từ `AGENTS.md` |
| `--no-suggest-promote` | tắt | Tắt trình gợi ý tự động thăng cấp |
| `--compressor-model <id>` | định tuyến | Ghi đè model nén |
| `--compress-threshold-tokens <n>` | `50000` | Kích thước lịch sử kích hoạt nén |

### `veles tui`
Mở REPL tương tác. Xem [tham khảo TUI](tui.md). Chấp nhận các cờ vòng lặp
agent dùng chung, `--resume`, các cờ chèn/nén `--no-*` ở trên, và:

| Cờ | Mặc định | Mục đích |
|---|---|---|
| `--theme <name>` | từ config hoặc `everforest` | Chủ đề màu (everforest, dracula, gruvbox, tokyo-night, catppuccin) |

### `veles add <source>`
Đọc một nguồn (file cục bộ hoặc URL `http(s)://`) và tổng hợp nó thành một
trang wiki. Chấp nhận các cờ vòng lặp agent dùng chung.

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
Chạy một chu kỳ củng cố bộ nhớ ngầm (insights → khử trùng lặp skill → gợi ý
thăng cấp → lint wiki, tùy chọn củng cố bằng LLM).

| Cờ | Mặc định | Mục đích |
|---|---|---|
| `--include-consolidation` | tắt | Chạy củng cố LLM tốn kém (cần API key) |
| `--dry-run` | tắt | Chạy tất cả các bước nhưng bỏ qua việc ghi `wiki/state` |
| `--skip-insights` / `--skip-dedup` / `--skip-promote` / `--skip-lint` | tắt | Bỏ qua từng bước riêng lẻ |
| `--consolidation-model <id>` | định tuyến (fallback về `anthropic/claude-haiku-4.5`) | Ghi đè model củng cố |
| `--provider <name>` | định tuyến | Nhà cung cấp cho sub-agent củng cố (bỏ qua để dùng nhà cung cấp định tuyến của dự án) |
| `--project-root <path>` | tự dò | Ghi đè dự án |

---

## Tri thức: skills, tools, modules

### `veles skill {list,show,add,remove,promote,demote,dedup,suggest-promote}`

| Lệnh con | Mục đích |
|---|---|
| `list` | Liệt kê các skill trong dự án đang hoạt động (kèm telemetry) |
| `show <name>` | In ra `SKILL.md` của một skill |
| `add <source> [--name N] [--scope project\|user] [-y]` | Cài đặt từ một URL git hoặc đường dẫn cục bộ |
| `remove <name> [--scope project\|user] [-y]` | Xóa một skill đã cài đặt |
| `promote <name> [--keep-telemetry]` | Sao chép một skill dự án sang phạm vi user (`~/.veles/skills/`) |
| `demote <name> [-y]` | Sao chép một skill user vào dự án đang hoạt động |
| `dedup [--mode auto\|embedding\|tfidf] [--embedding-threshold f] [--tfidf-threshold f]` | Tìm các skill gần trùng lặp |
| `suggest-promote [--save] [--min-uses n] [--min-success-rate f]` | Liệt kê các skill đạt ngưỡng tự động thăng cấp |

### `veles tool {list,show,promote,approve}`

| Lệnh con | Mục đích |
|---|---|
| `list` | Liệt kê các tool đã được lập danh mục trong `memory.db` của dự án này |
| `show <name>` | In ra manifest + telemetry của một tool |
| `promote <name> [-y]` | Chuyển một tool dự án sang `~/.veles/tools/` (dùng chung nhiều dự án) |
| `approve [<name>] [--all] [-y]` | Xem lại + phê duyệt một file tool tự soạn để loader sẽ chạy nó |

Các tool tự soạn (`.veles/tools/*.py`) chạy mã ở cấp module khi loader import
chúng, nên một file mới hoặc vừa chỉnh sửa sẽ **không được nạp cho đến khi bạn
phê duyệt nó** — `veles tool approve` hiển thị mã và ghi lại hash của nó. Chạy
`veles tool approve` không kèm gì sẽ liệt kê những gì đang chờ. Đây là lý do một
tool do agent viết cần một bước xem lại trước khi có thể gọi được.

### `veles module {list,show,add,remove}`

| Lệnh con | Mục đích |
|---|---|
| `list` | Liệt kê các module đã cài đặt |
| `show <name>` | In ra manifest của một module |
| `add <source> [--name N] [-y]` | Cài đặt một module từ URL git hoặc đường dẫn cục bộ |
| `remove <name> [-y]` | Xóa một module đã cài đặt |

### `veles browse {modules,skills} [query]`
Duyệt các registry đã được tuyển chọn.

| Cờ | Mặc định | Mục đích |
|---|---|---|
| `query` (vị trí) | `""` | Bộ lọc chuỗi con |
| `--source <url>` | chính tắc | Ghi đè nguồn registry |
| `--json` | tắt | Xuất JSON |

---

## Sessions & bộ nhớ

### `veles sessions {list,show,delete,search}`

| Lệnh con | Mục đích |
|---|---|
| `list [--limit n]` | Liệt kê các session gần đây (mặc định 20) |
| `show <session_id>` | In ra toàn bộ lịch sử lượt của một session |
| `delete <session_id>` | Xóa một session và các lượt của nó |
| `search "<query>" [--limit n] [--role user\|assistant\|both\|all] [--since 7d]` | Tìm kiếm toàn văn (FTS5) trên nội dung các lượt |

---

## Đa dự án

### `veles project {list,add,remove,switch}`

| Lệnh con | Mục đích |
|---|---|
| `list` | Liệt kê các dự án đã đăng ký, gần đây nhất trước |
| `add <path> [--slug S]` | Đăng ký một thư mục dự án đang có |
| `remove <slug>` | Hủy đăng ký một dự án (không động đến file) |
| `switch <slug>` | In ra đường dẫn tuyệt đối của dự án (dùng `cd $(veles project switch <slug>)`) |

### `veles subproject {init,list,switch,remove,suggest}`

| Lệnh con | Mục đích |
|---|---|
| `init <subdir> [--name N] [--description D]` | Tạo + đăng ký một subproject |
| `list` | Liệt kê các subproject của dự án đang hoạt động |
| `switch <slug>` | In ra đường dẫn tuyệt đối của một subproject |
| `remove <slug>` | Hủy đăng ký một subproject |
| `suggest [--save] [--min-pages n] [--min-similarity f]` | Phát hiện các cụm chủ đề và đề xuất subproject |

---

## Định tuyến & models

### `veles route {show,set,reset,refresh}`
Định tuyến ensemble theo từng tác vụ — `provider:model` nào xử lý từng loại tác
vụ (`default`, `curator`, `compressor`, `insights`, `skills`, `advisor`,
`vision`, `embedding`). Xem [định tuyến theo tác vụ](../how-to/per-task-routing.md).

| Lệnh con | Mục đích |
|---|---|
| `show` | In ra bảng định tuyến đã được giải quyết cho dự án đang hoạt động |
| `set <task> <provider:model>` | Ghim một tác vụ vào một spec |
| `reset [task]` | Đặt lại một tác vụ (hoặc tất cả) về mặc định |
| `refresh [--force]` | Phân tích lại các gợi ý định tuyến bằng ngôn ngữ tự nhiên từ `AGENTS.md` |

### `veles models <provider>`
Liệt kê các model của một nhà cung cấp. Các nhà cung cấp đám mây
(openrouter/openai/gemini) được cache 24h; các nhà cung cấp cục bộ luôn trực tiếp.

| Cờ | Mặc định | Mục đích |
|---|---|---|
| `provider` (vị trí) | — | Một trong [các tên nhà cung cấp](#provider-names) |
| `--refresh` | tắt | Bỏ qua cache trên đĩa (chỉ đám mây) |
| `--json` | tắt | Xuất `{provider, source, models}` dạng JSON |

---

## Tác vụ chạy dài

### `veles goal {list,show,start,checkpoint,pause,resume,done,cancel}`
Các mục tiêu tầm xa với ngân sách và checkpoint.

| Lệnh con | Mục đích |
|---|---|
| `list [--status active\|paused\|completed\|blocked\|cancelled]` | Liệt kê các goal |
| `show <id> [--json]` | Hiển thị một goal |
| `start "<objective>" [--scope S] [--done-when D] [--max-steps n] [--max-cost-usd f] [--max-wall-time-s n] [--forbid A]… [--approve A]…` | Tạo một goal |
| `checkpoint <id> "<note>" [--evidence U] [--cost-usd f] [--no-advance]` | Ghi nhận tiến độ |
| `pause <id>` / `resume <id>` | Tạm dừng / tiếp tục |
| `done <id> [--evidence E]` / `cancel <id> [--reason R]` | Hoàn thành / hủy |

### `veles job {add,list,show,pause,resume,trigger,remove,history,tick}`
Các job agent được lên lịch.

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
Các cấp quyền được lưu cho các tool nhạy cảm (`run_shell`, `write_file`,
`fetch_url`, …). Xem [bảo mật](../how-to/security-and-permissions.md).

| Lệnh con | Mục đích |
|---|---|
| `list` | Hiển thị các cấp quyền (phạm vi user + dự án) |
| `set <tool> [--scope project\|user]` | Cấp quyền cho một tool |
| `revoke <tool> [--scope project\|user\|both]` | Gỡ bỏ một cấp quyền |
| `clear [--scope project\|user\|all]` | Xóa sạch các cấp quyền trong một phạm vi |

### `veles autopilot {enable,disable,status}`
Một cửa sổ thời gian giới hạn trong đó các lời nhắc trust-ladder tự động cho phép.

| Lệnh con | Mục đích |
|---|---|
| `enable --until <DUR>` | Mở một cửa sổ (`+30m`, `+2h`, `+1d`, hoặc ISO `2026-05-12T18:00:00Z`) |
| `disable` | Đóng cửa sổ ngay bây giờ |
| `status` | Báo cáo xem autopilot có đang hoạt động không |

### `veles secret {set,get,list,delete}`
Các secret được hỗ trợ bởi keychain của hệ điều hành (API key, bot token).

| Lệnh con | Mục đích |
|---|---|
| `set <name> [value]` | Lưu trữ (bỏ qua value để nhập tương tác / qua stdin) |
| `get <name> [--reveal] [--no-env-fallback]` | Tra cứu (mặc định fallback về env) |
| `list` | Hiển thị các secret chính tắc nào đã được cấu hình |
| `delete <name>` | Gỡ bỏ một secret |

---

## Daemon & channels

### `veles daemon [start|stop|status|list|restart|delete|session|token]`
Chạy/điều khiển daemon HTTP+WS. `veles daemon` không kèm gì sẽ mở TUI **trình
chọn daemon** (dự án → daemon → channels). Xem [chạy dưới dạng daemon](../how-to/run-as-daemon.md).

| Lệnh con | Mục đích |
|---|---|
| `start [--host H] [--port P] [--foreground] [--name N]` | Khởi động một daemon (mặc định tách tiến trình) |
| `stop [--name N]` / `status [--name N]` | Dừng / kiểm tra |
| `list` | Liệt kê các daemon trên tất cả các dự án |
| `restart [target] [--name N]` | Dừng + tạo lại trên cùng host/port |
| `delete <target> [-y]` | Dừng + gỡ khỏi registry |
| `session create <name> [--host H] --port P [--model M] [--provider P] [--mode M]` | Khai báo một session daemon có tên |
| `session list [--all]` / `session delete <name>` | Quản lý các session có tên |
| `token add <name>` / `token list` / `token remove <name>` | CRUD bearer-token |

`start` cũng chấp nhận các cờ vòng lặp agent dùng chung; với daemon, `--model` /
`--provider` mặc định lấy từ config dự án và cố định trong suốt vòng đời của daemon.

### `veles channel {list,run,list-sessions,reset-session,add,remove}`
Các gateway chat bên ngoài (Telegram, …) giao tiếp với một daemon. Xem
[kết nối Telegram](../how-to/connect-telegram.md).

| Lệnh con | Mục đích |
|---|---|
| `list` | Liệt kê các nền tảng channel đã đăng ký + số lượng session |
| `run --channel telegram [--bot-token T] [--daemon-url U] [--daemon-token T]` | Khởi động một gateway ở foreground |
| `list-sessions [--channel C]` | Hiển thị các ánh xạ `chat_id → session_id` |
| `reset-session <chat_id> [--channel C]` | Quên một ánh xạ (tin nhắn tiếp theo bắt đầu mới) |
| `add [--channel C] [--session S]` | Gắn một channel vào một daemon (wizard; thông tin xác thực → keychain) |
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
| `--model <id>` | giải quyết từ model `[engine]` của dự án → `default_model` của user (không có mặc định cứng) | ID model |
| `--provider <name>` | `openrouter` | Nhà cung cấp (xem bên dưới) |
| `--max-tokens-total <n>` | `100000` | Ngân sách token tích lũy; `0` để tắt |
| `--max-iterations <n>` | `1000` | Số vòng lặp gọi tool tối đa mỗi lượt |
| `--stream` | tắt | Truyền phát phản hồi theo từng token |
| `--verbose` / `-v` | tắt | Tiến độ từng lượt ra stderr |
| `--project-root <path>` | tự dò từ cwd | Thao tác trên một dự án ở nơi khác |

## Tên nhà cung cấp

`openrouter` (mặc định) · `anthropic` · `openai` · `gemini` · `claude-cli` ·
`gemini-cli` · `ollama` · `llamacpp` · `openai-compat`

Các nhà cung cấp cục bộ (`ollama`, `llamacpp`, `openai-compat`) không cần API
key. Xem [tham khảo nhà cung cấp](providers.md) và [cấu hình nhà cung cấp](../how-to/configure-providers.md).

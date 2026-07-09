# Veles

[![CI](https://github.com/denisotree/veles/actions/workflows/ci.yml/badge.svg)](https://github.com/denisotree/veles/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/veles-ai.svg)](https://pypi.org/project/veles-ai/)
[![License: Apache-2.0](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)
[![Python 3.13+](https://img.shields.io/badge/python-3.13%2B-blue.svg)](pyproject.toml)

<p align="center">
  <a href="README.md">English</a> ·
  <a href="README.zh-CN.md">简体中文</a> ·
  <a href="README.zh-TW.md">繁體中文</a> ·
  <a href="README.ja.md">日本語</a> ·
  <a href="README.ko.md">한국어</a> ·
  <a href="README.es.md">Español</a> ·
  <a href="README.fr.md">Français</a> ·
  <a href="README.it.md">Italiano</a> ·
  <a href="README.pt-BR.md">Português (BR)</a> ·
  <a href="README.pt-PT.md">Português (PT)</a> ·
  <a href="README.ru.md">Русский</a> ·
  <a href="README.ar.md">العربية</a> ·
  <a href="README.hi.md">हिन्दी</a> ·
  <a href="README.bn.md">বাংলা</a> ·
  <b>Tiếng Việt</b>
</p>

**Một framework agent CLI tối giản, ngày càng thông minh hơn sau mỗi phiên làm việc.**

<p align="center">
  <img src="docs/assets/tui-hero.gif" alt="Veles REPL — đặt một câu hỏi và nhận câu trả lời dựa trên bộ nhớ của chính dự án" width="800">
</p>

Khác với các công cụ trò chuyện luôn bắt đầu lại từ đầu mỗi lần, Veles duy trì **bộ nhớ dự án có cấu trúc** — các insight, quy tắc, và kiến thức đã được chắt lọc, tích lũy qua từng phiên và khiến agent càng hữu ích hơn khi bạn dùng càng lâu. Cách tổ chức *nội dung* của bạn có thể tùy biến: mặc định là wiki LLM kiểu Karpathy, hoặc ghi chú dạng phẳng, hoặc không cấu trúc gì cả cho các kho mã nguồn. Được xây dựng gọn gàng: không có file khổng lồ, không bị khóa vào nhà cung cấp, không đồng bộ đám mây.

```bash
uv tool install veles-ai          # installs the `veles` command
veles init && veles run "Summarize the project architecture."
veles        # interactive REPL (just run `veles` with no subcommand)
```

---

## Vì sao chọn Veles?

**Bộ nhớ tích lũy** — Mỗi phiên đều được Curator chắt lọc thành bộ nhớ riêng của từng dự án (insight, quy tắc hành vi, bản tóm tắt phiên trong `.veles/`). Agent tự động nhớ lại các sự kiện liên quan và những quyết định trong quá khứ — bạn không còn phải giải thích lại cùng một bối cảnh nữa. Bộ nhớ hoạt động dưới *bất kỳ* layout nội dung nào.

**Layout nội dung có thể tùy biến** — `veles init` mặc định dựng sẵn một wiki LLM kiểu Karpathy; `--layout notes` cho bạn một thư mục ghi chú phẳng; `--layout bare` không thêm cấu trúc nào cả (lý tưởng cho các kho mã nguồn). Các gói layout tùy chỉnh chỉ là một file TOML duy nhất trong `~/.veles/layouts/`.

**Định tuyến không phụ thuộc nhà cung cấp** — OpenRouter, Anthropic, OpenAI, Gemini, Ollama, llamacpp, hoặc gói thuê bao CLI `claude`/`gemini` của bạn. Các loại tác vụ khác nhau (lập kế hoạch, nén, trích xuất insight) có thể định tuyến đến các mô hình khác nhau.

**Kỹ năng tích lũy** — Các khối prompt tái sử dụng được trở thành công cụ của agent. Hãy promote một skill từ dự án lên cấp người dùng toàn cục và nó sẽ khả dụng ở mọi nơi. Tính năng khử trùng lặp tích hợp sẵn sẽ phát hiện các skill gần như trùng nhau trước khi chúng phân hóa.

**Local-first + sandbox** — Không thu thập dữ liệu, không đồng bộ đám mây. Agent chỉ nhìn thấy thư mục dự án đang hoạt động. Thang tin cậy (trust ladder) hỏi xác nhận cho từng lời gọi công cụ nhạy cảm; có thể cấp quyền trước cho CI.

**Mô-đun hóa, không phải khối liền** — Phần lõi tối giản (bộ nhớ, vòng lặp agent, giao thức nhà cung cấp, registry công cụ). Mọi thứ còn lại — TUI, daemon, gateway Telegram, deep research, bộ lập lịch tác vụ — đều là mô-đun tùy chọn, có thể nạp được.

---

## Bắt đầu nhanh

**Yêu cầu:** Python 3.13+, macOS / Linux (Windows ở mức cố gắng tối đa). Hãy cài [uv](https://docs.astral.sh/uv/) trước.

```bash
# 1. Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# 2. Install veles (the package is published as `veles-ai`; the command is `veles`)
uv tool install veles-ai
# …or from source:
#   git clone https://github.com/denisotree/veles.git && cd veles && uv tool install .

# 3. Set an API key — OpenRouter is recommended (access to all models, one key)
export OPENROUTER_API_KEY=sk-or-v1-...

# 4. Create a project
mkdir my-project && cd my-project
veles init

# 5. Talk to the agent
veles run "Read AGENTS.md and describe this project."
```

Hoặc mở REPL tương tác (chạy `veles` trống cũng cho kết quả tương tự):

```bash
veles
```

Trong lần chạy đầu tiên, trình hướng dẫn cài đặt sẽ dẫn bạn qua ngôn ngữ, nhà cung cấp LLM, khóa API, mô hình mặc định, chủ đề màu sắc, và việc có khởi tạo một dự án trong thư mục hiện tại hay không.

---

## Nhà cung cấp

| Nhà cung cấp | Biến môi trường | Ghi chú |
|---|---|---|
| **OpenRouter** *(khuyến nghị)* | `OPENROUTER_API_KEY` | Claude, GPT, Gemini, Llama — một key, hàng trăm mô hình |
| Anthropic | `ANTHROPIC_API_KEY` | API trực tiếp |
| OpenAI | `OPENAI_API_KEY` | API trực tiếp |
| Gemini | `GEMINI_API_KEY` hoặc `GOOGLE_API_KEY` | API trực tiếp |
| `claude` CLI | — | Dùng gói thuê bao Claude của bạn; không cần API key |
| `gemini` CLI | — | Dùng gói thuê bao Gemini của bạn; không cần API key |
| Ollama | — | Mô hình cục bộ, `http://localhost:11434/v1` |
| llamacpp | — | Mô hình cục bộ, `http://localhost:8080/v1` |
| openai-compat | `OPENAI_COMPAT_BASE_URL` | Bất kỳ endpoint nào tương thích OpenAI |

Ghi đè cho từng lần chạy:

```bash
veles run --provider anthropic --model anthropic/claude-opus-4-8 "..."
veles run --provider ollama --model llama3.2 "..."
```

Lưu các API key trong keychain của hệ điều hành thay vì biến môi trường:

```bash
veles secret set OPENROUTER_API_KEY    # prompts for value, stores in keychain
```

---

## Quy trình làm việc cốt lõi

### Chọn một layout nội dung

```bash
veles init                  # default: Karpathy-style LLM wiki (sources/ + wiki/)
veles init --layout notes   # a single flat notes/ directory
veles init --layout bare    # no content scaffold — code repos, free-form work
```

Bộ nhớ riêng của agent (insight, quy tắc, bản tóm tắt phiên trong `.veles/`) hoạt động y hệt nhau dưới mọi layout. Các gói tùy chỉnh chỉ là một file `layout.toml` trong `~/.veles/layouts/<name>/`.

### Xây dựng cơ sở tri thức (layout llm-wiki)

```bash
veles add paper.pdf                   # read a source → write a wiki page
veles add https://example.com/post    # web pages, PDFs, plain text

veles run "What do we know about the authentication design?"
veles curate                          # explicit session → memory consolidation
```

<p align="center">
  <img src="docs/assets/kb-ingest.gif" alt="Cơ sở tri thức Veles — nạp một nguồn vào trang wiki, sau đó đặt câu hỏi và nhận câu trả lời có trích dẫn nguồn đó" width="800">
</p>

Curator chạy tự động sau mỗi phiên. Quá trình trích xuất insight bắt được những cụm từ như "always prefer X" hay "never do Y" và ghi chúng thành các insight dự án bền vững.

### Deep research

```bash
veles research "What are the trade-offs between SQLite and PostgreSQL for this use case?"
```

Phân rã câu hỏi thành các câu hỏi con song song, khảo sát từng câu, rồi tổng hợp thành một báo cáo có cấu trúc.

### Mục tiêu chạy dài

```bash
veles goal start "Migrate auth module to the new provider" --max-cost-usd 2.00
veles goal list
veles goal checkpoint <id> "Completed step 1: identified all call sites"
```

### Tác vụ theo lịch

```bash
veles job add --name "weekly-review" --schedule "0 9 * * 1" --prompt "Generate a weekly progress summary"
veles job list
```

---

## Định tuyến mô hình (Ensembles)

Định tuyến các loại tác vụ khác nhau đến các mô hình khác nhau — cài đặt một lần rồi quên đi.

**Qua CLI:**
```bash
veles route show                                          # current routing table
veles route set compressor anthropic/claude-haiku-4-5    # typed override
veles route reset compressor                             # back to default
```

**Qua ngôn ngữ tự nhiên trong `AGENTS.md`:**
```markdown
## Routing
Use Opus for planning and architecture decisions.
Haiku is fine for compression and insight extraction.
```

```bash
veles route refresh    # parse the NL hints; typed overrides always win
```

---

## Kỹ năng và Mô-đun

**Kỹ năng** (Skills) là các khối prompt tái sử dụng được (`SKILL.md`), tự động trở thành công cụ của agent.

```bash
veles skill add https://github.com/org/skill-repo    # install from git
veles skill add ./local-skill-dir                    # or from local path
veles skill list                                     # list with telemetry
veles skill promote my-skill                         # copy to ~/.veles/skills (global)
veles skill dedup                                    # find near-duplicates
veles skill suggest-promote --save                   # propose promotions based on usage
```

**Mô-đun** (Modules) là các plugin Python có thể móc vào vòng đời của agent (`pre_turn`, `post_turn`, `pre_tool_call`, `post_tool_call`) và phủ quyết việc điều phối công cụ.

```bash
veles module add https://github.com/org/module-repo
veles module list
```

---

## Phiên tương tác (REPL)

```bash
veles                        # new session (bare `veles` launches the interactive REPL)
veles -c                     # continue the most recent session in this project
veles --resume <id>          # resume a specific session
```

<p align="center">
  <img src="docs/assets/tui-tour.gif" alt="Veles REPL — các slash inspector (/status, /context), chuyển đổi chế độ, và bảng lệnh" width="800">
</p>

Các lệnh slash hiển thị mọi thứ trực tiếp — `/status`, `/tokens`, `/context`, `/mode`, `/help` — và `Shift+Tab` chuyển vòng giữa các chế độ (auto / planning / writing / goal).

| Phím | Hành động |
|---|---|
| `Enter` | Gửi tin nhắn |
| `Shift+Enter` | Xuống dòng trong ô soạn thảo |
| `Ctrl+I` | Bật/tắt trình kiểm tra hoạt động công cụ |
| `Ctrl+R` | Lớp phủ chọn phiên |
| `Ctrl+G` | Mở `$EDITOR` với bản nháp hiện tại |
| `Tab` | Tự động hoàn thành lệnh slash |
| `Ctrl+D` | Thoát |

Các lệnh slash: `/help` · `/model` · `/mode` · `/status` · `/tokens` · `/context` · `/wiki` · `/save <slug>` · `/history` · `/insights` · `/rules` · `/daemon` và nhiều lệnh khác.

---

## Daemon + Telegram

Chạy Veles như một daemon thường trực với API HTTP/WebSocket. Trong một thư mục dự án mới, `veles daemon start` sẽ dẫn bạn qua quá trình cài đặt — khởi tạo dự án, bật daemon, và **kết nối một kênh**: trước tiên chọn *loại* kênh (Telegram là nền tảng duy nhất hiện nay, nhưng trình chọn là điểm nối nơi các kênh mới đăng ký vào), sau đó điền các trường của kênh đó (bot token, danh sách trắng). Không cần phải mở TUI trước.

<p align="center">
  <img src="docs/assets/daemon-setup.gif" alt="veles daemon start — trình hướng dẫn khởi động daemon và kết nối một kênh Telegram (chọn loại kênh trước, rồi đến token và danh sách trắng của nó)" width="800">
</p>

```bash
veles daemon start                        # wizard (fresh dir) → starts on 127.0.0.1:8765
veles daemon status                       # is it running?
veles daemon list                         # daemons across all projects
```

Chạy `veles daemon` trống sẽ mở một bảng điều khiển trực tiếp — một cây project → daemons → channels. Khởi động, dừng, khởi động lại, hoặc xóa các daemon, và thêm/gỡ các kênh (vẫn theo luồng chọn loại kênh trước, phím `c`) trên mọi dự án, tất cả đều từ bàn phím:

<p align="center">
  <img src="docs/assets/daemon-panel.gif" alt="veles daemon — TUI bảng điều khiển: cây project → daemons → channels với các thao tác start/stop/restart/delete và quản lý kênh ngay tại chỗ" width="800">
</p>

Cùng trình hướng dẫn kênh đó cũng có sẵn ở dạng độc lập (`veles channel add`) trên một dự án đang chạy.

Các endpoint API: `POST /v1/runs` để gửi một prompt, `WS /v1/runs/{id}/events` để stream phản hồi, `GET /v1/sessions` để liệt kê các phiên. Tất cả ngoại trừ `GET /v1/health` đều yêu cầu `Authorization: Bearer <token>` (tạo một token bằng `veles daemon token add <name>`).

Mỗi người dùng Telegram nhận được một phiên thường trực. Dùng `veles channel list-sessions` / `reset-session` để quản lý các ánh xạ.

---

## Đa dự án

```bash
veles project list                       # registered projects
veles project switch <slug>              # print the absolute path
cd $(veles project switch <slug>)        # jump to a project

veles subproject init frontend           # create a child project
veles subproject suggest --save          # agent-detected topic clusters → proposals
```

---

## Tin cậy và An toàn

Mỗi lời gọi công cụ nhạy cảm (thực thi shell, ghi file, tải URL) đều hỏi xác nhận:

```
Tool 'run_shell' wants to execute. Allow?
  [1] Once  [2] Always for this project  [3] Always everywhere  [4] Refuse
```

Cấp quyền trước cho CI hoặc các lần chạy tự động kéo dài:

```bash
veles trust set run_shell --scope project   # pre-grant for this project
veles autopilot enable --until +2h          # temporary trust bypass (audit-logged)
veles autopilot disable
```

Agent chỉ nhìn thấy thư mục dự án đang hoạt động — các dự án khác, việc thoát ra qua symlink, và phép duyệt `..` đều bị chặn.

---

## Xuất / Nhập

```bash
veles export full ./backup.tar.gz        # full backup: memory, sessions, telemetry
veles export template ./template.tar.gz  # sanitised template (no sources/sessions/PII)
veles import ./backup.tar.gz --into ./new-dir
```

---

## Tham chiếu CLI

| Lệnh | Mục đích |
|---|---|
| `veles init [name]` | Tạo một dự án mới |
| `veles run "<prompt>"` | Lần chạy agent một lượt |
| `veles` | REPL tương tác (không có lệnh con) |
| `veles add <file\|url>` | Nạp một nguồn → các trang wiki theo chủ đề |
| `veles organize` | Tổ chức lại nội dung dự án theo layout đang dùng (đề xuất rồi áp dụng) |
| `veles research "<question>"` | Nghiên cứu sâu nhiều góc độ |
| `veles curate` | Hợp nhất các phiên vào wiki |
| `veles sessions {list,show,delete,search}` | Quản lý phiên |
| `veles skill {list,show,add,remove,promote,demote,dedup,suggest-promote}` | Quản lý kỹ năng |
| `veles tool {list,show,promote,approve}` | Quản lý công cụ (`approve` phê duyệt các công cụ tự tạo) |
| `veles module {list,add,remove}` | Quản lý plugin |
| `veles browse {modules,skills}` | Tìm kiếm registry module / kỹ năng đã tuyển chọn |
| `veles route {show,set,reset,refresh}` | Định tuyến mô hình |
| `veles schema {validate,edit}` | Kiểm tra / chỉnh sửa AGENTS.md |
| `veles self-doc` | Tạo tài liệu tự mô tả cho dự án |
| `veles layout {sync}` | Bảo trì gói layout |
| `veles goal {list,show,start,checkpoint,pause,resume,done,cancel}` | Mục tiêu dài hạn |
| `veles job {list,add,show,pause,resume,trigger,remove,history}` | Tác vụ theo lịch |
| `veles dream` | Chu kỳ hợp nhất bộ nhớ nền |
| `veles project {list,add,remove,switch}` | Registry đa dự án |
| `veles subproject {init,list,switch,remove,suggest}` | Dự án con |
| `veles trust {list,set,revoke,clear}` | Cấp quyền tin cậy |
| `veles autopilot {enable,disable,status}` | Bỏ qua tin cậy tạm thời |
| `veles secret {set,get,list,delete}` | Bí mật trong keychain hệ điều hành |
| `veles daemon {start,stop,status,list,restart,delete,session,token}` | Daemon HTTP/WS |
| `veles channel {list,run,list-sessions,reset-session,add,remove}` | Gateway kênh bên ngoài |
| `veles mcp {list,test}` | Máy chủ MCP bên ngoài |
| `veles models <provider>` | Liệt kê mô hình của nhà cung cấp |
| `veles doctor` | Kiểm tra sức khỏe |
| `veles export / import` | Sao lưu và chuyển giao dự án |

Mọi lệnh đều có `--help`.

---

## Tài liệu

Tài liệu đầy đủ — tổ chức theo Diátaxis (hướng dẫn nhập môn · hướng dẫn thực hành · tham chiếu · giải thích):

- **Tiếng Việt:** [`docs/vi/index.md`](docs/vi/index.md)

Ngôn ngữ khác: dùng bộ chuyển 🌐 ở đầu bất kỳ trang tài liệu nào.

---

## Đóng góp

Rất hoan nghênh các đóng góp — Veles được **xây dựng để mở rộng**. Phần lõi vẫn nhỏ gọn (vòng lặp agent + bộ nhớ dự án + giao thức nhà cung cấp); gần như mọi thứ khác đều là một điểm mở rộng có thể cắm vào, nên việc thêm một khả năng mới hiếm khi đụng đến phần lõi:

- **Bộ điều hợp nhà cung cấp** (`src/veles/adapters/`) — kết nối một backend mô hình mới.
- **Kỹ năng** — các khối prompt và công cụ tái sử dụng được với thừa kế `extends:`, có thể promote từ dự án lên cấp người dùng toàn cục.
- **Công cụ** — Python có kiểu mà agent tự viết và tái sử dụng, nằm dưới `<project>/.veles/tools/`.
- **Gói layout** — một file `layout.toml` duy nhất trong `~/.veles/layouts/<name>/` định nghĩa nguyên một layout nội dung.
- **Hook mô-đun** — khả năng quan sát, ghi log, và chính sách thông qua các hook `pre_turn` / `post_turn` (`src/veles/core/modules.py`).
- **Kênh & máy chủ MCP** — các gateway mới và nguồn công cụ bên ngoài.
- **Bản địa hóa** — các bản dịch trong `src/veles/locales/`.

```bash
git clone https://github.com/denisotree/veles.git && cd veles
uv sync                              # runtime + dev dependencies
uv run pytest                        # the full suite (3200+ tests, no network)
uv run ruff check src tests && uv run mypy
```

Codebase được phân tách có chủ đích — mỗi phần một trách nhiệm, không có file khổng lồ. Hãy đọc [`CONTRIBUTING.md`](CONTRIBUTING.md) để biết các quy ước và [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md) trước khi mở một PR. Những đóng góp đầu tiên phù hợp: bộ điều hợp nhà cung cấp, kỹ năng quy trình làm việc, hook mô-đun, và file bản địa hóa.

---

## Giấy phép

Apache 2.0 kèm cấp phép sáng chế — xem [`LICENSE`](LICENSE) và [`NOTICE`](NOTICE).

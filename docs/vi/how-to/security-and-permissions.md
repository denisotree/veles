# Cách quản lý bảo mật: trust, autopilot, secret

> 🌐 **Ngôn ngữ:** [English](../../en/how-to/security-and-permissions.md) · [简体中文](../../zh-CN/how-to/security-and-permissions.md) · [繁體中文](../../zh-TW/how-to/security-and-permissions.md) · [日本語](../../ja/how-to/security-and-permissions.md) · [한국어](../../ko/how-to/security-and-permissions.md) · [Español](../../es/how-to/security-and-permissions.md) · [Français](../../fr/how-to/security-and-permissions.md) · [Italiano](../../it/how-to/security-and-permissions.md) · [Português (BR)](../../pt-BR/how-to/security-and-permissions.md) · [Português (PT)](../../pt-PT/how-to/security-and-permissions.md) · [Русский](../../ru/how-to/security-and-permissions.md) · [العربية](../../ar/how-to/security-and-permissions.md) · [हिन्दी](../../hi/how-to/security-and-permissions.md) · [বাংলা](../../bn/how-to/security-and-permissions.md) · **Tiếng Việt**

Veles kiểm soát các hành động nguy hiểm thông qua một **thang trust**, đặt việc
truy cập tệp trong sandbox, và giữ secret trong keychain của hệ điều hành. Để hiểu
lý do, xem [trust & sandbox](../explanation/trust-and-sandbox.md).

## Thang trust

Các công cụ nhạy cảm (`run_shell`, `write_file`, `fetch_url`, …) sẽ hỏi trước khi
chạy. Bạn chọn: cho phép **một lần**, **luôn luôn cho dự án này**, **luôn luôn ở mọi
nơi**, hoặc **từ chối**. Các quyền được cấp sẽ được lưu lại nên bạn không bị hỏi lại.

Quản lý các quyền đã cấp mà không cần đợi lời nhắc:

```bash
veles trust list                          # current grants (user + project)
veles trust set run_shell --scope project # pre-grant for this project
veles trust set write_file --scope user   # pre-grant everywhere
veles trust revoke run_shell              # remove a grant
veles trust clear --scope all             # wipe everything
```

Một số hành động **luôn được xác nhận lại** ngay cả khi đã được cấp quyền — xóa
tệp, tải URL, cài đặt một skill/tool/module mới, kết nối một kênh, và ghi
ra ngoài phạm vi dự án.

## Autopilot — bỏ qua trong khung thời gian giới hạn

Đối với một lần chạy không giám sát (một batch chạy qua đêm), hãy mở một khung thời
gian mà các lời nhắc trust được tự động cho phép:

```bash
veles autopilot enable --until +2h
veles autopilot enable --until 2026-12-31T23:00:00Z
veles autopilot status
veles autopilot disable
```

Mọi hành động autopilot đều được ghi log để xem lại sau. Các ngữ cảnh không tương
tác (daemon, batch) mặc định từ chối, trừ khi autopilot đang bật.

## Secret

API key và bot token nằm trong keychain của hệ điều hành, không bao giờ nằm trong
các tệp cấu hình:

```bash
veles secret set OPENROUTER_API_KEY       # prompts (or pipe via stdin)
veles secret list                         # which secrets are configured
veles secret get OPENROUTER_API_KEY --reveal
veles secret delete OPENROUTER_API_KEY
veles secret set OPENROUTER_API_KEY --project myproj   # a key for one project only
```

Việc tra cứu sẽ dự phòng về [biến môi trường](../reference/environment-variables.md)
tương ứng, trừ khi bạn truyền `--no-env-fallback`.

## Sandbox

Các công cụ có thể đọc bên trong dự án đang hoạt động, `~/.veles/skills/` và
`~/.veles/locales/`, và chỉ ghi được bên trong dự án — hoặc chỉ vào các vùng cho phép
ghi của layout, khi layout có khai báo. Ghi đè các root cho những thiết lập nâng cao
bằng `VELES_SANDBOX_ROOTS` (ngăn cách bằng `:`). Việc tải URL duy trì một danh sách
chặn SSRF; `VELES_FETCH_ALLOW_PRIVATE=1` gỡ bỏ chặn mạng riêng (private network).

Bên trong `.veles/` của dự án, các công cụ tệp của agent chỉ được ghi vào `skills/`,
`tools/`, `tmp/`, `plans/`, `memory/` và `artifacts/`. Mọi thứ còn lại ở đó —
`trust.json`, `config.toml`, `project.toml`, `modules/`, `wiki.toml`, `memory.db` —
chỉ thay đổi qua các lệnh `veles` và các công cụ của chính Veles. Các công cụ tệp
cũng từ chối mọi thư mục `.veles/` khác trong dự án (của một subproject, hoặc một
thư mục agent cố cài vào `wiki/`) ở bất kỳ độ sâu nào. Vì vậy, qua các công cụ tệp,
agent không thể tự cấp quyền tin cậy cho mình hay thêm mã mà Veles sẽ chạy (một công
cụ nó ghi vào `.veles/tools/` chỉ được nạp sau khi bạn duyệt tệp của nó). Các cách
viết khác của cùng một tệp (hoa/thường, `..`, symlink) cũng bị từ chối.

Các tệp tự chạy mà không cần lệnh tường minh, hoặc điều khiển một agent CLI — mọi thứ
dưới `.git/`, `.githooks/`, `.claude/`, `.gemini/`, `.agents/`, `.codex/`, `.vscode/`,
`.devcontainer/`, `.husky/`, và `.envrc`, `.mcp.json`, `.pre-commit-config.yaml`,
`lefthook.yml`, ở bất kỳ độ sâu nào, cộng với thư mục `core.hooksPath` của repo và
nơi một `.git` dạng symlink trỏ tới — các công cụ tệp của agent chỉ ghi sau khi bạn
xác nhận lần ghi đó. Các quyền trust và autopilot không bao gồm việc này; daemon hỏi
trong kênh, còn một lần chạy batch không có ai để hỏi thì từ chối.

Các provider `claude-cli`, `codex` và `antigravity-cli` chạy như một model chỉ với các công cụ
của Veles: shell, công cụ sửa tệp và web riêng của chúng, cài đặt và hook `.claude/` của
dự án, cùng các máy chủ MCP khác đều không áp dụng, và mọi công cụ Veles chúng gọi
đều đi qua thang trust ở trên (ở đó không ai trả lời được prompt, nên bất cứ thứ gì
chưa được cấp đều bị từ chối). Config MCP của chúng nằm trong
`.veles/tmp/delegate-<pid>/`, mỗi tiến trình đang chạy một thư mục, mà các công cụ tệp
của agent không ghi vào được. `agy` chạy trong một workspace tạm bên ngoài dự án, dưới
`~/.veles/tmp/`, nên các hook và máy chủ MCP trong `.agents/` của chính dự án không bao
giờ đến được nó. Nó chạy kèm `--dangerously-skip-permissions` khi có các công cụ của
Veles — nếu không agy từ chối các lệnh gọi MCP ở chế độ headless — và một hook trong
workspace đó từ chối mọi công cụ của chính nó; một hook bị lỗi cũng từ chối. Các công
cụ tệp của Veles không ghi ra ngoài dự án, nên agy không thể ghi đè hook đó qua chúng. `codex` cũng chạy bên ngoài dự án, với
config codex của bạn bị bỏ qua, một sandbox chỉ đọc và các công cụ riêng của nó bị tắt
bằng các feature flag mà Veles kiểm tra tên trước mỗi lần chạy đầu tiên — một codex đã
đổi tên flag mà nó phụ thuộc sẽ bị từ chối, không được chạy ở trạng thái mở. MCP server
của nó nằm trong tham số (không có tệp config), chỉ các công cụ của server đó được phê
duyệt, và môi trường server đó nhận được được chuyển tiếp theo tên — không bao giờ là
`VELES_TRUST_AUTO_ALLOW`.

Các giới hạn đã biết:

- `run_shell` là một shell: một khi bạn cấp quyền cho nó (hoặc dưới autopilot), nó có
  thể ghi bất kỳ tệp nào ở trên mà không cần xác nhận theo từng tệp — và cả các kho
  phê duyệt trong `~/.veles/`. `veles … approve` cần một terminal hoặc hash đã được xem
  xét (`--sha256`) và từ chối lệnh do shell của agent khởi chạy, nhưng một shell đã
  được cấp quyền vẫn có thể gỡ dấu đó hoặc ghi trực tiếp vào các tệp đó.
- Một phê duyệt MCP ghim dòng lệnh của máy chủ, không ghim các tệp nó chạy từ dự án
  (một script nêu trong `args`) — hãy xem xét cả chúng.
- Với một provider CLI, các lần chạy chỉ tiền cấp quyền công cụ cho riêng mình (tác vụ
  nền của daemon, `veles research`) không truyền điều đó cho CLI được ủy quyền: việc
  tiền cấp quyền nằm trong tiến trình Veles, còn máy chủ MCP mà CLI khởi động là một
  tiến trình riêng, nên các công cụ Veles của nó cần một quyền cấp thường trực
  `veles trust set` hoặc một cửa sổ autopilot. Chế độ lập kế hoạch của lần chạy cha
  cũng không tới được chúng.
- `antigravity-cli` dựa vào việc agy tôn trọng `.agents/hooks.json` của workspace nó;
  một bản phát hành agy ngừng đọc hook của workspace sẽ để các công cụ riêng của nó
  mở dưới `--dangerously-skip-permissions`.

Đường dẫn chứa ký tự điều khiển (chuỗi escape của terminal, ký tự đảo chiều bidi) bị
từ chối, còn các xác nhận, lời nhắc trust và bản xem trước diff hiển thị các ký tự đó
ở dạng đã escape — một lệnh gọi công cụ không thể làm giả văn bản bạn duyệt.

Các máy chủ MCP trong cấu hình chỉ khởi động sau khi bạn duyệt chúng — xem
[các máy chủ MCP bên ngoài](external-mcp-servers.md).

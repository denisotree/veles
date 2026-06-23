# Cách kết nối các máy chủ MCP bên ngoài

> 🌐 **Ngôn ngữ:** [English](../../en/how-to/external-mcp-servers.md) · [Русский](../../ru/how-to/external-mcp-servers.md) · **Tiếng Việt**

Veles là một **client** [MCP](https://modelcontextprotocol.io/): nó có thể kết nối tới
các máy chủ MCP bên ngoài và cung cấp các công cụ của chúng cho agent như thể chúng được tích hợp sẵn
(GitHub, tài liệu thư viện, tìm kiếm web, các dịch vụ của riêng bạn, …).

## Cấu hình một máy chủ

Thêm một khối `[mcp.servers.<name>]` vào `<project>/.veles/config.toml` (hoặc
tệp cấu hình toàn cục của người dùng `~/.veles/config.toml`). `<name>` phải khớp với
`[A-Za-z0-9][A-Za-z0-9_-]{0,31}` — nó trở thành một phần trong tên của mỗi công cụ. Có ba
phương thức truyền tải (transport) được hỗ trợ: `stdio` (mặc định), `http`, `sse`.

| Khóa | Transport | Mặc định | Mục đích |
|---|---|---|---|
| `transport` | — | `"stdio"` | `stdio` \| `http` \| `sse` |
| `command` | stdio (bắt buộc) | — | chương trình thực thi cần khởi chạy — **chỉ chương trình, không bao gồm tham số** |
| `args` | stdio | `[]` | danh sách tham số, mỗi token là một mục |
| `env` | stdio | `{}` | biến môi trường bổ sung cho tiến trình con (gộp đè lên môi trường kế thừa) |
| `url` | http/sse (bắt buộc) | — | endpoint của máy chủ |
| `timeout_s` | — | `120` | ngân sách cho một lần gọi công cụ |
| `connect_timeout_s` | — | `30` | ngân sách cho lần kết nối ban đầu |
| `enabled` | — | `true` | đặt `false` để giữ lại mục cấu hình nhưng bỏ qua việc kết nối |

Các giá trị chuỗi trong `command`, `args`, `env`, và `url` sẽ nội suy `${VAR}` từ
môi trường (một biến chưa được đặt sẽ trở thành chuỗi rỗng kèm cảnh báo) — hãy giữ
các thông tin bí mật bên ngoài tệp cấu hình.

> **`command` so với `args`.** Veles chạy chương trình trực tiếp (không qua shell), nên
> chương trình thực thi và các tham số của nó là các trường **riêng biệt**. Hãy viết
> `command = "npx"`, `args = ["-y", "pkg"]` — **chứ không phải** `command = "npx -y pkg"`.

### stdio (tiến trình con cục bộ)

```toml
[mcp.servers.github]
transport = "stdio"
command = "npx"
args = ["-y", "@modelcontextprotocol/server-github"]
env = { GITHUB_TOKEN = "${GITHUB_TOKEN}" }
```

Một máy chủ do chính bạn vận hành cũng hoạt động theo cách tương tự — trỏ `command`/`args` tới nó:

```toml
[mcp.servers.mytools]
transport = "stdio"
command = "python"
args = ["-m", "my_mcp_server"]
```

### Một máy chủ cần API key (context7)

[Context7](https://context7.com) cung cấp tài liệu thư viện được cập nhật mới nhất. Truyền
key dưới dạng tham số để `${VAR}` giữ nó bên ngoài tệp:

```toml
[mcp.servers.context7]
transport = "stdio"
command = "npx"
args = ["-y", "@upstash/context7-mcp", "--api-key", "${CONTEXT7_API_KEY}"]
```

```bash
export CONTEXT7_API_KEY=...   # then start veles
```

### http / sse (từ xa)

```toml
[mcp.servers.search]
transport = "http"            # streamable HTTP; use "sse" for an SSE endpoint
url = "https://mcp.example.com/mcp"
```

> **Chưa hỗ trợ header tùy chỉnh.** Các transport `http`/`sse` chỉ gửi `url` —
> Veles không thể đính kèm header `Authorization`. Đối với một máy chủ từ xa cần
> key, hãy ưu tiên biến thể `stdio` của nó (ví dụ `npx`) với key đặt trong `args`/`env`, hoặc một
> endpoint chấp nhận key ngay trong URL.

## Ẩn các công cụ cụ thể

Đặt `[mcp] disabled_tools` — một bảng ánh xạ mỗi máy chủ tới tên các công cụ cần bỏ qua:

```toml
[mcp]
disabled_tools = { github = ["delete_repository"], search = ["raw_query"] }
```

## Kiểm tra và thử nghiệm

```bash
veles mcp list              # every configured server: transport, status, tool count
veles mcp test github       # connect to one server and list its tools
```

`veles mcp list` luôn thoát với mã 0 — nó là một công cụ kiểm tra, không phải cổng kiểm tra sức khỏe.
`veles mcp test` thoát với mã 1 khi kết nối thất bại và mã 2 khi tên máy chủ không xác định.

## Cách các công cụ xuất hiện

Sau khi được cấu hình, các máy chủ sẽ được gắn kết (mount) **tự động** trong lần `veles run` /
khởi động TUI / khởi động daemon kế tiếp — không có cờ "bật MCP" riêng biệt, sự hiện diện của
cấu hình chính là công tắc. Mỗi công cụ được đưa vào registry thông thường dưới dạng `mcp_<server>_<tool>`
và có thể được agent gọi như bất kỳ công cụ tích hợp sẵn nào. Các schema được làm sạch (giới hạn
tên/độ dài, loại bỏ ký tự điều khiển) để một máy chủ không đáng tin cậy không thể chèn nội dung vào prompt.
Các gợi ý (hint) của công cụ được ánh xạ tới thang tin cậy: các công cụ có tính phá hủy luôn yêu cầu xác nhận, các công cụ
chỉ đọc không yêu cầu hỏi, mọi thứ còn lại đi qua luồng
[tin cậy](security-and-permissions.md) thông thường — cấp quyền phê duyệt thường trực bằng
`veles trust set` nếu bạn không muốn bị hỏi mỗi lần.

## Xử lý lỗi

Một máy chủ kết nối thất bại — do thiếu `command`, sai `url`, hoặc bất kỳ mục cấu hình
không hợp lệ nào — sẽ được ghi log dưới dạng cảnh báo và bỏ qua. Nó không bao giờ chặn quá trình khởi động hay agent.
Chạy lại `veles mcp list` để xem trạng thái và lỗi.

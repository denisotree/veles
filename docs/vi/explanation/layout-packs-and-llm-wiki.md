# Layout pack & LLM-Wiki

> 🌐 **Ngôn ngữ:** [English](../../en/explanation/layout-packs-and-llm-wiki.md) · [简体中文](../../zh-CN/explanation/layout-packs-and-llm-wiki.md) · [繁體中文](../../zh-TW/explanation/layout-packs-and-llm-wiki.md) · [日本語](../../ja/explanation/layout-packs-and-llm-wiki.md) · [한국어](../../ko/explanation/layout-packs-and-llm-wiki.md) · [Español](../../es/explanation/layout-packs-and-llm-wiki.md) · [Français](../../fr/explanation/layout-packs-and-llm-wiki.md) · [Italiano](../../it/explanation/layout-packs-and-llm-wiki.md) · [Português (BR)](../../pt-BR/explanation/layout-packs-and-llm-wiki.md) · [Português (PT)](../../pt-PT/explanation/layout-packs-and-llm-wiki.md) · [Русский](../../ru/explanation/layout-packs-and-llm-wiki.md) · [العربية](../../ar/explanation/layout-packs-and-llm-wiki.md) · [हिन्दी](../../hi/explanation/layout-packs-and-llm-wiki.md) · [বাংলা](../../bn/explanation/layout-packs-and-llm-wiki.md) · **Tiếng Việt**

Một **layout pack** định nghĩa cách *nội dung người dùng* của một dự án được tổ chức
— có những thư mục nào, thư mục nào tác tử được phép ghi vào, và nó cung cấp những
thao tác nào. Mặc định là **`bare`**, không thêm gì vào thư mục của bạn ngoài
`.veles/` và `AGENTS.md`. **LLM-Wiki** là một tùy chọn từ registry tiện ích mở
rộng, **không phải** một nguyên tắc lõi của Veles.

## Layout pack là gì

Một layout pack là một thư mục chứa manifest `layout.toml` (cùng các tệp kỹ năng và
template tùy chọn). Manifest khai báo:

- **Vùng ghi được (writable zones)** — các thư mục mà tác tử được phép ghi nội dung
  vào (được áp đặt trên mỗi lần `write_file`).
- **Vùng chỉ-đọc (read-only zones)** — tài liệu mà tác tử đọc nhưng không bao giờ sửa.
- **Thao tác (operations)** — các workflow được đặt tên, đi kèm dưới dạng kỹ năng
  bên trong pack.
- **Scaffold** (`[layout.scaffold]`) — những gì `veles init` tạo ra: các thư mục và
  một template `AGENTS.md` tùy chọn (`{name}` được thay thế).
- **Engine** (`[layout.engines]`) — phần máy móc nội dung nào mà pack yêu cầu.
  Một engine do một module cung cấp (module `wiki` của registry cung cấp `wiki`).
  Nếu không có nó, dự án sẽ không có công cụ wiki, không có recall wiki, không có
  việc chèn INDEX.
- **Tệp ngữ cảnh (context file)** (`context_file`) — một tệp được chèn vào system
  prompt ổn định của tác tử (LLM-Wiki dùng `INDEX.md`).

## Các pack có sẵn

| Pack | Lấy từ đâu | Những gì `veles init --layout <name>` tạo ra |
|---|---|---|
| `bare` *(mặc định)* | tích hợp sẵn | Hoàn toàn không có scaffold nội dung — dành cho các repo mã nguồn và công việc tự do. Việc ghi được cho phép thoải mái bên trong thư mục gốc của dự án (vẫn chịu sự kiểm soát của trust ladder). |
| `llm-wiki` | registry (`public:official/llm-wiki`, kéo theo module `wiki`) | [LLM-Wiki theo phong cách Karpathy](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f): `sources/` (thô, chỉ-đọc theo quy ước — không bị áp đặt), `wiki/` (tác tử ghi được), `INDEX.md` được chèn vào prompt, các kỹ năng `ingest`/`query`/`lint`/`organize`/`structure_design`, engine wiki được bật, cùng `veles add` và `/wiki`. Một prompt hành vi do layout khai báo (`templates/behaviour.md`) mang kỷ luật sources/wiki và các quy tắc migration/log-patch. |
| `notes` | registry (`public:official/notes`) | Một thư mục phẳng `notes/` duy nhất để tác tử ghi vào. Không có máy móc wiki. |

`veles init` tại terminal sẽ hỏi dùng pack nào (các pack đã cài và các pack có
trong registry của bạn); chọn một pack chưa cài sẽ đề nghị cài nó.
`veles registry install llm-wiki` cài sẵn từ trước.

## Dự án từ trước 1.2.3

Một dự án có layout chưa được cài (dự án `llm-wiki` sau khi nâng cấp, hoặc dự án
không có khóa `layout` — tất cả đều từng là dự án wiki) vẫn mở bình thường. Tại
terminal, `veles` và `veles run` đề nghị cài pack (cùng engine nó cần) chỉ với một
lần xác nhận; ở nơi khác — daemon, kênh, các verb khác — Veles in lệnh cài đặt một
lần và hoạt động không có wiki. Không có gì trong `wiki/` bị động đến.

## Layout tùy chỉnh

Đặt một pack vào `~/.veles/layouts/<name>/layout.toml` (toàn cục theo người dùng)
hoặc `<project>/.veles/layouts/<name>/` (cục bộ theo dự án; che khuất các pack cùng
tên ở mức người dùng và tích hợp sẵn) rồi truyền `veles init --layout <name>`. Pack
`notes` của registry là ví dụ tối thiểu để sao chép. Một pack yêu cầu engine mà không
module nào đã cài cung cấp cũng nhận được đề nghị cài đặt tương tự. Bạn cũng có thể mô tả các quy ước
trong `AGENTS.md` — layout áp đặt các vùng, còn AGENTS.md hướng dẫn hành vi.

## Những gì nó *không phải*

Layout chỉ quản lý **nội dung của bạn**. Bộ nhớ dự án của riêng Veles —
`memory.db` cùng cây artefact `.veles/memory/` (insight, bản tóm tắt phiên,
proposal, nhật ký vận hành hệ thống) — nằm ở phía hệ thống và hoạt động giống hệt
nhau dưới mọi layout. Việc chuyển layout không bao giờ động đến vòng lặp học, các
phiên, hay các registry. Xem [kiến trúc](architecture.md) và
[bố cục dự án](../reference/project-layout.md).

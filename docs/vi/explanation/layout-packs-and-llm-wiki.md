# Layout pack & LLM-Wiki

> 🌐 **Ngôn ngữ:** [English](../../en/explanation/layout-packs-and-llm-wiki.md) · [简体中文](../../zh-CN/explanation/layout-packs-and-llm-wiki.md) · [繁體中文](../../zh-TW/explanation/layout-packs-and-llm-wiki.md) · [日本語](../../ja/explanation/layout-packs-and-llm-wiki.md) · [한국어](../../ko/explanation/layout-packs-and-llm-wiki.md) · [Español](../../es/explanation/layout-packs-and-llm-wiki.md) · [Français](../../fr/explanation/layout-packs-and-llm-wiki.md) · [Italiano](../../it/explanation/layout-packs-and-llm-wiki.md) · [Português (BR)](../../pt-BR/explanation/layout-packs-and-llm-wiki.md) · [Português (PT)](../../pt-PT/explanation/layout-packs-and-llm-wiki.md) · [Русский](../../ru/explanation/layout-packs-and-llm-wiki.md) · [العربية](../../ar/explanation/layout-packs-and-llm-wiki.md) · [हिन्दी](../../hi/explanation/layout-packs-and-llm-wiki.md) · [বাংলা](../../bn/explanation/layout-packs-and-llm-wiki.md) · **Tiếng Việt**

Một **layout pack** định nghĩa cách *nội dung người dùng* của một dự án được tổ chức
— có những thư mục nào, thư mục nào tác tử được phép ghi vào, và nó cung cấp những
thao tác nào. Mặc định là **LLM-Wiki**. Đây là một tùy chọn về nội dung, **không
phải** một nguyên tắc lõi của Veles.

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
- **Engine** (`[layout.engines]`) — phần máy móc nội dung lõi nào mà pack kích hoạt.
  Hiện tại có một engine: `wiki`. Nếu không có nó, dự án sẽ không có công cụ wiki,
  không có recall wiki, không có việc chèn INDEX.
- **Tệp ngữ cảnh (context file)** (`context_file`) — một tệp được chèn vào system
  prompt ổn định của tác tử (LLM-Wiki dùng `INDEX.md`).

## Các pack tích hợp sẵn

| Pack | Những gì `veles init --layout <name>` tạo ra |
|---|---|
| `llm-wiki` *(mặc định)* | [LLM-Wiki theo phong cách Karpathy](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f): `sources/` (chỉ-đọc), `wiki/` (tác tử ghi được), `INDEX.md` được chèn vào prompt, các kỹ năng `ingest`/`query`/`lint`, engine wiki được bật. |
| `notes` | Một thư mục phẳng `notes/` duy nhất để tác tử ghi vào. Không có máy móc wiki. |
| `bare` | Hoàn toàn không có scaffold nội dung — dành cho các repo mã nguồn và công việc tự do. Việc ghi được cho phép thoải mái bên trong thư mục gốc của dự án (vẫn chịu sự kiểm soát của trust ladder). |

## Layout tùy chỉnh

Đặt một pack vào `~/.veles/layouts/<name>/layout.toml` (toàn cục theo người dùng)
hoặc `<project>/.veles/layouts/<name>/` (cục bộ theo dự án; che khuất các pack cùng
tên ở mức người dùng và tích hợp sẵn) rồi truyền `veles init --layout <name>`. Pack
tích hợp `notes` là ví dụ tối thiểu để sao chép. Bạn cũng có thể mô tả các quy ước
trong `AGENTS.md` — layout áp đặt các vùng, còn AGENTS.md hướng dẫn hành vi.

## Những gì nó *không phải*

Layout chỉ quản lý **nội dung của bạn**. Bộ nhớ dự án của riêng Veles —
`memory.db` cùng cây artefact `.veles/memory/` (insight, bản tóm tắt phiên,
proposal, nhật ký vận hành hệ thống) — nằm ở phía hệ thống và hoạt động giống hệt
nhau dưới mọi layout. Việc chuyển layout không bao giờ động đến vòng lặp học, các
phiên, hay các registry. Xem [kiến trúc](architecture.md) và
[bố cục dự án](../reference/project-layout.md).

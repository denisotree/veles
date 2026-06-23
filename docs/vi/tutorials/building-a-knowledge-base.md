# Xây dựng một cơ sở tri thức

> 🌐 **Ngôn ngữ:** [English](../../en/tutorials/building-a-knowledge-base.md) · [简体中文](../../zh-CN/tutorials/building-a-knowledge-base.md) · [繁體中文](../../zh-TW/tutorials/building-a-knowledge-base.md) · [日本語](../../ja/tutorials/building-a-knowledge-base.md) · [한국어](../../ko/tutorials/building-a-knowledge-base.md) · [Español](../../es/tutorials/building-a-knowledge-base.md) · [Français](../../fr/tutorials/building-a-knowledge-base.md) · [Italiano](../../it/tutorials/building-a-knowledge-base.md) · [Português (BR)](../../pt-BR/tutorials/building-a-knowledge-base.md) · [Português (PT)](../../pt-PT/tutorials/building-a-knowledge-base.md) · [Русский](../../ru/tutorials/building-a-knowledge-base.md) · [العربية](../../ar/tutorials/building-a-knowledge-base.md) · [हिन्दी](../../hi/tutorials/building-a-knowledge-base.md) · [বাংলা](../../bn/tutorials/building-a-knowledge-base.md) · **Tiếng Việt**

Trong hướng dẫn này bạn sẽ biến một dự án Veles thành một cơ sở tri thức sống:
nạp một vài nguồn, để Veles viết các trang wiki, đặt câu hỏi, và củng cố những gì
bạn đã học. Đây là quy trình **LLM-Wiki** mặc định. Khoảng 15 phút.

Bạn nên hoàn thành [Bắt đầu](getting-started.md) trước.

## Ý tưởng

Một dự án Veles có hai vùng nội dung:

- `sources/` — tài liệu thô, bất biến mà bạn cung cấp (chỉ đọc đối với agent).
- `wiki/` — tri thức do chính agent tạo ra bằng LLM (vùng duy nhất nó ghi nội
  dung vào).

Bạn nạp các nguồn vào; Veles chưng cất chúng thành các trang wiki có liên kết; bạn
truy vấn wiki bằng ngôn ngữ tự nhiên. Xem [gói layout & LLM-Wiki](../explanation/layout-packs-and-llm-wiki.md)
để hiểu lý do.

## 1. Nạp một nguồn

`veles add` đọc một tệp hoặc URL và viết một trang wiki tóm tắt nó:

```bash
veles add https://en.wikipedia.org/wiki/Knowledge_management
veles add ./notes/meeting-2026-06-01.md
```

Mỗi `add` tạo ra một trang dưới `wiki/` và liên kết nó vào đồ thị wiki.

## 2. Quan sát wiki phát triển

Hãy xem những gì đã được viết:

```bash
ls wiki/concepts wiki/entities wiki/sources
```

Các trang tham chiếu chéo lẫn nhau. Danh mục `wiki/INDEX.md` theo nhu cầu giữ một
bản đồ mà agent tải khi cần (không phải một bản đổ ngữ cảnh khổng lồ).

## 3. Đặt câu hỏi

Bây giờ truy vấn cơ sở tri thức của bạn bằng ngôn ngữ tự nhiên:

```bash
veles run "Using the wiki, summarise the main approaches to knowledge management
and cite the pages you used."
```

Veles tìm kiếm trong wiki, đọc các trang liên quan, và trả lời — dựa trên những gì
bạn đã nạp chứ không chỉ dựa vào dữ liệu huấn luyện của nó.

Để trao đổi qua lại tương tác, hãy làm điều tương tự trong TUI (`veles tui`).

## 4. Củng cố các session

Khi bạn làm việc, các cuộc hội thoại tích lũy. Chạy curator để nén chúng thành các
trang wiki bền vững và trích xuất các bài học:

```bash
veles curate
```

Lệnh này ghi các trang `wiki/sessions/` và cập nhật các insight và quy tắc của dự
án. Veles cũng tự động làm điều này theo thời gian — xem
[bộ nhớ dự án & vòng lặp học hỏi](../explanation/project-memory-and-learning-loop.md).

## 5. Giữ wiki khỏe mạnh

Theo thời gian các trang trở nên lỗi thời hoặc mồ côi. Thao tác `lint` tìm ra
chúng:

```bash
veles run "lint"
```

(`ingest`, `query`, và `lint` là các skill đi kèm với layout LLM-Wiki; bạn gọi
chúng bằng `veles run "<operation>"` hoặc để agent tự gọi.)

## Những gì bạn đã xây dựng

Một cơ sở tri thức tự tổ chức: nguồn đi vào, các trang wiki có liên kết đi ra, có
thể truy vấn bằng ngôn ngữ tự nhiên, và ngày càng gọn gàng hơn khi Veles củng cố.
Từ đây:

- **[Quản lý skills, tools, và modules](../how-to/manage-skills-and-tools.md)** —
  dạy Veles các quy trình tái sử dụng.
- **[Chạy như một daemon](../how-to/run-as-daemon.md)** + **[kết nối Telegram](../how-to/connect-telegram.md)** —
  trò chuyện với cơ sở tri thức của bạn từ điện thoại.
- **[Nhiều dự án & subproject](../how-to/multi-project-and-subprojects.md)** —
  mở rộng ra nhiều cơ sở tri thức.

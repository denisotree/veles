# Bộ nhớ dự án & vòng lặp học

> 🌐 **Ngôn ngữ:** [English](../../en/explanation/project-memory-and-learning-loop.md) · [简体中文](../../zh-CN/explanation/project-memory-and-learning-loop.md) · [繁體中文](../../zh-TW/explanation/project-memory-and-learning-loop.md) · [日本語](../../ja/explanation/project-memory-and-learning-loop.md) · [한국어](../../ko/explanation/project-memory-and-learning-loop.md) · [Español](../../es/explanation/project-memory-and-learning-loop.md) · [Français](../../fr/explanation/project-memory-and-learning-loop.md) · [Italiano](../../it/explanation/project-memory-and-learning-loop.md) · [Português (BR)](../../pt-BR/explanation/project-memory-and-learning-loop.md) · [Português (PT)](../../pt-PT/explanation/project-memory-and-learning-loop.md) · [Русский](../../ru/explanation/project-memory-and-learning-loop.md) · [العربية](../../ar/explanation/project-memory-and-learning-loop.md) · [हिन्दी](../../hi/explanation/project-memory-and-learning-loop.md) · [বাংলা](../../bn/explanation/project-memory-and-learning-loop.md) · **Tiếng Việt**

Đặc tính định danh của Veles là nó **ghi nhớ** và **học** theo từng dự án. Trang này
giải thích bộ nhớ đó là gì và vòng lặp học giữ cho nó hữu ích ra sao.

## Bộ nhớ là một artefact có cấu trúc

Bộ nhớ dự án nằm trong `<project>/.veles/` — `memory.db` (SQLite, nguồn sự thật) cùng
một cây `.veles/memory/` đọc được bởi con người (các view insight đã render, bản tóm
tắt phiên, proposal, nhật ký vận hành hệ thống). Nó **tách biệt khỏi nội dung của
bạn** và hoạt động giống hệt nhau dưới mọi layout (wiki, notes, hay bare). Nó không
phải là một bãi đổ bản ghi chat — mà là một tập hợp các lớp có cấu trúc:

- **Nhật ký phiên (session log)** — mọi cuộc trò chuyện, mỗi lượt một hàng, được lập
  chỉ mục toàn văn.
- **Quy tắc (rules)** — các mệnh lệnh ngắn mà tác tử nên tuân theo (`format`, `do`,
  `don't`, `preference`), được chèn vào system prompt ổn định.
- **Insight** — các bài học được chắt lọc từ các phiên. Hàng SQL là chuẩn (recall,
  lão hóa, và dedup hoạt động trên nó); một view markdown được render ra
  `.veles/memory/insights/` cho con người và cho việc export.
- **Bản đồ cây dự án (project tree map)** — một bản đồ tệp được cache, gắn thẻ theo
  ngữ nghĩa để tác tử đọc 3–5 tệp liên quan, chứ không phải cả cây.
- **Registry kỹ năng & công cụ** — kèm telemetry (số lần dùng/thành công/lỗi) mà
  việc xếp hạng và dedup sử dụng.

Xem danh sách bảng trong [bố cục dự án](../reference/project-layout.md#project-memory-velesmemorydb).

## Recall: ngữ cảnh nhỏ, kéo vào theo nhu cầu

`AGENTS.md` được giữ nhỏ một cách có chủ đích. Khi bạn hỏi điều gì đó, Veles chỉ kéo
vào những gì liên quan: các lượt trao đổi quá khứ khớp (toàn văn + tái xếp hạng
vector tùy chọn), các quy tắc và insight áp dụng được, và các tệp được bản đồ cây dự
án chấm điểm cao nhất. Điều này giữ cho mỗi lời gọi model tập trung và rẻ thay vì đổ
hết mọi thứ vào.

## Vòng lặp học

Kinh nghiệm trở thành tri thức bền vững thông qua ba cơ chế:

### Insight — nắm bắt các bài học
Sau một lượt chạy, một bộ trích xuất tìm những điều đáng ghi nhớ: phản hồi rõ ràng
kiểu "nhớ X" / "đừng bao giờ Y", và các mẫu lỗi-công-cụ→khôi-phục (một thất bại được
tiếp nối bởi một bản sửa). Nó chắt lọc những điều này thành insight và quy tắc để
cùng một lỗi không lặp lại.

### Curator — củng cố các phiên
Curator chắt lọc các phiên cũ hơn thành bộ nhớ bền vững: luôn luôn là các insight và
quy tắc SQL; thêm vào đó là một trang `wiki/sessions/` khi layout của dự án bật
engine wiki. Nó chạy theo bộ đếm thời gian khi rảnh/sau-lượt, hoặc theo nhu cầu với
`veles curate`.

### Dreaming — bảo trì nền
`veles dream` (và daemon khi rảnh) trích xuất insight, khử trùng lặp các kỹ năng và
insight, đề xuất việc đề bạt (promotion), và (dưới một layout wiki) lint wiki — giữ
cho bộ nhớ luôn mới mà không chặn bạn lại. Thêm `--include-consolidation` để có một
lượt LLM sâu hơn.

## Nén ngữ cảnh

Các cuộc trò chuyện dài được giữ dưới giới hạn ngữ cảnh của model bằng một bộ nén
cửa-sổ-trượt: khi lịch sử trong bộ nhớ vượt một ngưỡng token, phần giữa được tóm tắt
(bởi một model rẻ được định tuyến) và thay bằng một con trỏ đến bản tóm tắt đã lưu
trong `.veles/memory/sessions/`. Lịch sử đầy đủ luôn còn lại trong `memory.db` — chỉ
cửa sổ trong bộ nhớ bị nén, nên nó không mất mát dữ liệu trên đĩa.

## Vì sao điều này quan trọng

Vì bộ nhớ có cấu trúc và vòng lặp chạy liên tục, một dự án Veles trở nên **hữu ích
hơn khi bạn dùng nó càng nhiều** — nó học các quy ước của bạn, tránh các lỗi lặp
lại, và đặt câu trả lời trên nền những gì nó đã thực sự thấy.

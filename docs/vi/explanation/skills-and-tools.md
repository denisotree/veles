# Kỹ năng & công cụ như năng lực tích lũy

> 🌐 **Ngôn ngữ:** [English](../../en/explanation/skills-and-tools.md) · [简体中文](../../zh-CN/explanation/skills-and-tools.md) · [繁體中文](../../zh-TW/explanation/skills-and-tools.md) · [日本語](../../ja/explanation/skills-and-tools.md) · [한국어](../../ko/explanation/skills-and-tools.md) · [Español](../../es/explanation/skills-and-tools.md) · [Français](../../fr/explanation/skills-and-tools.md) · [Italiano](../../it/explanation/skills-and-tools.md) · [Português (BR)](../../pt-BR/explanation/skills-and-tools.md) · [Português (PT)](../../pt-PT/explanation/skills-and-tools.md) · [Русский](../../ru/explanation/skills-and-tools.md) · [العربية](../../ar/explanation/skills-and-tools.md) · [हिन्दी](../../hi/explanation/skills-and-tools.md) · [বাংলা](../../bn/explanation/skills-and-tools.md) · **Tiếng Việt**

Veles khởi động với một tập hợp công cụ và kỹ năng tối thiểu rồi **mở rộng** dần
trong quá trình làm việc. Trang này giải thích sự khác biệt giữa hai khái niệm đó
và cách chúng tích lũy. Để biết các lệnh, xem [quản lý kỹ năng & công cụ](../how-to/manage-skills-and-tools.md).

## Công cụ và kỹ năng

- **Công cụ** (tool) là một hành động có thể thực thi đơn lẻ — đọc một tệp, chạy
  một lệnh shell, lấy nội dung từ URL, tìm kiếm trên web, viết một trang wiki. Công
  cụ là thứ mà model gọi.
- **Kỹ năng** (skill) là một *quy trình* được hình thức hóa — một tệp `SKILL.md` với
  phần thân là prompt cùng một danh sách công cụ được phép, chạy như một sub-agent
  tập trung. Kỹ năng kết hợp các công cụ thành một quy trình lặp lại được (ví dụ
  `ingest`/`query`/`lint` của LLM-Wiki).

## Khởi động tối thiểu, mở rộng theo nhu cầu

Veles khởi động với vừa đủ để hữu ích, cộng thêm một nơi đã biết để lấy thêm. Việc
cài đặt phần bổ sung (một kỹ năng, một công cụ, một module) mặc định sẽ hỏi phê
duyệt; bạn có thể cấp quyền tự chủ thường trực. Cách này giữ cho một dự án mới gọn
nhẹ trong khi vẫn cho phép năng lực phát triển ở nơi cần đến.

## Năng lực tích lũy như thế nào

1. **Veles tự viết công cụ của mình.** Khi nhận thấy một tác vụ lặp đi lặp lại, nó
   có thể tự soạn một công cụ Python sạch, có kiểu (typed), tái sử dụng được vào
   `<project>/.veles/tools/` (kèm một lượt review mã bởi advisor). Công cụ đó gia
   nhập registry cùng với telemetry.
2. **Quy trình lặp lại trở thành kỹ năng.** Một bộ phát hiện mẫu (pattern detector)
   nhận ra các chuỗi công cụ lặp lại và đề xuất hình thức hóa chúng thành một kỹ
   năng; kỹ năng có thể dùng `extends:` một kỹ năng khác để kế thừa phần thân và
   công cụ của nó.
3. **Telemetry điều khiển việc xếp hạng.** Mỗi công cụ/kỹ năng mang theo số liệu về
   số lần dùng/thành công/lỗi. Những số liệu này nuôi việc khử trùng lặp
   (`veles skill dedup`) và các đề xuất thăng cấp.

## Hai phạm vi, kèm cơ chế thăng cấp

Cả công cụ lẫn kỹ năng đều tồn tại ở hai cấp:

- **Cục bộ theo dự án** (`<project>/.veles/`) — chỉ nhìn thấy ở đây.
- **Toàn cục theo người dùng** (`~/.veles/`) — khả dụng trên mọi dự án.

Một năng lực đã chứng tỏ giá trị trong một dự án có thể được **thăng cấp** lên phạm
vi người dùng để mọi dự án cùng hưởng lợi (`veles skill promote`,
`veles tool promote`), hoặc **hạ cấp** trở lại. Đây là cách Veles mang các quy
trình khó khăn lắm mới có được giữa các dự án.

## Vì sao dùng registry, không chỉ là tệp

Lưu kỹ năng/công cụ dưới dạng tệp thuần giúp chúng dễ xem xét và chỉnh sửa; lưu
*telemetry* của chúng trong `memory.db` cho phép Veles suy luận về việc cái nào
thực sự hoạt động hiệu quả. Chính sự kết hợp này biến "một thư mục chứa script"
thành năng lực tích lũy, tự curate.

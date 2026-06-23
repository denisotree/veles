# Các chế độ chạy

> 🌐 **Ngôn ngữ:** [English](../../en/explanation/modes.md) · [简体中文](../../zh-CN/explanation/modes.md) · [繁體中文](../../zh-TW/explanation/modes.md) · [日本語](../../ja/explanation/modes.md) · [한국어](../../ko/explanation/modes.md) · [Español](../../es/explanation/modes.md) · [Français](../../fr/explanation/modes.md) · [Italiano](../../it/explanation/modes.md) · [Português (BR)](../../pt-BR/explanation/modes.md) · [Português (PT)](../../pt-PT/explanation/modes.md) · [Русский](../../ru/explanation/modes.md) · [العربية](../../ar/explanation/modes.md) · [हिन्दी](../../hi/explanation/modes.md) · [বাংলা](../../bn/explanation/modes.md) · **Tiếng Việt**

Trong TUI, mỗi prompt được xử lý bởi một **chế độ chạy (run mode)** — một chiến lược
quyết định lượt tương tác được trao bao nhiêu quyền tự chủ và những công cụ nào.
Chuyển vòng giữa các chế độ bằng `Shift+Tab`; thứ tự là `auto → planning → writing → goal`.

## Bốn chế độ

### `writing` — trò chuyện trực tiếp
Chế độ thẳng thắn: prompt của bạn được gửi đến tác tử với toàn bộ bộ công cụ sẵn
sàng, và nó phản hồi. Dùng nó cho công việc thông thường khi bạn muốn tác tử hành động.

### `planning` — nghiên cứu chỉ-đọc + một kế hoạch
Các thao tác thay đổi bị chặn (không `write_file`, không `run_shell`). Tác tử dùng
các công cụ đọc/tìm kiếm để thu thập ngữ cảnh, rồi tạo ra một artefact kế hoạch có
cấu trúc. Dùng nó để suy nghĩ trước khi động vào bất cứ thứ gì — hoặc truyền `--plan`
cho `veles run` để có hiệu ứng tương tự trên CLI.

### `auto` — định tuyến thông minh (mặc định)
Một bước phân loại nhanh quyết định xem prompt của bạn là một yêu cầu trực tiếp hay
cần lập kế hoạch, rồi điều phối tương ứng đến `writing` hoặc `planning`. Đây là lựa
chọn dự phòng thông minh nhất khi bạn chưa bày tỏ ý định, đó là lý do nó là điểm
dừng đầu tiên mặc định trong vòng chuyển.

### `goal` — mục tiêu dài hạn
Điều khiển một máy trạng thái hữu hạn cho một mục tiêu nhiều bước: nó phỏng vấn bạn
để làm rõ, xác nhận một kế hoạch, thực thi các bước (kèm các bước kiểm tra của
advisor), và xác minh điều-kiện-hoàn-thành — tất cả dưới các ngân sách (budget) rõ
ràng. Tương đương trên CLI là họ lệnh
[`veles goal`](../how-to/long-running-tasks.md#goals--objectives-with-budgets-and-checkpoints).

## Vì sao các chế độ tồn tại

Các yêu cầu khác nhau cần lượng thận trọng khác nhau. Một câu hỏi nhanh không nên
đòi hỏi nghi thức rườm rà; một thay đổi rủi ro sẽ được lợi nếu có một lượt lập kế
hoạch chỉ-đọc trước; một mục tiêu lớn cần ngân sách và các điểm kiểm soát
(checkpoint). Các chế độ làm cho lựa chọn đó trở nên rõ ràng và có thể chuyển đổi
theo từng lượt, thay vì nung cứng một hành vi duy nhất cho cả phiên.

Khi bạn chuyển chế độ giữa chừng, tác tử được thông báo về các quy tắc mới nên hành
vi của nó thay đổi ngay lập tức.

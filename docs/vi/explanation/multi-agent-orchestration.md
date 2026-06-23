# Điều phối đa tác tử

> 🌐 **Ngôn ngữ:** [English](../../en/explanation/multi-agent-orchestration.md) · [简体中文](../../zh-CN/explanation/multi-agent-orchestration.md) · [繁體中文](../../zh-TW/explanation/multi-agent-orchestration.md) · [日本語](../../ja/explanation/multi-agent-orchestration.md) · [한국어](../../ko/explanation/multi-agent-orchestration.md) · [Español](../../es/explanation/multi-agent-orchestration.md) · [Français](../../fr/explanation/multi-agent-orchestration.md) · [Italiano](../../it/explanation/multi-agent-orchestration.md) · [Português (BR)](../../pt-BR/explanation/multi-agent-orchestration.md) · [Português (PT)](../../pt-PT/explanation/multi-agent-orchestration.md) · [Русский](../../ru/explanation/multi-agent-orchestration.md) · [العربية](../../ar/explanation/multi-agent-orchestration.md) · [हिन्दी](../../hi/explanation/multi-agent-orchestration.md) · [বাংলা](../../bn/explanation/multi-agent-orchestration.md) · **Tiếng Việt**

Với công việc phức tạp, Veles có thể chia một tác vụ ra giữa một **manager** và các
tác tử con **worker** chuyên biệt thay vì làm tất cả trong một ngữ cảnh duy nhất.
Trang này giải thích mô hình đó; để bật nó, xem
[chế độ manager](../how-to/long-running-tasks.md#manager-mode--decompose-any-prompt).

## Hình dạng

```
            manager  (decomposes the task, never writes the final answer)
           /    |    \
    explorer  writer  advisor   (specialised workers, run in parallel)
```

- **Manager** lập kế hoạch phân rã và điều phối — nhưng **không** tự viết sản phẩm
  cuối cùng.
- **Các worker** có system prompt riêng theo vai trò: `explorer` thu thập, `writer`
  tạo ra câu trả lời, `advisor` rà soát. Tập hợp này có thể mở rộng.
- Cuối cùng, manager ghi một báo cáo ngắn vào bộ nhớ.

## Không có trò "tam sao thất bản"

Một quy tắc then chốt: các artefact trung gian đến tay người tổng hợp **nguyên văn**,
chứ không phải qua lời diễn giải của manager. Phát hiện của explorer được trao trực
tiếp cho writer, nhờ vậy chi tiết không bị mất qua một chuỗi tóm tắt. Đây chính là
điều khiến việc phân rã làm tăng chất lượng thay vì làm loãng nó.

## Vì sao "manager không bao giờ viết"

Nếu người điều phối cũng viết câu trả lời, nó sẽ bị cám dỗ đi tắt qua các worker và
mất đi lợi ích của sự chuyên biệt hóa. Giữ phần tổng hợp ở một `writer` chuyên trách
(được cấp đầu vào nguyên văn) sẽ áp đặt sự phân công lao động. Veles biến điều này
thành một đảm bảo tại thời điểm chạy (runtime guarantee).

## Khi nào nó hữu ích — và khi nào không

Việc phân rã đem lại lợi ích cho các tác vụ rộng hoặc nhiều mặt (audit codebase này,
nghiên cứu câu hỏi này từ nhiều góc độ). Với một yêu cầu nhanh, đơn-ngữ-cảnh, nó chỉ
thêm chi phí — đó là lý do chế độ manager là **tùy chọn bật rõ ràng (explicit
opt-in)**, mặc định tắt (`veles run --manager` hoặc `VELES_MANAGER_MODE=1`).

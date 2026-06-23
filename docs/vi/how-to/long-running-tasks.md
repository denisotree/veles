# Cách chạy các tác vụ dài hạn: goals, jobs, dreaming, research

> 🌐 **Ngôn ngữ:** [English](../../en/how-to/long-running-tasks.md) · [Русский](../../ru/how-to/long-running-tasks.md) · **Tiếng Việt**

Vượt ra ngoài các prompt đơn lẻ, Veles có thể theo đuổi các **mục tiêu (goals)** nhiều bước với ngân sách, chạy
các **tác vụ theo lịch (jobs)**, **mơ (dream)** để củng cố bộ nhớ, **nghiên cứu (research)** web song song,
và phân rã công việc giữa một **quản lý (manager)** cùng các sub-agent.

## Goals — mục tiêu kèm ngân sách và điểm kiểm tra

Một goal là một mục tiêu dài hạn với các giới hạn rõ ràng và nhật ký tiến độ:

```bash
veles goal start "Draft a competitor analysis report" \
  --done-when "report.md exists and cites >=3 sources" \
  --max-steps 30 --max-cost-usd 5 --max-wall-time-s 3600

veles goal list
veles goal show <id>
veles goal checkpoint <id> "Outlined sections; cited 2 sources" --cost-usd 0.40
veles goal pause <id> ; veles goal resume <id>
veles goal done <id> --evidence report.md
veles goal cancel <id> --reason "scope changed"
```

Trong TUI, chế độ chạy **goal** (chuyển đổi bằng `Shift+Tab`) điều khiển cùng một FSM
theo cách tương tác: nó phỏng vấn bạn, xác nhận một kế hoạch, thực thi và kiểm tra.

## Jobs — các lần chạy agent theo lịch

Lên lịch để một prompt chạy theo biểu thức cron, theo khoảng thời gian, hoặc một lần vào một thời điểm:

```bash
veles job add --name daily-digest \
  --schedule "0 9 * * *" \
  --prompt "Summarise yesterday's sessions into wiki/digests/"

veles job list
veles job history <id>
veles job trigger <id>          # run on the next tick
veles job pause <id> ; veles job resume <id>
veles job remove <id>
```

`--schedule` chấp nhận một biểu thức cron, `<N><s|m|h|d>` (ví dụ `30m`), hoặc một dấu thời gian
ISO. Các job chạy khi daemon đang hoạt động, hoặc bạn có thể chạy tất cả chúng một lần một cách đồng bộ:

```bash
veles job tick                  # run due jobs now, no daemon needed
```

Gửi đầu ra của một job tới một kênh bằng `--deliver-to telegram:<chat_id>`.

## Dreaming — củng cố bộ nhớ ở chế độ nền

`dream` trích xuất các insight, khử trùng lặp skill, đề xuất các thăng cấp (promotion), và lint
wiki — giữ cho bộ nhớ luôn mới mà bạn không phải chờ đợi:

```bash
veles dream
veles dream --include-consolidation     # also run the (paid) LLM consolidation
veles dream --dry-run                    # show what it would do
```

Một daemon đang chạy sẽ tự động dream khi rảnh rỗi.

## Research — điều tra web song song

```bash
veles research "What are the leading approaches to retrieval-augmented generation?" \
  --max-subquestions 4
```

Veles phân rã câu hỏi, khám phá các khía cạnh song song, và tổng hợp một
báo cáo có trích dẫn nguồn.

## Manager mode — phân rã bất kỳ prompt nào

Bật tính năng phân rã đa agent cho một lần chạy duy nhất (một manager sinh ra các sub-agent explorer /
writer / advisor và không bao giờ tự viết câu trả lời cuối cùng):

```bash
veles run --manager "Audit this codebase for security issues and write a report"
# or globally: export VELES_MANAGER_MODE=1   (=0 to force off)
```

Xem [điều phối đa agent](../explanation/multi-agent-orchestration.md).

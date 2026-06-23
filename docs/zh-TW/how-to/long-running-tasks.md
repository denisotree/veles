# 如何執行長時間運行的任務：goals、jobs、dreaming、research

> 🌐 **語言：** **English** · [Русский](../../ru/how-to/long-running-tasks.md)

除了單次 prompt 之外，Veles 還能追求帶有預算的多步驟 **goals**、執行
**排程 jobs**、透過 **dream** 來整併記憶、平行地在網路上做 **research**，並把工作
拆解到一個 **manager** 與多個 sub-agents 之間。

## Goals — 帶有預算與檢查點的目標

goal 是一個長程目標，帶有明確的限制與進度日誌：

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

在 TUI 中，**goal** 執行模式（用 `Shift+Tab` 循環切換）會以互動方式驅動同一個 FSM：
它會訪問你、確認計畫、執行並檢查。

## Jobs — 排程的 agent 執行

把一個 prompt 排程成依 cron 表達式、間隔時間或在某個時間點執行一次：

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

`--schedule` 接受 cron 表達式、`<N><s|m|h|d>`（例如 `30m`），或一個 ISO
時間戳記。Jobs 會在 daemon 運行時執行，或者你也可以同步地把它們全部執行一次：

```bash
veles job tick                  # run due jobs now, no daemon needed
```

用 `--deliver-to telegram:<chat_id>` 把 job 的輸出投遞到某個 channel。

## Dreaming — 背景記憶整併

`dream` 會擷取 insights、去除重複的 skills、建議 promotions，並對 wiki 做 lint —
讓記憶保持新鮮，而你不必等待：

```bash
veles dream
veles dream --include-consolidation     # also run the (paid) LLM consolidation
veles dream --dry-run                    # show what it would do
```

運行中的 daemon 會在閒置時自動 dream。

## Research — 平行的網路調查

```bash
veles research "What are the leading approaches to retrieval-augmented generation?" \
  --max-subquestions 4
```

Veles 會拆解問題，平行地從各個角度探索，並綜合出一份帶引用的報告。

## Manager 模式 — 拆解任何 prompt

為單次執行開啟多 agent 拆解（一個 manager 會衍生 explorer / writer / advisor
sub-agents，而自己絕不撰寫最終答案）：

```bash
veles run --manager "Audit this codebase for security issues and write a report"
# or globally: export VELES_MANAGER_MODE=1   (=0 to force off)
```

請參閱 [multi-agent orchestration](../explanation/multi-agent-orchestration.md)。

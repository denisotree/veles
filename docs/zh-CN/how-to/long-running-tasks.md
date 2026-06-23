# 如何运行长时间任务：目标、作业、做梦、研究

> 🌐 **语言：** [English](../../en/how-to/long-running-tasks.md) · **简体中文** · [繁體中文](../../zh-TW/how-to/long-running-tasks.md) · [日本語](../../ja/how-to/long-running-tasks.md) · [한국어](../../ko/how-to/long-running-tasks.md) · [Español](../../es/how-to/long-running-tasks.md) · [Français](../../fr/how-to/long-running-tasks.md) · [Italiano](../../it/how-to/long-running-tasks.md) · [Português (BR)](../../pt-BR/how-to/long-running-tasks.md) · [Português (PT)](../../pt-PT/how-to/long-running-tasks.md) · [Русский](../../ru/how-to/long-running-tasks.md) · [العربية](../../ar/how-to/long-running-tasks.md) · [हिन्दी](../../hi/how-to/long-running-tasks.md) · [বাংলা](../../bn/how-to/long-running-tasks.md) · [Tiếng Việt](../../vi/how-to/long-running-tasks.md)

除了单条提示之外，Veles 还能带着预算去推进多步骤的**目标（goals）**、运行**定时作业（scheduled jobs）**、通过**做梦（dream）**来整合内存、并行地在网络上做**研究（research）**，并把工作拆解到一个**管理者（manager）**和子智能体之间。

## 目标（Goals）——带预算和检查点的目的

目标是一个带有明确限制和进度日志的长周期目的：

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

在 TUI 中，**goal** 运行模式（用 `Shift+Tab` 循环切换）以交互方式驱动同一个状态机：它会向你提问、确认计划、执行并检查。

## 作业（Jobs）——定时的智能体运行

按 cron 表达式、按时间间隔，或在某个时刻执行一次，来调度一条提示运行：

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

`--schedule` 接受 cron 表达式、`<N><s|m|h|d>`（例如 `30m`），或一个 ISO 时间戳。作业会在守护进程运行时执行，或者你可以同步地把它们全部运行一次：

```bash
veles job tick                  # run due jobs now, no daemon needed
```

用 `--deliver-to telegram:<chat_id>` 把作业输出投递到某个频道。

## 做梦（Dreaming）——后台内存整合

`dream` 会提取洞见、对技能去重、给出晋升建议，并对 wiki 做 lint——在你无需等待的情况下保持内存新鲜：

```bash
veles dream
veles dream --include-consolidation     # also run the (paid) LLM consolidation
veles dream --dry-run                    # show what it would do
```

正在运行的守护进程会在空闲时自动做梦。

## 研究（Research）——并行的网络调查

```bash
veles research "What are the leading approaches to retrieval-augmented generation?" \
  --max-subquestions 4
```

Veles 会拆解问题，并行地从多个角度探索，并综合出一份带引用的报告。

## 管理者模式（Manager mode）——拆解任意提示

为单次运行开启多智能体拆解（一个管理者会派生 explorer / writer / advisor 子智能体，且管理者本身绝不撰写最终答案）：

```bash
veles run --manager "Audit this codebase for security issues and write a report"
# or globally: export VELES_MANAGER_MODE=1   (=0 to force off)
```

参见[多智能体编排](../explanation/multi-agent-orchestration.md)。

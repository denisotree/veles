# लंबे चलने वाले tasks कैसे चलाएँ: goals, jobs, dreaming, research

> 🌐 **भाषाएँ:** [English](../../en/how-to/long-running-tasks.md) · [简体中文](../../zh-CN/how-to/long-running-tasks.md) · [繁體中文](../../zh-TW/how-to/long-running-tasks.md) · [日本語](../../ja/how-to/long-running-tasks.md) · [한국어](../../ko/how-to/long-running-tasks.md) · [Español](../../es/how-to/long-running-tasks.md) · [Français](../../fr/how-to/long-running-tasks.md) · [Italiano](../../it/how-to/long-running-tasks.md) · [Português (BR)](../../pt-BR/how-to/long-running-tasks.md) · [Português (PT)](../../pt-PT/how-to/long-running-tasks.md) · [Русский](../../ru/how-to/long-running-tasks.md) · [العربية](../../ar/how-to/long-running-tasks.md) · **हिन्दी** · [বাংলা](../../bn/how-to/long-running-tasks.md) · [Tiếng Việt](../../vi/how-to/long-running-tasks.md)

single prompts से आगे, Veles budgets के साथ multi-step **goals** का पीछा कर सकता है,
**scheduled jobs** चला सकता है, memory consolidate करने के लिए **dream** कर सकता है, web को समानांतर रूप से
**research** कर सकता है, और काम को एक **manager** और sub-agents में विभाजित कर सकता है।

## Goals — budgets और checkpoints वाले उद्देश्य

एक goal स्पष्ट सीमाओं और progress log वाला एक long-horizon उद्देश्य है:

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

TUI में, **goal** run mode (`Shift+Tab` से cycle करें) उसी FSM को
interactively चलाता है: यह आपका interview लेता है, एक plan confirm करता है, execute करता है, और जाँच करता है।

## Jobs — scheduled agent runs

किसी prompt को cron expression, interval, या किसी निश्चित समय पर एक बार चलाने के लिए schedule करें:

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

`--schedule` एक cron expression, `<N><s|m|h|d>` (जैसे `30m`), या एक ISO
timestamp स्वीकार करता है। Jobs तब चलते हैं जब daemon चालू हो, या उन सबको एक बार synchronously चलाएँ:

```bash
veles job tick                  # run due jobs now, no daemon needed
```

किसी job के output को `--deliver-to telegram:<chat_id>` के साथ किसी channel तक पहुँचाएँ।

## Dreaming — background memory consolidation

`dream` insights extract करता है, skills को deduplicate करता है, promotions सुझाता है, और wiki को
lint करता है — आपको इंतज़ार कराए बिना memory को ताज़ा रखता है:

```bash
veles dream
veles dream --include-consolidation     # also run the (paid) LLM consolidation
veles dream --dry-run                    # show what it would do
```

एक चालू daemon idle होने पर अपने आप dream करता है।

## Research — समानांतर web investigation

```bash
veles research "What are the leading approaches to retrieval-augmented generation?" \
  --max-subquestions 4
```

Veles प्रश्न को विभाजित करता है, समानांतर रूप से अलग-अलग पहलुओं का अन्वेषण करता है, और एक
cited report संश्लेषित करता है।

## Manager mode — किसी भी prompt को विभाजित करें

एक single run के लिए multi-agent decomposition चालू करें (एक manager explorer /
writer / advisor sub-agents spawn करता है और final answer खुद कभी नहीं लिखता):

```bash
veles run --manager "Audit this codebase for security issues and write a report"
# or globally: export VELES_MANAGER_MODE=1   (=0 to force off)
```

देखें [multi-agent orchestration](../explanation/multi-agent-orchestration.md)।

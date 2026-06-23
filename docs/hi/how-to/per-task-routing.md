# tasks को विभिन्न models पर route कैसे करें

> 🌐 **भाषाएँ:** [English](../../en/how-to/per-task-routing.md) · [简体中文](../../zh-CN/how-to/per-task-routing.md) · [繁體中文](../../zh-TW/how-to/per-task-routing.md) · [日本語](../../ja/how-to/per-task-routing.md) · [한국어](../../ko/how-to/per-task-routing.md) · [Español](../../es/how-to/per-task-routing.md) · [Français](../../fr/how-to/per-task-routing.md) · [Italiano](../../it/how-to/per-task-routing.md) · [Português (BR)](../../pt-BR/how-to/per-task-routing.md) · [Português (PT)](../../pt-PT/how-to/per-task-routing.md) · [Русский](../../ru/how-to/per-task-routing.md) · [العربية](../../ar/how-to/per-task-routing.md) · **हिन्दी** · [বাংলা](../../bn/how-to/per-task-routing.md) · [Tiếng Việt](../../vi/how-to/per-task-routing.md)

Veles किसी एक model से बँधा नहीं है। प्रत्येक internal **task** एक अलग `provider:model`
का उपयोग कर सकता है — context compression के लिए एक सस्ता model, main agent के लिए एक
मज़बूत model, images के लिए एक vision model। यह *ensemble routing* system है।

## Task types

| Task | किसके लिए |
|---|---|
| `default` | main agent loop |
| `curator` | Session → wiki consolidation |
| `compressor` | Sliding-window context compression |
| `insights` | run के बाद insight extraction |
| `skills` | Skill execution |
| `advisor` | `advisor_review` self-check |
| `vision` | `image_describe` (जब एक vision adapter wire किया गया हो) |
| `embedding` | `veles skill dedup` similarity |

## वर्तमान routing देखें

```bash
veles route show
```

यह प्रत्येक task के लिए resolved `provider:model` और एक `source` label प्रिंट करता है
जो बताता है कि किस layer ने इसे तय किया।

## एक task को एक model पर pin करें

```bash
veles route set compressor openrouter:anthropic/claude-haiku-4.5
veles route set advisor    openrouter:anthropic/claude-opus-4.8
veles route set vision     openai:gpt-4o
```

ये `<project>/.veles/config.toml` में `[routing.tasks]` लिखते हैं:

```toml
[routing.tasks]
compressor = "openrouter:anthropic/claude-haiku-4.5"
advisor    = "openrouter:anthropic/claude-opus-4.8"
vision     = "openai:gpt-4o"
```

## Reset

```bash
veles route reset compressor   # one task back to default
veles route reset              # all tasks back to default
```

## AGENTS.md में natural-language hints

आप routing को `AGENTS.md` में गद्य में व्यक्त कर सकते हैं (जैसे "use a cheap model for
compression")। Veles इन्हें एक auto-generated `routing.nl.toml` में parse करता है:

```bash
veles route refresh            # re-parse AGENTS.md hints
veles route refresh --force    # even if AGENTS.md hasn't changed
```

explicit `[routing.tasks]` entries हमेशा NL hints पर जीतती हैं।

## Resolution क्रम

प्रत्येक task के लिए, पहली layer जो एक spec देती है वह जीतती है:

1. project `[routing.tasks][task]`
2. project `[routing.tasks].default`
3. project NL hint (`routing.nl.toml`)
4. project `[provider]` base
5. user `[routing.tasks][task]` / `.default`
6. user `[user] default_provider` + `default_model`

यदि इनमें से कोई भी resolve नहीं होता, तो कोई **hardcoded fallback नहीं है** — task
unset छोड़ दिया जाता है और उसका caller degrade हो जाता है (feature छोड़ देता है) या साफ
तौर पर error देता है, बजाय चुपचाप किसी cloud model तक पहुँचने के।

(`embedding` catch-alls को छोड़ देता है — एक chat model embedding model नहीं है — इसलिए
केवल एक explicit `[routing.tasks].embedding` ही इसका उत्तर देता है।)

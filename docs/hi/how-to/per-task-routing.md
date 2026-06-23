# विभिन्न मॉडल्स पर टास्क रूट कैसे करें

> 🌐 **भाषाएँ:** **English** · [Русский](../../ru/how-to/per-task-routing.md)

Veles किसी एक मॉडल से बँधा नहीं है। प्रत्येक आंतरिक **task** एक अलग
`provider:model` इस्तेमाल कर सकता है — context compression के लिए एक सस्ता मॉडल,
मुख्य agent के लिए एक मज़बूत मॉडल, images के लिए एक vision मॉडल। यही है
*ensemble routing* सिस्टम।

## Task types

| Task | किसके लिए |
|---|---|
| `default` | मुख्य agent loop |
| `curator` | Session → wiki consolidation |
| `compressor` | Sliding-window context compression |
| `insights` | रन के बाद insight extraction |
| `skills` | Skill execution |
| `advisor` | `advisor_review` self-check |
| `vision` | `image_describe` (जब vision adapter जुड़ा हो) |
| `embedding` | `veles skill dedup` similarity |

## मौजूदा routing देखें

```bash
veles route show
```

यह हर task के लिए resolved `provider:model` और एक `source` label प्रिंट करता है,
जो बताता है कि किस layer ने उसे तय किया।

## किसी task को किसी मॉडल पर पिन करें

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
veles route reset compressor   # एक task को वापस default पर
veles route reset              # सभी tasks वापस default पर
```

## AGENTS.md में natural-language hints

आप `AGENTS.md` में routing को सादे शब्दों में व्यक्त कर सकते हैं (जैसे "compression
के लिए सस्ता मॉडल इस्तेमाल करो")। Veles इन्हें पार्स करके एक auto-generated
`routing.nl.toml` बनाता है:

```bash
veles route refresh            # AGENTS.md hints दोबारा पार्स करें
veles route refresh --force    # भले ही AGENTS.md बदला न हो
```

स्पष्ट `[routing.tasks]` entries हमेशा NL hints पर भारी पड़ती हैं।

## Resolution order

प्रत्येक task के लिए, पहली layer जो कोई spec देती है वही जीतती है:

1. project `[routing.tasks][task]`
2. project `[routing.tasks].default`
3. project NL hint (`routing.nl.toml`)
4. project `[provider]` base
5. user `[routing.tasks][task]` / `.default`
6. user `[user] default_provider` + `default_model`
7. उस task के लिए built-in default

(`embedding` catch-alls को skip करता है — एक chat मॉडल कोई embedding मॉडल नहीं है।)

# Architecture overview

> 🌐 **भाषाएँ:** **English** · [Русский](../../ru/explanation/architecture.md)

यह पेज समझाता है कि Veles *क्या है* और इसके हिस्से आपस में कैसे जुड़ते हैं, ताकि
बाक़ी दस्तावेज़ समझ में आएँ। प्रामाणिक प्रोडक्ट विज़न के लिए repo root में
`VISION.md` देखें।

## डिज़ाइन का इरादा

Veles जानबूझकर **minimalist और साफ़-सुथरे रूप से decomposed** है —
single-responsibility मॉड्यूल, कोई god-file नहीं। यह **local-first** है: आप इसे
अपनी मशीन पर एक डायरेक्टरी के विरुद्ध चलाते हैं, और यह अपनी संरचित memory वहीं
रखता है।

## पाँच स्तंभ (core)

core में सब कुछ इन पाँच कामों में से किसी एक की सेवा करता है:

1. **Project memory** — एक संरचित artefact (आपके कंटेंट से अलग) जो सेशन लॉग,
   सीखे गए rules/insights, एक प्रोजेक्ट फ़ाइल मैप, और telemetry के साथ
   skill/tool रजिस्ट्रियाँ रखता है। देखें [project memory & the learning loop](project-memory-and-learning-loop.md)।
2. **The learning loop** — curator, insight extractor, और dreaming जो memory को
   ताज़ा रखते हैं और अनुभव को पुन: उपयोग योग्य rules में बदलते हैं।
3. **Multi-agent orchestration** — एक manager जो किसी कार्य को विघटित करता है और
   विशेषज्ञ workers spawn करता है। देखें [multi-agent orchestration](multi-agent-orchestration.md)।
4. **A provider protocol** — कई LLM बैकएंड्स (cloud, local, CLI delegation) पर एक
   ही इंटरफ़ेस। देखें [providers](../reference/providers.md)।
5. **Minimal tools & skills** — एक छोटा bootstrap सेट जो तब **जमा होता** है जब
   Veles अपने खुद के tools लिखता है और दोहराई जाने वाली प्रक्रियाओं को skills में
   औपचारिक बनाता है। देखें [skills & tools](skills-and-tools.md)।

## बाक़ी सब कुछ एक वैकल्पिक मॉड्यूल है

Gateways/channels, daemon, scheduler, TUI, vision/STT — ये सब **pluggable** हैं
और तभी लोड होते हैं जब उपयोग किए जाएँ। Veles न्यूनतम के साथ बूट होता है और माँग पर
विस्तृत होता है, इसलिए एक साधारण `veles run` साधारण ही रहता है।

## एक turn कैसे प्रवाहित होता है

```
your prompt
   │
   ▼
context: AGENTS.md (small) + on-demand recall from project memory
   │
   ▼
agent loop  ──►  provider (routed per task)  ──►  tool calls
   │                                               │
   │            (trust ladder gates sensitive tools)
   ▼
response  ──►  saved to memory  ──►  learning triggers (insights, curator)
```

context फ़ाइल (`AGENTS.md`) को जानबूझकर छोटा रखा जाता है; सहायक ज्ञान (wiki पेज,
प्रोजेक्ट फ़ाइल मैप, प्रासंगिक पिछले turns) पहले से डंप करने के बजाय **माँग पर**
खींचा जाता है।

## state कहाँ रहता है

- `<project>/.veles/` — इस प्रोजेक्ट की memory, config, local skills/tools।
- `~/.veles/` — user-global config, cross-project skills/tools, caches, trust।
- `<project>/AGENTS.md`, `wiki/`, `sources/` — आपका कंटेंट (LLM-Wiki layout)।

देखें [project layout](../reference/project-layout.md)।

## एक ही loop में multi-project

एक ही agent loop कई प्रोजेक्ट्स की सेवा करता है। प्रत्येक प्रोजेक्ट को अपनी खुद
की डायरेक्टरी मिलती है जिसमें उसका अपना context और memory होता है; `AGENTS.md` को
`CLAUDE.md`/`GEMINI.md` से symlink किया जाता है ताकि वहाँ लॉन्च किया गया कोई
बाहरी CLI वही context देखे। देखें
[multiple projects](../how-to/multi-project-and-subprojects.md)।

## surfaces

- **CLI** (`veles run`, `veles add`, …) — one-shot और scripted उपयोग।
- **TUI** (`veles tui`) — [run modes](modes.md) के साथ इंटरैक्टिव REPL।
- **Daemon + channels** — headless API, Telegram, scheduled jobs।

तीनों एक ही core agent loop को चलाते हैं।

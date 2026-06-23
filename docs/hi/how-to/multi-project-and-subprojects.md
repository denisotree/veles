# कई projects और subprojects के साथ कैसे काम करें

> 🌐 **भाषाएँ:** [English](../../en/how-to/multi-project-and-subprojects.md) · [简体中文](../../zh-CN/how-to/multi-project-and-subprojects.md) · [繁體中文](../../zh-TW/how-to/multi-project-and-subprojects.md) · [日本語](../../ja/how-to/multi-project-and-subprojects.md) · [한국어](../../ko/how-to/multi-project-and-subprojects.md) · [Español](../../es/how-to/multi-project-and-subprojects.md) · [Français](../../fr/how-to/multi-project-and-subprojects.md) · [Italiano](../../it/how-to/multi-project-and-subprojects.md) · [Português (BR)](../../pt-BR/how-to/multi-project-and-subprojects.md) · [Português (PT)](../../pt-PT/how-to/multi-project-and-subprojects.md) · [Русский](../../ru/how-to/multi-project-and-subprojects.md) · [العربية](../../ar/how-to/multi-project-and-subprojects.md) · **हिन्दी** · [বাংলা](../../bn/how-to/multi-project-and-subprojects.md) · [Tiếng Việt](../../vi/how-to/multi-project-and-subprojects.md)

Veles एक ही agent loop में कई projects चलाता है। हर project की अपनी memory,
skills, और tools होती हैं। **Subprojects** किसी parent के अंतर्गत nested projects हैं — किसी बड़े
monorepo या knowledge base को scoped memories में विभाजित करने के लिए उपयोगी।

## Projects

Veles active project को आपके cwd से ऊपर की ओर किसी `.veles/`
directory तक चलकर खोजता है (`git` की तरह)। registry manage करें:

```bash
veles project list                  # registered projects, most-recent first
veles project add /path/to/project  # register an existing project
veles project add /path --slug web  # with a custom slug
veles project remove <slug>         # unregister (files untouched)
```

`switch` एक path print करता है, ताकि आप किसी project में `cd` कर सकें:

```bash
cd "$(veles project switch web)"
```

बिना `cd` किए कहीं और मौजूद किसी project के विरुद्ध एक command चलाएँ:

```bash
veles run --project-root /path/to/project "..."
```

## Subprojects

एक subproject किसी parent के अंदर एक child Veles project है। एक बनाएँ:

```bash
veles subproject init frontend --description "the web client"
veles subproject list
cd "$(veles subproject switch frontend)"
veles subproject remove frontend    # unregister (files untouched)
```

### Veles को एक split सुझाने दें

जब किसी project की wiki बढ़ती है, तो Veles thematic clusters का पता लगा सकता है और उन्हें
subprojects के रूप में प्रस्तावित कर सकता है:

```bash
veles subproject suggest            # print candidates
veles subproject suggest --save     # save each to .veles/memory/proposals/ for recall
```

## कब किसका उपयोग करें

- **अलग projects** — असंबंधित knowledge bases / codebases।
- **Subprojects** — किसी एक बड़ी चीज़ के हिस्से जिन्हें scoped memory से फ़ायदा होता है लेकिन
  एक parent context साझा करते हैं।

देखें [architecture](../explanation/architecture.md) कि कैसे multi-project context
एक monolithic dump के बजाय माँग पर load होता है।

# Skills, tools, और modules कैसे manage करें

> 🌐 **भाषाएँ:** [English](../../en/how-to/manage-skills-and-tools.md) · [简体中文](../../zh-CN/how-to/manage-skills-and-tools.md) · [繁體中文](../../zh-TW/how-to/manage-skills-and-tools.md) · [日本語](../../ja/how-to/manage-skills-and-tools.md) · [한국어](../../ko/how-to/manage-skills-and-tools.md) · [Español](../../es/how-to/manage-skills-and-tools.md) · [Français](../../fr/how-to/manage-skills-and-tools.md) · [Italiano](../../it/how-to/manage-skills-and-tools.md) · [Português (BR)](../../pt-BR/how-to/manage-skills-and-tools.md) · [Português (PT)](../../pt-PT/how-to/manage-skills-and-tools.md) · [Русский](../../ru/how-to/manage-skills-and-tools.md) · [العربية](../../ar/how-to/manage-skills-and-tools.md) · **हिन्दी** · [বাংলা](../../bn/how-to/manage-skills-and-tools.md) · [Tiếng Việt](../../vi/how-to/manage-skills-and-tools.md)

Veles समय के साथ capability जमा करता है। **Skills** पुनः-उपयोग योग्य workflows हैं,
**tools** executable actions हैं, **modules** वैकल्पिक plug-ins हैं। हर एक दो
scopes पर रहता है: project-local (`<project>/.veles/`) और user-global (`~/.veles/`)।
concepts के लिए देखें [skills & tools](../explanation/skills-and-tools.md)।

## Skills

एक skill एक `SKILL.md` है (frontmatter + prompt body) जिसे agent किसी tool की तरह invoke कर सकता है।

```bash
veles skill list                          # installed skills + telemetry
veles skill show <name>                   # print its SKILL.md
veles skill add https://github.com/org/skill.git
veles skill add ./local-skill --scope user   # install user-global
veles skill remove <name>
```

### scopes के बीच promote / demote करें

एक skill जो किसी एक project में उपयोगी साबित होती है उसे user scope में move किया जा सकता है ताकि हर project
उसे देखे (या इसका उल्टा):

```bash
veles skill promote <name>     # project → ~/.veles/skills/
veles skill demote  <name>     # user → this project
```

### duplicates और promotion candidates खोजें

```bash
veles skill dedup                         # near-duplicate skills (embedding/TF-IDF)
veles skill suggest-promote --save        # skills that meet the auto-promote bar
```

## Tools

Tools project की `memory.db` में usage telemetry के साथ catalogued होते हैं। Veles काम करते-करते
अपने खुद के tools लिख सकता है; आप उन्हें इनसे manage करते हैं:

```bash
veles tool list                # tools in this project
veles tool show <name>         # manifest + telemetry
veles tool promote <name>      # move to ~/.veles/tools/ (cross-project)
```

संवेदनशील tools (`run_shell`, `write_file`, `fetch_url`, …) पर
[trust ladder](security-and-permissions.md) का नियंत्रण रहता है।

## Modules

Modules core को फुलाए बिना वैकल्पिक capabilities (embeddings, vision, STT) जोड़ते हैं।
किसी एक को install करने के लिए default रूप से confirmation चाहिए।

```bash
veles module list
veles module add https://github.com/org/module.git
veles module remove <name>
```

## और खोजें

curated registries browse करें:

```bash
veles browse skills [query]
veles browse modules [query]
```

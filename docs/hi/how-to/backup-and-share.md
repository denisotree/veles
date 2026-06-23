# किसी project का backup और share कैसे करें

> 🌐 **भाषाएँ:** [English](../../en/how-to/backup-and-share.md) · [简体中文](../../zh-CN/how-to/backup-and-share.md) · [繁體中文](../../zh-TW/how-to/backup-and-share.md) · [日本語](../../ja/how-to/backup-and-share.md) · [한국어](../../ko/how-to/backup-and-share.md) · [Español](../../es/how-to/backup-and-share.md) · [Français](../../fr/how-to/backup-and-share.md) · [Italiano](../../it/how-to/backup-and-share.md) · [Português (BR)](../../pt-BR/how-to/backup-and-share.md) · [Português (PT)](../../pt-PT/how-to/backup-and-share.md) · [Русский](../../ru/how-to/backup-and-share.md) · [العربية](../../ar/how-to/backup-and-share.md) · **हिन्दी** · [বাংলা](../../bn/how-to/backup-and-share.md) · [Tiếng Việt](../../vi/how-to/backup-and-share.md)

Veles projects portable होते हैं। backup या migration के लिए किसी project को एक
ही `.tar.gz` bundle में export करें, या अपने data को लीक किए बिना share करने के
लिए एक sanitised template।

## पूर्ण backup

पूरे project (`.veles/` + `AGENTS.md`) को packs करता है, runtime ephemera (locks,
budget state) को छोड़कर:

```bash
veles export full ./my-project-backup.tar.gz
```

इसे कहीं भी restore करें:

```bash
veles import ./my-project-backup.tar.gz                # into cwd
veles import ./my-project-backup.tar.gz --into ./restored
veles import ./my-project-backup.tar.gz --force        # overwrite an existing .veles/
```

एक पूर्ण bundle में आपका `memory.db` (sessions, insights) शामिल होता है, इसलिए
इसे private data की तरह मानें।

## Shareable template

केवल पुनः-उपयोग्य scaffolding को packs करता है — schema, skills, modules, और
non-session wiki पेज। यह `memory.db`, `sources/`, `sessions/`, trust grants को
**हटा देता है**, और text को PII-redact करता है:

```bash
veles export template ./my-template.tar.gz
```

Template को किसी सहकर्मी को दें; वे इसे `veles import` करते हैं और आपकी
conversation history या raw sources के बिना आपकी संरचना और skills पा लेते हैं।

## किसका उपयोग करें

| लक्ष्य | Command |
|---|---|
| किसी project का अक्षुण्ण backup / move करना | `veles export full` |
| संरचना + skills share करना, data नहीं | `veles export template` |

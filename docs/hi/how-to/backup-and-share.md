# किसी project का backup और share कैसे करें

> 🌐 **भाषाएँ:** **English** · [Русский](../../ru/how-to/backup-and-share.md)

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

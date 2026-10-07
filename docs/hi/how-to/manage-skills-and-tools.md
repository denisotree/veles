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

module Python code (`module.toml` + एक entrypoint) है जो Veles के अंदर चलता है — core को फुलाए
बिना वैकल्पिक capabilities (memory providers, embeddings, vision, STT) जोड़ता है। किसी एक को
install करने के लिए default रूप से confirmation चाहिए, और वह हर run में तभी load होता है जब
तक उसकी files वैसी ही हों जैसी आपने approve की थीं (देखें [installs को ईमानदार
रखें](../../en/how-to/extension-registries.md#keep-installs-honest))।

```bash
veles module list                              # both scopes, with a `scope` column
veles module add https://github.com/org/module.git
veles module add ./local-module --user          # install to ~/.veles/modules/, all projects
veles module show <name> [--user]             # manifest + files का sha256
veles module remove <name> [--user]
veles module approve <name> [--user]          # terminal पर `yes` टाइप करें
veles module approve <name> --sha256 <hash>   # terminal के बिना: आपका समीक्षा किया हुआ hash
```

Modules दो scopes में रहते हैं, skills और tools की तरह: project-local
(`<project>/.veles/modules/`) और user-global (`~/.veles/modules/`, हर project में load होता है)।
user-level module उसी approval gate से गुज़रता है जिससे project वाला, और gate नामों की तुलना से
पहले चलता है। अगर project और user module का नाम एक ही हो, तो approved project module load होता
है और Veles चेतावनी देता है कि user-level वाला shadow हो गया; unapproved project module skip
होता है (warning में उसकी directory का नाम होता है) और user module load होता है। एक ही scope के
दो approved modules का नाम एक हो — पहला (directory के क्रम में) load होता है, बाकी warn करके
skip होते हैं। `veles module {show,approve,remove}` manifest name लेते हैं (जो `list` दिखाता है)
और ऐसा नाम अस्वीकार करते हैं जिसे scope की एक से अधिक directory declare करती हो, और उन्हें
सूचीबद्ध करते हैं; `veles module add` ऐसे module को install करने से मना करता है जिसका नाम scope
की कोई और directory पहले से declare करती हो।

### memory provider जोड़ने वाला module लिखें

module का `register(api)` entrypoint `api.add_memory_provider(name, factory)` बुला सकता है
ताकि कोई external memory source recall में plug हो जाए। `name` को `~/.veles/config.toml` के
किसी `[memory.external.<name>]` section से मेल खाना चाहिए; `factory` को वह section (एक `dict`)
देकर बुलाया जाता है और उसे Veles का `MemoryProvider` protocol (`veles.core.memory.provider`)
implement करने वाला object लौटाना चाहिए, या provider को skip करने के लिए `None`:

```toml
# module.toml
[module]
name = "my-provider"
description = "Recalls memories from my external store."
entrypoint = "my_provider.py:register"
version = "0.1.0"
```

```python
# my_provider.py
from veles.core.memory.provider import RecallHit


class MyProvider:
    name = "my-provider"

    def recall(self, query: str, *, limit: int) -> list[RecallHit]:
        ...  # query the external store, return RecallHit objects


def _build(cfg: dict) -> MyProvider | None:
    api_key = cfg.get("api_key")
    return MyProvider() if api_key else None


def register(api) -> None:
    api.add_memory_provider("my-provider", _build)
```

```toml
# ~/.veles/config.toml
[memory.external.my-provider]
api_key = "..."
```

जो provider `ingest(title, body, *, insight_id) ->
bool` (`IngestingMemoryProvider` protocol) भी implement करता है, उसे Veles के writes भी
मिलते हैं, सिर्फ़ reads नहीं। अगर दो modules एक ही provider name register करें, तो दूसरे module
का load fail होता है — उसे warning के साथ skip किया जाता है, कुछ भी आधा-register नहीं रहता।
`config.toml` में configure किया गया जो section है पर उसका module install नहीं है, वह install
command के साथ एक warning print करता है; recall उसके बिना काम करता रहता है।

registry Honcho, Mem0 और Supermemory को तैयार provider modules के रूप में देती है — इन्हें
`veles registry install --user {honcho,mem0,supermemory}` से install करें, फिर install जो
`uv tool install veles-ai --with '<package>'` command print करे उसे चलाएँ (हर एक एक SDK declare
करता है — `mem0ai>=2.0`, `honcho-ai>=2.5`, `supermemory>=3.62` — जिसे Veles आपके लिए कभी install
नहीं करता), और संबंधित `[memory.external.<name>]` section भरें:

- **mem0**: `api_key`, `user_id`, optional `agent_id` (उस agent की memories भी recall करें) और
  `host`। SDK telemetry default रूप से बंद है; हर recall एक अतिरिक्त `GET /v1/ping/` request
  करता है।
- **supermemory**: `api_key`, optional `user_id` (search के `container_tag` के रूप में भेजा जाता
  है) और `base_url`।
- **honcho**: `api_key`, `workspace_id`, optional `peer_id` (केवल उस peer के messages में search
  करें) और `base_url`। हर recall workspace का get-or-create करता है — अगर `workspace_id` पहले
  से मौजूद नहीं है तो उसे बना देता है।

## और खोजें

connected registries में search करें:

```bash
veles registry search [query] [--kind module|skill|layout|mcp]
```

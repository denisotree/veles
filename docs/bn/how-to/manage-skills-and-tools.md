# Skill, tool, ও module কীভাবে পরিচালনা করবেন

> 🌐 **ভাষা:** [English](../../en/how-to/manage-skills-and-tools.md) · [简体中文](../../zh-CN/how-to/manage-skills-and-tools.md) · [繁體中文](../../zh-TW/how-to/manage-skills-and-tools.md) · [日本語](../../ja/how-to/manage-skills-and-tools.md) · [한국어](../../ko/how-to/manage-skills-and-tools.md) · [Español](../../es/how-to/manage-skills-and-tools.md) · [Français](../../fr/how-to/manage-skills-and-tools.md) · [Italiano](../../it/how-to/manage-skills-and-tools.md) · [Português (BR)](../../pt-BR/how-to/manage-skills-and-tools.md) · [Português (PT)](../../pt-PT/how-to/manage-skills-and-tools.md) · [Русский](../../ru/how-to/manage-skills-and-tools.md) · [العربية](../../ar/how-to/manage-skills-and-tools.md) · [हिन्दी](../../hi/how-to/manage-skills-and-tools.md) · **বাংলা** · [Tiếng Việt](../../vi/how-to/manage-skills-and-tools.md)

Veles সময়ের সাথে সাথে সক্ষমতা সঞ্চয় করে। **Skill** হলো পুনঃব্যবহারযোগ্য workflow, **tool** হলো executable action, **module** হলো ঐচ্ছিক plug-in। প্রতিটি দুটি scope-এ থাকে: project-local (`<project>/.veles/`) এবং user-global (`~/.veles/`)। ধারণাগুলোর জন্য দেখুন [skills & tools](../explanation/skills-and-tools.md)।

## Skills

একটি skill হলো একটি `SKILL.md` (frontmatter + প্রম্পট body) যা এজেন্ট একটি টুলের মতো invoke করতে পারে।

```bash
veles skill list                          # installed skills + telemetry
veles skill show <name>                   # print its SKILL.md
veles skill add https://github.com/org/skill.git
veles skill add ./local-skill --scope user   # install user-global
veles skill remove <name>
```

### scope-এর মধ্যে promote / demote

একটি প্রকল্পে উপযোগী প্রমাণিত একটি skill-কে user scope-এ সরানো যায় যাতে প্রতিটি প্রকল্প সেটি দেখতে পায় (অথবা উল্টোটা):

```bash
veles skill promote <name>     # project → ~/.veles/skills/
veles skill demote  <name>     # user → this project
```

### duplicate ও promotion-প্রার্থী খুঁজে বের করা

```bash
veles skill dedup                         # near-duplicate skills (embedding/TF-IDF)
veles skill suggest-promote --save        # skills that meet the auto-promote bar
```

## Tools

Tool-গুলো প্রকল্পের `memory.db`-তে ব্যবহারের telemetry-সহ ক্যাটালগ করা থাকে। কাজ করার সময় Veles নিজের টুল লিখতে পারে; আপনি সেগুলো পরিচালনা করেন এর মাধ্যমে:

```bash
veles tool list                # tools in this project
veles tool show <name>         # manifest + telemetry
veles tool promote <name>      # move to ~/.veles/tools/ (cross-project)
```

সংবেদনশীল টুল (`run_shell`, `write_file`, `fetch_url`, …) [trust ladder](security-and-permissions.md) দ্বারা নিয়ন্ত্রিত।

## Modules

একটি module হলো Python কোড (`module.toml` + একটি entrypoint) যা Veles-এর ভেতরে চলে — core-কে ভারী না করেই
ঐচ্ছিক সক্ষমতা (memory provider, embeddings, vision, STT) যোগ করে। একটি ইনস্টল করতে ডিফল্টভাবে
নিশ্চিতকরণ প্রয়োজন, এবং এর ফাইল আপনার অনুমোদিত অবস্থার সঙ্গে মিললেই তবে প্রতিটি run-এ এটি লোড হয়
([ইনস্টল নির্ভরযোগ্য রাখুন](../../en/how-to/extension-registries.md#keep-installs-honest) দেখুন)।

```bash
veles module list                              # both scopes, with a `scope` column
veles module add https://github.com/org/module.git
veles module add ./local-module --user          # install to ~/.veles/modules/, all projects
veles module show <name> [--user]
veles module remove <name> [--user]
veles module approve <name> [--user]
```

Skill ও tool-এর মতোই module-ও দুই scope-এ থাকে: প্রজেক্ট-লোকাল (`<project>/.veles/modules/`) এবং
user-global (`~/.veles/modules/`, প্রতিটি প্রজেক্টে লোড হয়)। user-level module প্রজেক্টের module-এর মতোই একই
অনুমোদন-গেটের মধ্য দিয়ে যায়, এবং গেটটি নাম তুলনার আগে চলে। প্রজেক্ট ও user module-এর নাম এক হলে,
অনুমোদিত প্রজেক্ট module লোড হয় এবং Veles user-level module-টি ঢাকা পড়ার বিষয়ে সতর্ক করে; অননুমোদিত
প্রজেক্ট module এড়িয়ে যাওয়া হয় (warning-এ তার ডিরেক্টরির নাম থাকে) এবং user module লোড হয়। একই scope-এ
একই নামের দুটি অনুমোদিত module থাকলে — প্রথমটি (ডিরেক্টরি অনুযায়ী সাজানো) লোড হয়, বাকিগুলো warn করে এবং
এড়িয়ে যাওয়া হয়। `veles module {show,approve,remove}` manifest-এর নাম নেয় (`list` যা দেখায়) এবং scope-এ
একাধিক ডিরেক্টরি যে নাম ঘোষণা করে তা প্রত্যাখ্যান করে, ডিরেক্টরিগুলো তালিকাভুক্ত করে; `veles module add`
এমন module ইনস্টল করতে অস্বীকার করে যার নাম scope-এর অন্য কোনো ডিরেক্টরি ইতিমধ্যে ঘোষণা করেছে।

### memory provider যোগ করে এমন module লেখা

module-এর `register(api)` entrypoint `api.add_memory_provider(name, factory)` কল করে recall-এ একটি বাহ্যিক
memory source যুক্ত করতে পারে। `name` অবশ্যই `~/.veles/config.toml`-এর একটি `[memory.external.<name>]`
section-এর সঙ্গে মিলতে হবে; `factory` ওই section (একটি `dict`) নিয়ে কল হয় এবং Veles-এর `MemoryProvider`
protocol (`veles.core.memory.provider`) বাস্তবায়নকারী একটি object ফেরত দিতে হবে, অথবা provider এড়াতে `None`:

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

যে provider `ingest(title, body, *, insight_id) -> bool` (`IngestingMemoryProvider` protocol)-ও বাস্তবায়ন করে,
সে শুধু read নয়, Veles-এর write-ও পায়। দুটি module একই provider নাম register করলে দ্বিতীয় module লোড
ব্যর্থ হয় — warning দিয়ে এড়িয়ে যাওয়া হয়, আংশিক কিছু register হয়ে থাকে না। `config.toml`-এ কনফিগার করা
কোনো section-এর module ইনস্টল না থাকলে install কমান্ডসহ একটি warning ছাপা হয়; এটি ছাড়াও recall কাজ করে।

registry-তে Honcho, Mem0 ও Supermemory তৈরি-করা provider module হিসেবে আছে — ইনস্টল করুন
`veles registry install --user {honcho,mem0,supermemory}` দিয়ে, তারপর install যে
`uv tool install veles-ai --with '<package>'` কমান্ড ছাপে তা চালান (প্রতিটি একটি SDK ঘোষণা করে —
`mem0ai>=2.0`, `honcho-ai>=2.5`, `supermemory>=3.62` — যা Veles কখনো আপনার হয়ে ইনস্টল করে না), এবং
সংশ্লিষ্ট `[memory.external.<name>]` section পূরণ করুন:

- **mem0**: `api_key`, `user_id`, ঐচ্ছিক `agent_id` (ওই agent-এর memory-ও recall করে) ও `host`। SDK
  telemetry ডিফল্টভাবে বন্ধ; প্রতিটি recall একটি বাড়তি `GET /v1/ping/` অনুরোধ করে।
- **supermemory**: `api_key`, ঐচ্ছিক `user_id` (search-এর `container_tag` হিসেবে পাঠানো হয়) ও `base_url`।
- **honcho**: `api_key`, `workspace_id`, ঐচ্ছিক `peer_id` (শুধু ওই peer-এর message search করে) ও `base_url`।
  প্রতিটি recall একটি workspace get-or-create করে — `workspace_id` না থাকলে তৈরি করে।

## আরও আবিষ্কার করুন

সংযুক্ত registry-গুলোতে অনুসন্ধান করুন:

```bash
veles registry search [query] [--kind module|skill|layout|mcp]
```

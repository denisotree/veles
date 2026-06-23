# Skill, tool, ও module কীভাবে পরিচালনা করবেন

> 🌐 **Languages:** [English](../../en/how-to/manage-skills-and-tools.md) · [Русский](../../ru/how-to/manage-skills-and-tools.md) · **বাংলা**

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

Module-গুলো core-কে ভারী না করেই ঐচ্ছিক সক্ষমতা (embeddings, vision, STT) যোগ করে। একটি ইনস্টল করতে ডিফল্টভাবে নিশ্চিতকরণ প্রয়োজন।

```bash
veles module list
veles module add https://github.com/org/module.git
veles module remove <name>
```

## আরও আবিষ্কার করুন

curated registry-গুলো ব্রাউজ করুন:

```bash
veles browse skills [query]
veles browse modules [query]
```

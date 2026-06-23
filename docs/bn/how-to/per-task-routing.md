# বিভিন্ন মডেলে কাজ কীভাবে route করবেন

> 🌐 **Languages:** [English](../../en/how-to/per-task-routing.md) · [Русский](../../ru/how-to/per-task-routing.md) · **বাংলা**

Veles একটি মডেলে আবদ্ধ নয়। প্রতিটি অভ্যন্তরীণ **task** ভিন্ন একটি `provider:model` ব্যবহার করতে পারে — context compression-এর জন্য একটি সস্তা মডেল, মূল এজেন্টের জন্য একটি শক্তিশালী মডেল, ছবির জন্য একটি vision মডেল। এটিই হলো *ensemble routing* সিস্টেম।

## Task type-সমূহ

| Task | যে কাজে ব্যবহৃত হয় |
|---|---|
| `default` | মূল এজেন্ট লুপ |
| `curator` | Session → wiki একত্রীকরণ |
| `compressor` | Sliding-window context compression |
| `insights` | রান-পরবর্তী insight extraction |
| `skills` | Skill execution |
| `advisor` | `advisor_review` self-check |
| `vision` | `image_describe` (যখন একটি vision adapter যুক্ত থাকে) |
| `embedding` | `veles skill dedup` similarity |

## বর্তমান routing দেখুন

```bash
veles route show
```

এটি প্রতিটি task-এর জন্য সমাধানকৃত `provider:model` প্রিন্ট করে এবং একটি `source` লেবেল দেয় যা বলে কোন স্তর সেটি নির্ধারণ করেছে।

## একটি task-কে একটি মডেলে pin করা

```bash
veles route set compressor openrouter:anthropic/claude-haiku-4.5
veles route set advisor    openrouter:anthropic/claude-opus-4.8
veles route set vision     openai:gpt-4o
```

এগুলো `<project>/.veles/config.toml`-এ `[routing.tasks]` লেখে:

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

## AGENTS.md-তে natural-language hint

আপনি `AGENTS.md`-এ গদ্যে routing প্রকাশ করতে পারেন (যেমন "use a cheap model for compression")। Veles এগুলো পার্স করে একটি স্বয়ংক্রিয়ভাবে তৈরি `routing.nl.toml`-এ পরিণত করে:

```bash
veles route refresh            # re-parse AGENTS.md hints
veles route refresh --force    # even if AGENTS.md hasn't changed
```

সুস্পষ্ট `[routing.tasks]` এন্ট্রি সবসময় NL hint-এর উপর জয়ী হয়।

## সমাধানের ক্রম

প্রতিটি task-এর জন্য, যে প্রথম স্তর একটি spec দেয় সেটিই জয়ী হয়:

1. project `[routing.tasks][task]`
2. project `[routing.tasks].default`
3. project NL hint (`routing.nl.toml`)
4. project `[provider]` base
5. user `[routing.tasks][task]` / `.default`
6. user `[user] default_provider` + `default_model`
7. সেই task-এর জন্য বিল্ট-ইন ডিফল্ট

(`embedding` catch-all গুলো এড়িয়ে যায় — একটি chat মডেল embedding মডেল নয়।)

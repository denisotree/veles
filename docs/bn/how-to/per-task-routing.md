# বিভিন্ন মডেলে টাস্ক কীভাবে রাউট করবেন

> 🌐 **Languages:** **English** · [Русский](../../ru/how-to/per-task-routing.md)

Veles একটিমাত্র মডেলে আটকে নেই। প্রতিটি ইন্টারনাল **টাস্ক** একটি ভিন্ন
`provider:model` ব্যবহার করতে পারে — কনটেক্সট কম্প্রেশনের জন্য একটি সস্তা মডেল, মূল
এজেন্টের জন্য একটি শক্তিশালী মডেল, ছবির জন্য একটি vision মডেল। এটিই *ensemble রাউটিং* সিস্টেম।

## টাস্ক টাইপ

| টাস্ক | যার জন্য ব্যবহৃত |
|---|---|
| `default` | মূল এজেন্ট লুপ |
| `curator` | Session → wiki কনসলিডেশন |
| `compressor` | স্লাইডিং-উইন্ডো কনটেক্সট কম্প্রেশন |
| `insights` | রান-পরবর্তী insight এক্সট্রাকশন |
| `skills` | Skill এক্সিকিউশন |
| `advisor` | `advisor_review` সেলফ-চেক |
| `vision` | `image_describe` (যখন একটি vision অ্যাডাপ্টার ওয়্যার করা থাকে) |
| `embedding` | `veles skill dedup` সিমিলারিটি |

## বর্তমান রাউটিং দেখুন

```bash
veles route show
```

এটি প্রতিটি টাস্কের জন্য রিজলভ করা `provider:model` এবং কোন লেয়ার এটি সিদ্ধান্ত
নিয়েছে তা জানানো একটি `source` লেবেল প্রিন্ট করে।

## একটি টাস্ককে একটি মডেলে পিন করুন

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

## রিসেট

```bash
veles route reset compressor   # one task back to default
veles route reset              # all tasks back to default
```

## AGENTS.md-এ ন্যাচারাল-ল্যাঙ্গুয়েজ হিন্ট

আপনি `AGENTS.md`-এ গদ্যে রাউটিং প্রকাশ করতে পারেন (যেমন "use a cheap model for
compression")। Veles এগুলো একটি অটো-জেনারেটেড `routing.nl.toml`-এ পার্স করে:

```bash
veles route refresh            # re-parse AGENTS.md hints
veles route refresh --force    # even if AGENTS.md hasn't changed
```

স্পষ্ট `[routing.tasks]` এন্ট্রি সর্বদা NL হিন্টের উপরে জেতে।

## রিজলিউশন ক্রম

প্রতিটি টাস্কের জন্য, প্রথম যে লেয়ার একটি স্পেক দেয় সেটি জেতে:

1. project `[routing.tasks][task]`
2. project `[routing.tasks].default`
3. project NL hint (`routing.nl.toml`)
4. project `[provider]` base
5. user `[routing.tasks][task]` / `.default`
6. user `[user] default_provider` + `default_model`

এগুলোর কোনোটিই রিজলভ না হলে, **কোনো হার্ডকোডেড ফলব্যাক নেই** — টাস্কটি আনসেট থাকে
এবং এর কলার ডিগ্রেড করে (ফিচারটি এড়িয়ে যায়) বা স্পষ্টভাবে এরর দেয়, নীরবে একটি
ক্লাউড মডেলের দিকে হাত বাড়ানোর পরিবর্তে।

(`embedding` catch-all-গুলো এড়িয়ে যায় — একটি চ্যাট মডেল কোনো embedding মডেল নয় —
তাই শুধু একটি স্পষ্ট `[routing.tasks].embedding` এটির উত্তর দেয়।)

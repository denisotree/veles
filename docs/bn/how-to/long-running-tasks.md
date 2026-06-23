# দীর্ঘ-সময়ের কাজ কীভাবে চালাবেন: goals, jobs, dreaming, research

> 🌐 **Languages:** [English](../../en/how-to/long-running-tasks.md) · [Русский](../../ru/how-to/long-running-tasks.md) · **বাংলা**

একক প্রম্পটের বাইরেও Veles বাজেটসহ বহু-ধাপের **goal** অনুসরণ করতে পারে, **scheduled job** চালাতে পারে, মেমরি একত্রীকরণের জন্য **dream** করতে পারে, সমান্তরালে ওয়েব **research** করতে পারে, এবং একটি **manager** ও sub-agent-দের মধ্যে কাজ ভাগ করে দিতে পারে।

## Goals — বাজেট ও checkpoint-সহ লক্ষ্য

একটি goal হলো সুস্পষ্ট সীমা ও একটি অগ্রগতি লগসহ একটি দীর্ঘ-দিগন্তের লক্ষ্য:

```bash
veles goal start "Draft a competitor analysis report" \
  --done-when "report.md exists and cites >=3 sources" \
  --max-steps 30 --max-cost-usd 5 --max-wall-time-s 3600

veles goal list
veles goal show <id>
veles goal checkpoint <id> "Outlined sections; cited 2 sources" --cost-usd 0.40
veles goal pause <id> ; veles goal resume <id>
veles goal done <id> --evidence report.md
veles goal cancel <id> --reason "scope changed"
```

TUI-তে, **goal** run mode (`Shift+Tab` দিয়ে cycle করুন) একই FSM-কে ইন্টারঅ্যাক্টিভভাবে চালায়: এটি আপনাকে প্রশ্ন করে, একটি পরিকল্পনা নিশ্চিত করে, কার্যকর করে, এবং যাচাই করে।

## Jobs — scheduled এজেন্ট রান

একটি প্রম্পটকে cron expression, একটি interval, বা একবার একটি নির্দিষ্ট সময়ে চালানোর জন্য schedule করুন:

```bash
veles job add --name daily-digest \
  --schedule "0 9 * * *" \
  --prompt "Summarise yesterday's sessions into wiki/digests/"

veles job list
veles job history <id>
veles job trigger <id>          # run on the next tick
veles job pause <id> ; veles job resume <id>
veles job remove <id>
```

`--schedule` একটি cron expression, `<N><s|m|h|d>` (যেমন `30m`), অথবা একটি ISO timestamp গ্রহণ করে। daemon চালু থাকলে job-গুলো চলে, অথবা সবগুলোকে একবারে synchronously চালান:

```bash
veles job tick                  # run due jobs now, no daemon needed
```

`--deliver-to telegram:<chat_id>` দিয়ে একটি job-এর আউটপুট একটি channel-এ পৌঁছে দিন।

## Dreaming — ব্যাকগ্রাউন্ড মেমরি একত্রীকরণ

`dream` insight বের করে, skill deduplicate করে, promotion-এর পরামর্শ দেয়, এবং wiki lint করে — আপনাকে অপেক্ষা না করিয়েই মেমরি সতেজ রাখে:

```bash
veles dream
veles dream --include-consolidation     # also run the (paid) LLM consolidation
veles dream --dry-run                    # show what it would do
```

একটি চলমান daemon idle থাকলে স্বয়ংক্রিয়ভাবে dream করে।

## Research — সমান্তরাল ওয়েব অনুসন্ধান

```bash
veles research "What are the leading approaches to retrieval-augmented generation?" \
  --max-subquestions 4
```

Veles প্রশ্নটিকে ভাগ করে, সমান্তরালে বিভিন্ন দিক অন্বেষণ করে, এবং একটি উদ্ধৃতিসহ রিপোর্ট সংশ্লেষণ করে।

## Manager mode — যেকোনো প্রম্পট ভাগ করা

একটি একক রানের জন্য multi-agent decomposition চালু করুন (একটি manager explorer / writer / advisor sub-agent spawn করে এবং চূড়ান্ত উত্তর নিজে কখনো লেখে না):

```bash
veles run --manager "Audit this codebase for security issues and write a report"
# or globally: export VELES_MANAGER_MODE=1   (=0 to force off)
```

দেখুন [multi-agent orchestration](../explanation/multi-agent-orchestration.md)।

# শুরু করা

> 🌐 **Languages:** **English** · [Русский](../../ru/tutorials/getting-started.md)

এই টিউটোরিয়ালে আপনি Veles ইনস্টল করবেন, এটিকে একটি API কী দেবেন, আপনার প্রথম
প্রজেক্ট তৈরি করবেন, এবং আপনার প্রথম প্রম্পট চালাবেন। প্রায় ১০ মিনিট। শেষে আপনার
হাতে থাকবে একটি কর্মক্ষম Veles প্রজেক্ট যার সাথে আপনি কথা বলতে পারবেন।

## পূর্বশর্ত

- **Python 3.13+** (Veles-এর `>=3.13` প্রয়োজন)।
- একটি LLM API কী। আমরা **OpenRouter** (ডিফল্ট প্রোভাইডার) ব্যবহার করব; যেকোনো
  [অন্যান্য প্রোভাইডার](../reference/providers.md)-ও কাজ করে, এমনকি কোনো কী ছাড়া
  সম্পূর্ণ লোকাল প্রোভাইডারও।

## ১. ইনস্টল

Veles [uv](https://docs.astral.sh/uv/)-এর মাধ্যমে একটি গ্লোবাল `veles` কমান্ড হিসেবে ইনস্টল হয়:

```bash
# install uv if you don't have it
curl -LsSf https://astral.sh/uv/install.sh | sh

# install veles (published as `veles-ai`; the command is `veles`)
uv tool install veles-ai
# …or from a source checkout: uv tool install .

# verify
veles --help
```

পরে আপডেট করতে: `uv tool upgrade veles-ai`।

## ২. Veles-কে একটি API কী দিন

[openrouter.ai](https://openrouter.ai) থেকে একটি কী নিন এবং এক্সপোর্ট করুন:

```bash
export OPENROUTER_API_KEY=sk-or-v1-...
```

আপনি এটি OS keychain-এও সংরক্ষণ করতে পারেন যাতে প্রতিটি শেলে পুনরায় এক্সপোর্ট করতে না হয়:

```bash
veles secret set OPENROUTER_API_KEY
```

(কোনো কী ছাড়া সম্পূর্ণ লোকাল সেটআপ পছন্দ করেন? [Ollama](https://ollama.com) ইনস্টল করুন,
`ollama pull qwen3:4b-instruct` চালান, এবং নিচে `--provider ollama` ব্যবহার করুন।)

## ৩. আপনার প্রথম প্রজেক্ট তৈরি করুন

একটি Veles প্রজেক্ট মানে শুধু একটি ডিরেক্টরি যাতে একটি `.veles/` স্টেট ফোল্ডার আছে। একটি তৈরি করুন:

```bash
mkdir my-notes && cd my-notes
veles init my-notes
```

এটি তৈরি করে `AGENTS.md` (আপনার প্রজেক্ট কনটেক্সট), `sources/` ও `wiki/` (ডিফল্ট
[LLM-Wiki লেআউট](../explanation/layout-packs-and-llm-wiki.md)), এবং
`.veles/` (মেশিন স্টেট)। দেখুন [প্রজেক্ট লেআউট](../reference/project-layout.md)।

## ৪. আপনার প্রথম প্রম্পট চালান

```bash
veles run "Read AGENTS.md and describe this project in three sentences."
```

Veles আপনার প্রজেক্ট কনটেক্সট লোড করে, মডেল কল করে, এবং উত্তর প্রিন্ট করে। টার্নটি
প্রজেক্টের মেমরিতে সংরক্ষিত হয়।

টোকেন আসার সাথে সাথে দেখতে `--stream` যোগ করুন, বা প্রতি-টার্ন অগ্রগতির জন্য `--verbose`:

```bash
veles run --stream "What files exist in this project right now?"
```

## ৫. ইন্টারঅ্যাক্টিভ REPL খুলুন

একটি মাল্টি-টার্ন কথোপকথনের জন্য, TUI খুলুন:

```bash
veles tui
```

একটি মেসেজ টাইপ করুন এবং Enter চাপুন। দরকারি কী: প্রস্থানে `Ctrl+D`, [রান মোড](../explanation/modes.md)
সাইকেল করতে `Shift+Tab`, স্ল্যাশ কমান্ড তালিকাভুক্ত করতে `/help`। সম্পূর্ণ
তালিকা [TUI রেফারেন্স](../reference/tui.md)-এ।

## ৬. Veles কী মনে রাখে দেখুন

প্রতিটি রান সংরক্ষিত হয়। আপনার সেশন তালিকাভুক্ত ও সার্চ করুন:

```bash
veles sessions list
veles sessions search "three sentences"
```

## এরপর কোথায় যাবেন

- **[একটি নলেজ বেস তৈরি করা](building-a-knowledge-base.md)** — উইকিতে সোর্স ইনজেস্ট
  করুন এবং সেগুলো সম্পর্কে প্রশ্ন করুন।
- **[প্রোভাইডার কনফিগার করুন](../how-to/configure-providers.md)** — Anthropic,
  OpenAI, Gemini, বা একটি সম্পূর্ণ লোকাল মডেলে স্যুইচ করুন।
- **[আর্কিটেকচার ওভারভিউ](../explanation/architecture.md)** — Veles পর্দার আড়ালে কী
  করছে তা বুঝুন।

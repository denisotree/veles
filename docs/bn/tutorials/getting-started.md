# শুরু করা

> 🌐 **ভাষা:** [English](../../en/tutorials/getting-started.md) · [Русский](../../ru/tutorials/getting-started.md)

এই টিউটোরিয়ালে আপনি Veles ইনস্টল করবেন, এটিকে একটি API key দেবেন, আপনার প্রথম প্রজেক্ট তৈরি করবেন, এবং আপনার প্রথম prompt চালাবেন। প্রায় ১০ মিনিট। শেষে আপনার কাছে একটি কর্মক্ষম Veles প্রজেক্ট থাকবে যার সঙ্গে আপনি কথা বলতে পারবেন।

## পূর্বশর্ত

- **Python 3.13+** (Veles-এর জন্য `>=3.13` প্রয়োজন)।
- একটি LLM API key। আমরা **OpenRouter** ব্যবহার করব (ডিফল্ট provider); [অন্য যেকোনো provider](../reference/providers.md)-ও কাজ করে, এমনকি key ছাড়া সম্পূর্ণ লোকাল provider-ও।

## ১. ইনস্টল করা

Veles [uv](https://docs.astral.sh/uv/)-এর মাধ্যমে একটি গ্লোবাল `veles` কমান্ড হিসেবে ইনস্টল হয়:

```bash
# install uv if you don't have it
curl -LsSf https://astral.sh/uv/install.sh | sh

# from the Veles source directory
uv tool install .

# verify
veles --help
```

পরে আপডেট করতে: `uv tool install . --reinstall`।

## ২. Veles-কে একটি API key দেওয়া

[openrouter.ai](https://openrouter.ai) থেকে একটি key নিন এবং export করুন:

```bash
export OPENROUTER_API_KEY=sk-or-v1-...
```

প্রতিবার shell-এ পুনরায় export করা এড়াতে আপনি এটি OS keychain-এও সংরক্ষণ করতে পারেন:

```bash
veles secret set OPENROUTER_API_KEY
```

(key ছাড়া সম্পূর্ণ লোকাল সেটআপ পছন্দ করেন? [Ollama](https://ollama.com) ইনস্টল করুন, `ollama pull qwen3:4b-instruct` চালান, এবং নিচে `--provider ollama` ব্যবহার করুন।)

## ৩. আপনার প্রথম প্রজেক্ট তৈরি করা

একটি Veles প্রজেক্ট মানে শুধু একটি ডিরেক্টরি যার মধ্যে একটি `.veles/` state ফোল্ডার থাকে। একটি তৈরি করুন:

```bash
mkdir my-notes && cd my-notes
veles init my-notes
```

এটি তৈরি করে `AGENTS.md` (আপনার প্রজেক্ট context), `sources/` ও `wiki/` (ডিফল্ট [LLM-Wiki layout](../explanation/layout-packs-and-llm-wiki.md)), এবং `.veles/` (machine state)। দেখুন [project layout](../reference/project-layout.md)।

## ৪. আপনার প্রথম prompt চালানো

```bash
veles run "Read AGENTS.md and describe this project in three sentences."
```

Veles আপনার প্রজেক্ট context লোড করে, model কল করে, এবং উত্তর প্রিন্ট করে। turn-টি প্রজেক্টের memory-তে সংরক্ষিত হয়।

token যেমন আসছে তেমন দেখতে `--stream` যোগ করুন, অথবা per-turn progress-এর জন্য `--verbose`:

```bash
veles run --stream "What files exist in this project right now?"
```

## ৫. ইন্টারঅ্যাক্টিভ REPL খোলা

বহু-turn কথোপকথনের জন্য TUI খুলুন:

```bash
veles tui
```

একটি বার্তা টাইপ করে Enter চাপুন। দরকারি কী: বের হতে `Ctrl+D`, [run mode](../explanation/modes.md) পরিবর্তন করতে `Shift+Tab`, slash কমান্ডের তালিকা দেখতে `/help`। সম্পূর্ণ তালিকা [TUI reference](../reference/tui.md)-এ।

## ৬. Veles যা মনে রাখে তা দেখা

প্রতিটি run সংরক্ষিত হয়। আপনার session তালিকাভুক্ত ও খুঁজুন:

```bash
veles sessions list
veles sessions search "three sentences"
```

## এরপর কোথায় যাবেন

- **[Building a knowledge base](building-a-knowledge-base.md)** — wiki-তে source ingest করুন এবং সেগুলো সম্পর্কে প্রশ্ন করুন।
- **[Configure providers](../how-to/configure-providers.md)** — Anthropic, OpenAI, Gemini, অথবা একটি সম্পূর্ণ লোকাল model-এ স্যুইচ করুন।
- **[Architecture overview](../explanation/architecture.md)** — Veles পর্দার আড়ালে কী করছে তা বুঝুন।

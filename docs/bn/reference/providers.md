# Providers

> 🌐 **Languages:** [English](../../en/reference/providers.md) · [Русский](../../ru/reference/providers.md) · **বাংলা**

Veles provider-নিরপেক্ষ। যেকোনো agent কমান্ডে `--provider <name>` পাস করুন, অথবা config-এ
একটি ডিফল্ট সেট করুন। Model ID গুলো সংশ্লিষ্ট provider-এর নিজস্ব নামকরণ অনুসরণ করে।

| Provider | Kind | API key | Notes |
|---|---|---|---|
| `openrouter` | Cloud gateway | `OPENROUTER_API_KEY` | **ডিফল্ট।** শত শত model relay করে; model ID যেমন `anthropic/claude-sonnet-4.6` |
| `anthropic` | Cloud direct | `ANTHROPIC_API_KEY` | Claude Messages API, prompt caching |
| `openai` | Cloud direct | `OPENAI_API_KEY` | GPT chat completions |
| `gemini` | Cloud direct | `GEMINI_API_KEY` / `GOOGLE_API_KEY` | Google Gemini |
| `claude-cli` | Subprocess | — (CLI session) | একটি লোকাল `claude` CLI-কে JSON-stream মোডে delegate করে |
| `gemini-cli` | Subprocess | — (CLI session) | একটি লোকাল `gemini` CLI-কে delegate করে |
| `ollama` | Local | none | `OLLAMA_BASE_URL` (ডিফল্ট `http://localhost:11434/v1`) |
| `llamacpp` | Local | none | `LLAMACPP_BASE_URL` (ডিফল্ট `http://localhost:8080/v1`) |
| `openai-compat` | Local/custom | none | `OPENAI_COMPAT_BASE_URL` (আবশ্যক, কোনো ডিফল্ট নেই) |

ডিফল্ট: provider `openrouter`, model `anthropic/claude-sonnet-4.6`, compressor
`anthropic/claude-haiku-4.5`।

## লোকাল provider

`ollama`, `llamacpp`, এবং `openai-compat`-এর কোনো API key লাগে না। ইনস্টল করা model-গুলোর
তালিকা পেতে `veles models <provider>` চালান (লোকাল provider-এর ক্ষেত্রে সবসময় লাইভ)।

লোকাল provider-গুলোতে **tool calling ডিফল্টভাবে বন্ধ** — অনেক লোকাল model
ত্রুটিপূর্ণ tool call তৈরি করে। একটি tool-সক্ষম model বেছে নেওয়ার পর এটি চালু করুন:

```bash
export VELES_LOCAL_TOOLS=1
veles run --provider ollama --model qwen3:4b-instruct "..."
```

`*_BASE_URL` env var দিয়ে endpoint override করুন (দেখুন
[environment variables](environment-variables.md))।

## CLI delegation (`claude-cli`, `gemini-cli`)

আপনার কাছে যদি Claude বা Gemini CLI সাবস্ক্রিপশন থাকে, Veles সেই binary-কে
JSON-streaming মোডে চালিয়ে coordinator হিসেবে কাজ করতে পারে — আলাদা কোনো API key ছাড়াই
লুপটিকে local-first রেখে। MCP bridge কনফিগার করা থাকলেই কেবল Veles-এর tool-গুলো subprocess-এ পৌঁছায়।

## Multimodal status (vision / speech-to-text)

Veles একটি `VisionAdapter` ও একটি STT adapter protocol সংজ্ঞায়িত করে (`modules/vision.py`,
`modules/stt.py`) সাথে একটি process-global registry, **কিন্তু কোনো concrete adapter
ship করে না এবং daemon startup-এ কোনোটি register-ও হয় না**। তাই channel-এ পাঠানো কোনো
ছবি বা ভয়েস মেসেজ বর্তমানে বিশ্লেষিত হওয়ার বদলে একটি "not configured" বার্তা ফেরত দেয়।
কোনো adapter wire করা হলে ব্যবহারের জন্য `vision` routing task-টি বিদ্যমান। দেখুন
[connect Telegram](../how-to/connect-telegram.md#multimodal-limitation)।

## একটি model বেছে নেওয়া

```bash
veles models openrouter            # cached 24h
veles models openrouter --refresh  # bypass cache
veles models ollama                # always live
```

বিভিন্ন কাজের জন্য বিভিন্ন model ব্যবহার করতে (compression-এর জন্য সস্তা, planning-এর জন্য শক্তিশালী),
দেখুন [per-task routing](../how-to/per-task-routing.md)।

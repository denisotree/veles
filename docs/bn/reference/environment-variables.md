# এনভায়রনমেন্ট ভ্যারিয়েবল

> 🌐 **ভাষা:** [English](../../en/reference/environment-variables.md) · [简体中文](../../zh-CN/reference/environment-variables.md) · [繁體中文](../../zh-TW/reference/environment-variables.md) · [日本語](../../ja/reference/environment-variables.md) · [한국어](../../ko/reference/environment-variables.md) · [Español](../../es/reference/environment-variables.md) · [Français](../../fr/reference/environment-variables.md) · [Italiano](../../it/reference/environment-variables.md) · [Português (BR)](../../pt-BR/reference/environment-variables.md) · [Português (PT)](../../pt-PT/reference/environment-variables.md) · [Русский](../../ru/reference/environment-variables.md) · [العربية](../../ar/reference/environment-variables.md) · [हिन्दी](../../hi/reference/environment-variables.md) · **বাংলা** · [Tiếng Việt](../../vi/reference/environment-variables.md)

Veles রানটাইমে এগুলো পড়ে। API কী ও টোকেন OS keychain-এ রাখাই সবচেয়ে ভালো
(`veles secret set …`); env ভ্যারিয়েবল হলো ফলব্যাক ও ওভাররাইড।

## প্রোভাইডার API কী

API-কী লুকআপ ক্যাসকেড: OS keychain (project scope) → OS keychain (default scope)
→ এনভায়রনমেন্ট ভ্যারিয়েবল।

| ভ্যারিয়েবল | প্রোভাইডার | নোট |
|---|---|---|
| `OPENROUTER_API_KEY` | openrouter | ডিফল্ট প্রোভাইডার |
| `ANTHROPIC_API_KEY` | anthropic | সরাসরি Anthropic API |
| `OPENAI_API_KEY` | openai | সরাসরি OpenAI API |
| `GEMINI_API_KEY` | gemini | Google Gemini-এর প্রাইমারি কী |
| `GOOGLE_API_KEY` | gemini | Google Gemini-এর ফলব্যাক |

`claude-cli` এবং `gemini-cli` তাদের নিজস্ব বাইনারির মাধ্যমে অথেনটিকেট করে — কোনো env var লাগে না।

## লোকাল প্রোভাইডার

| ভ্যারিয়েবল | ডিফল্ট | উদ্দেশ্য |
|---|---|---|
| `OLLAMA_BASE_URL` | `http://localhost:11434/v1` | Ollama এন্ডপয়েন্ট |
| `OLLAMA_HOST` | follows `OLLAMA_BASE_URL` | embeddings-এর জন্য Ollama host |
| `LLAMACPP_BASE_URL` | `http://localhost:8080/v1` | llama.cpp সার্ভার এন্ডপয়েন্ট |
| `OPENAI_COMPAT_BASE_URL` | — (required) | `openai-compat` প্রোভাইডারের জন্য এন্ডপয়েন্ট |
| `VELES_LOCAL_TOOLS` | off | লোকাল প্রোভাইডারে টুল কলিং সক্রিয় করে (`1`/`true`) |
| `VELES_OLLAMA_EMBED_MODEL` | provider default | Ollama embedding মডেল ওভাররাইড করে |

## চ্যানেল ও ডিমন

| ভ্যারিয়েবল | ডিফল্ট | উদ্দেশ্য |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | — | `veles channel run --channel telegram`-এর জন্য Telegram বট টোকেন |
| `VELES_DAEMON_URL` | `http://127.0.0.1:8765` | চ্যানেল গেটওয়ে দ্বারা ব্যবহৃত ডিমন বেস URL |
| `VELES_DAEMON_TOKEN` | — | ডিমন অথেনটিকেশনের জন্য Bearer টোকেন |

## পাথ ও locale

| ভ্যারিয়েবল | ডিফল্ট | উদ্দেশ্য |
|---|---|---|
| `VELES_USER_HOME` | `~` | যে home `~/.veles/` ধারণ করে তা ওভাররাইড করে (state, cache, keychain index) |
| `VELES_HOME` | — | `VELES_USER_HOME`-এর লেগ্যাসি অ্যালিয়াস |
| `VELES_REGISTRY_PATH` | `~/.veles/…` | মাল্টি-প্রজেক্ট রেজিস্ট্রি পাথ ওভাররাইড করে |
| `VELES_LOCALE` | `[user] language` or `en` | একটি রানের জন্য সক্রিয় UI locale ওভাররাইড করে |
| `VELES_LOG_LEVEL` | `INFO` | ডিমন/লগ ভার্বোসিটি (`DEBUG`/`INFO`/`WARNING`/`ERROR`) |
| `VELES_CONFIG_FILENAME` | `config.toml` | কনফিগ ফাইলনেম ওভাররাইড করে (টেস্টিং) |

## আচরণ ও ফিচার ফ্ল্যাগ

| ভ্যারিয়েবল | ডিফল্ট | উদ্দেশ্য |
|---|---|---|
| `VELES_NO_WIZARD` | off | প্রথম-রানের উইজার্ড এড়িয়ে যায় (একটি TTY-ও দরকার) |
| `VELES_MANAGER_MODE` | off | `veles run`-এর জন্য মাল্টি-এজেন্ট ম্যানেজার বাধ্য করে (`1` on / `0` kill switch) |
| `VELES_VERIFY_MODE` | off | `veles run`-এর জন্য verify→escalate পাস বাধ্য করে (`1` on / `0` kill switch) |
| `VELES_FENCED_TOOLS` | off | fenced/sandboxed এক্সিকিউশন পাথে tools চালায় |
| `VELES_TRUST_AUTO_ALLOW` | off | trust ladder বাইপাস করে (CI / autopilot / প্রি-অথরাইজড সাব-এজেন্ট) |
| `VELES_SANDBOX_ROOTS` | project + `~/.veles` | read/write স্যান্ডবক্স রুটের `:`-সেপারেটেড ওভাররাইড |
| `VELES_FETCH_ALLOW_PRIVATE` | off | tools-কে RFC-1918 / প্রাইভেট ঠিকানা ফেচ করতে দেয় |
| `VELES_MEMORY_RERANK` | on | মেমরি রিকলের ভেক্টর রির‍্যাঙ্কিং (`0`/`false` নিষ্ক্রিয় করে) |
| `VELES_WEB_SEARCH_BACKEND` | auto | `research` এবং `web_search`-এর জন্য ওয়েব সার্চ ব্যাকএন্ড |

## রেজিস্ট্রি

| ভ্যারিয়েবল | উদ্দেশ্য |
|---|---|
| `VELES_SKILLS_REGISTRY_URL` | `veles browse skills`-এর সোর্স |
| `VELES_MODULES_REGISTRY_URL` | `veles browse modules`-এর সোর্স |

## ইন্টারনাল / টেস্টিং

`VELES_BUNDLE_VERSION`, `VELES_CACHE_BREAKPOINT` — ইন্টারনাল; এগুলো সেট করার
আপনার প্রয়োজন হওয়ার কথা নয়।

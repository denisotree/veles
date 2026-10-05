# Providers कैसे configure करें

> 🌐 **भाषाएँ:** [English](../../en/how-to/configure-providers.md) · [简体中文](../../zh-CN/how-to/configure-providers.md) · [繁體中文](../../zh-TW/how-to/configure-providers.md) · [日本語](../../ja/how-to/configure-providers.md) · [한국어](../../ko/how-to/configure-providers.md) · [Español](../../es/how-to/configure-providers.md) · [Français](../../fr/how-to/configure-providers.md) · [Italiano](../../it/how-to/configure-providers.md) · [Português (BR)](../../pt-BR/how-to/configure-providers.md) · [Português (PT)](../../pt-PT/how-to/configure-providers.md) · [Русский](../../ru/how-to/configure-providers.md) · [العربية](../../ar/how-to/configure-providers.md) · **हिन्दी** · [বাংলা](../../bn/how-to/configure-providers.md) · [Tiếng Việt](../../vi/how-to/configure-providers.md)

Veles को OpenRouter, Anthropic, OpenAI, Gemini, local models, या एक CLI subscription
के बीच switch करें। पूरी provider सूची: [providers संदर्भ](../reference/providers.md)।

## प्रति command एक provider चुनें

```bash
veles run --provider anthropic --model claude-sonnet-4.6 "..."
veles run --provider openai     --model gpt-4o            "..."
veles run --provider gemini     --model gemini-2.5-pro    "..."
```

## प्रोजेक्ट के लिए एक default set करें

`<project>/.veles/config.toml` में एक base डालें:

```toml
[engine]
provider = "openrouter"                 # provider name
model = "anthropic/claude-sonnet-4.6"  # model id
```

या `~/.veles/config.toml` में एक user-global default:

```toml
[user]
default_provider = "openrouter"
default_model = "anthropic/claude-sonnet-4.6"
```

## API key प्रदान करें

Cloud providers को एक key चाहिए। इसे OS keychain में एक बार संग्रहित करें:

```bash
veles secret set OPENROUTER_API_KEY
veles secret set ANTHROPIC_API_KEY
```

…या [environment variable](../reference/environment-variables.md) export करें:

```bash
export OPENROUTER_API_KEY=sk-or-v1-...
```

Lookup क्रम: keychain (project scope) → keychain (default) → env var। Keys config
files में **कभी** नहीं लिखे जाते।

## एक पूरी तरह local model का उपयोग करें (बिना key)

[Ollama](https://ollama.com) install करें, एक model pull करें, और Veles को उस पर इंगित करें:

```bash
ollama pull qwen3:4b-instruct
veles models ollama                     # confirm it's listed
veles run --provider ollama --model qwen3:4b-instruct "Hello"
```

Tool calling server जो advertise करता है उससे **detect** होती है। इसे जबरन on करने के लिए
`VELES_LOCAL_TOOLS=1` दें (या off के लिए `=0`)।

यदि आपका server default port पर नहीं है तो endpoints override करें:

```bash
export OLLAMA_BASE_URL=http://localhost:11434/v1
export LLAMACPP_BASE_URL=http://localhost:8080/v1
export OPENAI_COMPAT_BASE_URL=http://my-host:8000/v1   # required for openai-compat
```

## अपना provider जोड़ें

कोई भी hosted OpenAI-compatible API, या आपका चलाया हुआ server, `~/.veles/providers.toml` में
एक entry के साथ provider बन जाता है — कोई code नहीं। id table का नाम है:

```toml
[providers.groq]
kind = "openai-api"                          # a hosted API; needs a key
label = "Groq"                               # shown in the wizards (optional)
base_url = "https://api.groq.com/openai/v1"
key_env = ["GROQ_API_KEY"]

[providers.lmstudio]
kind = "local"                               # a server you run; a key is optional
base_url = "http://localhost:1234/v1"
```

फिर इसे किसी भी builtin की तरह उपयोग करें:

```bash
veles secret set GROQ_API_KEY      # into the keychain, where the groq entry reads it
veles models groq
veles run --provider groq --model llama-3.3-70b-versatile "..."
```

| Key | अर्थ |
|---|---|
| `kind` | `openai-api` (एक hosted API) या `local` (आपका चलाया हुआ server) |
| `base_url` | OpenAI-compatible endpoint, जो `/v1` (या provider के समकक्ष) पर समाप्त होता है |
| `base_url_env` | एक env var जो set होने पर `base_url` को override करता है |
| `key_env` | env var के नाम जिनसे key पढ़ी जाती है; keychain पहले आज़माया जाता है |
| `label`, `tagline` | wizards इसे कैसे दिखाते हैं |
| `tools` | `auto` (default), `on` या `off` — model को tool calls मिलें या नहीं |

builtin id वाली entry (`[providers.ollama]`) उस provider की settings बदलती है — जैसे उसका
`base_url` — पर उसका kind नहीं। टूटी हुई file की सूचना एक बार दी जाती है, और Veles
builtin providers के साथ आगे चलता है; `veles doctor` बताता है कि उसमें क्या गड़बड़ है।

आम APIs के लिए शुरुआती बिंदु — **Veles team द्वारा सत्यापित नहीं**, मौजूदा endpoint के लिए
provider का documentation देखें:

| id | `base_url` | `key_env` |
|---|---|---|
| `groq` | `https://api.groq.com/openai/v1` | `GROQ_API_KEY` |
| `deepseek` | `https://api.deepseek.com/v1` | `DEEPSEEK_API_KEY` |
| `mistral` | `https://api.mistral.ai/v1` | `MISTRAL_API_KEY` |
| `together` | `https://api.together.xyz/v1` | `TOGETHER_API_KEY` |
| `xai` | `https://api.x.ai/v1` | `XAI_API_KEY` |
| `fireworks` | `https://api.fireworks.ai/inference/v1` | `FIREWORKS_API_KEY` |
| `deepinfra` | `https://api.deepinfra.com/v1/openai` | `DEEPINFRA_API_KEY` |
| `nebius` | `https://api.studio.nebius.com/v1` | `NEBIUS_API_KEY` |
| `cerebras` | `https://api.cerebras.ai/v1` | `CEREBRAS_API_KEY` |
| `zai` | `https://api.z.ai/api/paas/v4` | `ZAI_API_KEY` |
| `moonshot` | `https://api.moonshot.ai/v1` | `MOONSHOT_API_KEY` |
| `lmstudio` (`local`) | `http://localhost:1234/v1` | — |
| `vllm` (`local`) | `http://localhost:8000/v1` | — |

## एक Claude / Google subscription को delegate करें

यदि आपके पास `claude` CLI authenticated है, तो Veles उसे चला सकता है:

```bash
veles run --provider claude-cli "..."
```

Google subscription के लिए, Antigravity CLI (`agy`) को install करें और एक बार log in करें,
फिर उसके provider का नाम दें — `antigravity-cli` module उसी run पर आपकी connected
registries से खुद install हो जाता है:

```bash
veles run --provider antigravity-cli --model gemini-3.8-flash-high "..."
veles models antigravity-cli
```

कोई API key नहीं चाहिए — CLI auth संभालता है।

## उपलब्ध models सूचीबद्ध करें

```bash
veles models openrouter            # cloud: cached 24h
veles models openrouter --refresh  # force re-fetch
veles models ollama                # local: always live
```

## आगे

- [विभिन्न tasks को विभिन्न models पर route करें](per-task-routing.md) — compression
  के लिए सस्ता model, planning के लिए मज़बूत model।

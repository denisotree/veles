# Providers

> 🌐 **भाषाएँ:** [English](../../en/reference/providers.md) · [简体中文](../../zh-CN/reference/providers.md) · [繁體中文](../../zh-TW/reference/providers.md) · [日本語](../../ja/reference/providers.md) · [한국어](../../ko/reference/providers.md) · [Español](../../es/reference/providers.md) · [Français](../../fr/reference/providers.md) · [Italiano](../../it/reference/providers.md) · [Português (BR)](../../pt-BR/reference/providers.md) · [Português (PT)](../../pt-PT/reference/providers.md) · [Русский](../../ru/reference/providers.md) · [العربية](../../ar/reference/providers.md) · **हिन्दी** · [বাংলা](../../bn/reference/providers.md) · [Tiếng Việt](../../vi/reference/providers.md)

Veles provider-agnostic है। किसी भी agent command को `--provider <name>` दें, या config
में एक default set करें। Model IDs provider के अपने naming का उपयोग करते हैं।

| Provider | प्रकार | API key | टिप्पणियाँ |
|---|---|---|---|
| `openrouter` | Cloud gateway | `OPENROUTER_API_KEY` | **Default.** सैकड़ों models रिले करता है; model IDs जैसे `anthropic/claude-sonnet-4.6` |
| `anthropic` | Cloud direct | `ANTHROPIC_API_KEY` | Claude Messages API, prompt caching |
| `openai` | Cloud direct | `OPENAI_API_KEY` | GPT chat completions |
| `gemini` | Cloud direct | `GEMINI_API_KEY` / `GOOGLE_API_KEY` | Google Gemini |
| `claude-cli` | Subprocess | — (CLI session) | JSON-stream mode में एक local `claude` CLI को delegate करता है |
| `gemini-cli` | Subprocess | — (CLI session) | एक local `gemini` CLI को delegate करता है |
| `ollama` | Local | none | `OLLAMA_BASE_URL` (default `http://localhost:11434/v1`) |
| `llamacpp` | Local | none | `LLAMACPP_BASE_URL` (default `http://localhost:8080/v1`) |
| `openai-compat` | Local/custom | none | `OPENAI_COMPAT_BASE_URL` (आवश्यक, कोई default नहीं) |

Default provider: `openrouter`। कोई **hardcoded default model नहीं है** — इसे setup
wizard, `[provider] model`, या `--model` के ज़रिए set करें (अन्यथा agent "no model
configured" बताता है)। प्रति-task routes अपने base के रूप में `[provider]` को inherit
करते हैं जब तक कि `[routing.tasks]` में override न किया जाए — देखें
[per-task routing](../how-to/per-task-routing.md)।

## Local providers

`ollama`, `llamacpp`, और `openai-compat` को कोई API key नहीं चाहिए। installed models
को `veles models <provider>` से सूचीबद्ध करें (local providers के लिए हमेशा live)।

local providers पर **tool calling default रूप से off है** — कई local models विकृत
tool calls उत्पन्न करते हैं। जब आप एक tool-सक्षम model चुन लें तो इसे सक्षम करें:

```bash
export VELES_LOCAL_TOOLS=1
veles run --provider ollama --model qwen3:4b-instruct "..."
```

`*_BASE_URL` env vars से endpoints override करें (देखें
[environment variables](environment-variables.md))।

## CLI delegation (`claude-cli`, `gemini-cli`)

यदि आपके पास Claude या Gemini CLI subscription है, तो Veles उस binary को
JSON-streaming mode में चला सकता है और coordinator की तरह काम कर सकता है — loop को
एक अलग API key के बिना local-first रखते हुए। Veles tools subprocess तक केवल तब पहुँचते
हैं जब एक MCP bridge configured हो।

## Multimodal status (vision / speech-to-text)

Veles एक `VisionAdapter` और एक STT adapter protocol (`modules/vision.py`,
`modules/stt.py`) के साथ एक process-global registry परिभाषित करता है, **लेकिन कोई
concrete adapter ship नहीं होता और daemon startup पर कोई इसे register नहीं करता**।
इसलिए किसी channel को भेजी गई photo या voice message का विश्लेषण होने के बजाय फिलहाल
"not configured" notice लौटता है। `vision` routing task तब के लिए मौजूद है जब एक
adapter wire किया जाए। देखें
[Telegram जोड़ें](../how-to/connect-telegram.md#multimodal-limitation)।

## एक model चुनना

```bash
veles models openrouter            # cached 24h
veles models openrouter --refresh  # bypass cache
veles models ollama                # always live
```

विभिन्न jobs के लिए विभिन्न models का उपयोग करने हेतु (compression के लिए सस्ता,
planning के लिए मज़बूत), देखें [per-task routing](../how-to/per-task-routing.md)।

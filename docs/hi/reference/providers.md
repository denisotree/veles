# Providers

> 🌐 **भाषाएँ:** **English** · [Русский](../../ru/reference/providers.md)

Veles provider-agnostic है। किसी भी agent command को `--provider <name>` पास करें, या
config में एक default सेट करें। Model IDs provider के अपने naming का उपयोग करते हैं।

| Provider | Kind | API key | Notes |
|---|---|---|---|
| `openrouter` | Cloud gateway | `OPENROUTER_API_KEY` | **Default.** Relays hundreds of models; model IDs like `anthropic/claude-sonnet-4.6` |
| `anthropic` | Cloud direct | `ANTHROPIC_API_KEY` | Claude Messages API, prompt caching |
| `openai` | Cloud direct | `OPENAI_API_KEY` | GPT chat completions |
| `gemini` | Cloud direct | `GEMINI_API_KEY` / `GOOGLE_API_KEY` | Google Gemini |
| `claude-cli` | Subprocess | — (CLI session) | Delegates to a local `claude` CLI in JSON-stream mode |
| `gemini-cli` | Subprocess | — (CLI session) | Delegates to a local `gemini` CLI |
| `ollama` | Local | none | `OLLAMA_BASE_URL` (default `http://localhost:11434/v1`) |
| `llamacpp` | Local | none | `LLAMACPP_BASE_URL` (default `http://localhost:8080/v1`) |
| `openai-compat` | Local/custom | none | `OPENAI_COMPAT_BASE_URL` (required, no default) |

Defaults: provider `openrouter`, model `anthropic/claude-sonnet-4.6`, compressor
`anthropic/claude-haiku-4.5`।

## Local providers

`ollama`, `llamacpp`, और `openai-compat` को किसी API key की ज़रूरत नहीं है। इंस्टॉल किए गए
models की सूची `veles models <provider>` से देखें (local providers के लिए हमेशा live)।

**Local providers पर tool calling by default बंद होती है** — कई local models malformed
tool calls देते हैं। एक बार tool-capable model चुन लेने के बाद इसे enable करें:

```bash
export VELES_LOCAL_TOOLS=1
veles run --provider ollama --model qwen3:4b-instruct "..."
```

Endpoints को `*_BASE_URL` env vars से override करें (देखें
[environment variables](environment-variables.md))।

## CLI delegation (`claude-cli`, `gemini-cli`)

अगर आपके पास Claude या Gemini CLI subscription है, तो Veles binary को
JSON-streaming mode में चला सकता है और coordinator की तरह काम कर सकता है — बिना किसी
अलग API key के loop को local-first रखते हुए। Veles tools subprocess तक तभी पहुँचते हैं
जब कोई MCP bridge कॉन्फ़िगर किया गया हो।

## Multimodal status (vision / speech-to-text)

Veles एक `VisionAdapter` और एक STT adapter protocol (`modules/vision.py`,
`modules/stt.py`) तथा एक process-global registry परिभाषित करता है, **लेकिन कोई concrete
adapter ship नहीं होता और daemon startup पर कोई इसे register नहीं करता**। इसलिए किसी channel
को भेजी गई photo या voice message अभी analyse होने के बजाय "not configured" notice लौटाती है।
`vision` routing task तब के लिए मौजूद है जब कोई adapter wire किया जाए। देखें
[connect Telegram](../how-to/connect-telegram.md#multimodal-limitation)।

## एक model चुनना

```bash
veles models openrouter            # cached 24h
veles models openrouter --refresh  # bypass cache
veles models ollama                # always live
```

अलग-अलग jobs के लिए अलग models उपयोग करने के लिए (compression के लिए सस्ता, planning के
लिए मज़बूत), देखें [per-task routing](../how-to/per-task-routing.md)।

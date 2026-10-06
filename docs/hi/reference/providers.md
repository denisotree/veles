# Providers

> 🌐 **भाषाएँ:** [English](../../en/reference/providers.md) · [简体中文](../../zh-CN/reference/providers.md) · [繁體中文](../../zh-TW/reference/providers.md) · [日本語](../../ja/reference/providers.md) · [한국어](../../ko/reference/providers.md) · [Español](../../es/reference/providers.md) · [Français](../../fr/reference/providers.md) · [Italiano](../../it/reference/providers.md) · [Português (BR)](../../pt-BR/reference/providers.md) · [Português (PT)](../../pt-PT/reference/providers.md) · [Русский](../../ru/reference/providers.md) · [العربية](../../ar/reference/providers.md) · **हिन्दी** · [বাংলা](../../bn/reference/providers.md) · [Tiếng Việt](../../vi/reference/providers.md)

Veles provider-agnostic है। किसी भी agent command को `--provider <id>` दें, या config
में एक default set करें। Model IDs provider के अपने naming का उपयोग करते हैं।

## Provider catalogue

Veles जो भी provider जानता है, वह एक ही catalogue की एक entry है, जो तीन sources से बनता है:

1. **Builtin** — नीचे की तालिका, जो Veles के साथ आती है।
2. **आपके अपने** — `~/.veles/providers.toml`: एक entry जोड़कर कोई hosted
   OpenAI-compatible API या आपका चलाया हुआ server (देखें
   [अपना provider जोड़ें](../how-to/configure-providers.md#अपना-provider-जोड़ें))।
   builtin id वाली entry उस provider की settings को override करती है (जैसे उसका `base_url`)।
3. **Modules** — एक registry module कोई provider देता है (`antigravity-cli`)। उसका
   नाम `[engine] provider`, किसी route या `--provider` में देने पर वह अगले run में आपकी
   connected registries से install हो जाता है, ठीक declared channel की तरह।

`--provider`, `veles models`, setup wizards, routing और `veles doctor` सब catalogue
पढ़ते हैं, इसलिए किसी भी source का provider हर उस जगह काम करता है जहाँ builtin करता है।
अज्ञात id एक पंक्ति की error है जो बताती है कि क्या-क्या मौजूद है; `veles doctor`
`~/.veles/providers.toml` और आपके routes में नामित हर provider की भी जाँच करता है।

| Provider | प्रकार | API key | टिप्पणियाँ |
|---|---|---|---|
| `openrouter` | Cloud gateway | `OPENROUTER_API_KEY` | **Default.** सैकड़ों models रिले करता है; model IDs जैसे `anthropic/claude-sonnet-4.6` |
| `anthropic` | Cloud direct | `ANTHROPIC_API_KEY` | Claude Messages API, prompt caching |
| `openai` | Cloud direct | `OPENAI_API_KEY` | GPT chat completions |
| `gemini` | Cloud direct | `GEMINI_API_KEY` / `GOOGLE_API_KEY` | Google Gemini |
| `claude-cli` | CLI delegate | — (CLI session) | JSON-stream mode में एक local `claude` CLI को delegate करता है |
| `codex` | CLI delegate | — (CLI session) | एक local `codex` CLI को delegate करता है (ChatGPT subscription) |
| `ollama` | Local | none | `OLLAMA_BASE_URL` (default `http://localhost:11434/v1`) |
| `llamacpp` | Local | none | `LLAMACPP_BASE_URL` (default `http://localhost:8080/v1`) |
| `openai-compat` | Local/custom | optional `OPENAI_COMPAT_API_KEY` | `OPENAI_COMPAT_BASE_URL` (आवश्यक, कोई default नहीं) |

`gemini-cli` को 1.2.6 में हटा दिया गया — Google अब personal accounts को Gemini CLI नहीं
देता। API key के साथ `gemini` का उपयोग करें, या `antigravity-cli` module का।

Default provider: `openrouter`। कोई **hardcoded default model नहीं है** — इसे setup
wizard, `[engine] model`, या `--model` के ज़रिए set करें (अन्यथा agent "no model
configured" बताता है)। प्रति-task routes अपने base के रूप में `[engine]` को inherit
करते हैं जब तक कि `[routing.tasks]` में override न किया जाए — देखें
[per-task routing](../how-to/per-task-routing.md)।

## Local providers

`ollama`, `llamacpp`, और `openai-compat` को कोई API key नहीं चाहिए। installed models
को `veles models <provider>` से सूचीबद्ध करें (local providers के लिए हमेशा live)।

**Tool calling का पता चलता है** (detect होती है) उससे जो backend advertise करता है: ollama हर
model की capabilities बताता है, llama.cpp server अपने chat template की। `VELES_LOCAL_TOOLS=1`
tool calling को जबरन on करता है, `=0` off; unset होने पर detect होती है।

```bash
veles run --provider ollama --model qwen3:4b-instruct "..."
```

`*_BASE_URL` env vars से endpoints override करें (देखें
[environment variables](environment-variables.md))।

## CLI delegation (`claude-cli`, `codex`, `antigravity-cli`)

यदि आपके पास Claude, ChatGPT या Google subscription है, तो Veles उसकी CLI को headless चला सकता है
और coordinator की तरह काम कर सकता है — एक अलग API key के बिना। `claude-cli` और `codex` builtin हैं;
`antigravity-cli` (`agy` CLI) एक registry module है जो नाम देने पर खुद install हो जाता है।

Delegate केवल model है: Veles के tools उस तक एक MCP bridge के ज़रिए पहुँचते हैं, और हर
call Veles की trust ladder से गुज़रती है। Bridge का config चल रहे process की एक directory में
रहता है, `.veles/tmp/delegate-<pid>/`, जो process के exit होने पर हट जाती है। `agy` आपके
project के बाहर (`~/.veles/tmp/` के अंतर्गत) एक scratch workspace में चलता है, इसलिए project का
अपना `.agents/` config उस तक कभी नहीं पहुँचता, एक ऐसे gate के पीछे जो उसके अपने shell और
file tools को deny करता है।

`codex` भी आपके project के बाहर (`~/.veles/tmp/` के अंतर्गत) चलता है, आपका codex config अनदेखा
करके और उसके अपने tools — shell, file edits, images, subagents, browser, web search — बंद
करके; Veles उन flag नामों को प्रति process एक बार जाँचता है और ऐसा codex चलाने से मना कर देता है
जिसने अपने इस्तेमाल का कोई flag rename कर दिया हो। उसका MCP server file के बजाय arguments में
दिया जाता है। `veles run` में, codex Veles के tool protocol का पालन claude से कम भरोसेमंद ढंग से
करता है: वह tool को call किए बिना ही जवाब दे सकता है कि वह file नहीं पढ़ सकता — दोबारा पूछें,
या tool का नाम बताएँ ("use read_file on …")।

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

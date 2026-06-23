# शुरुआत करना

> 🌐 **भाषाएँ:** **English** · [Русский](../../ru/tutorials/getting-started.md)

इस tutorial में आप Veles इंस्टॉल करेंगे, उसे एक API key देंगे, अपना पहला project बनाएँगे,
और अपना पहला prompt चलाएँगे। लगभग 10 मिनट। अंत में आपके पास एक काम करता हुआ Veles project
होगा जिससे आप बात कर सकते हैं।

## आवश्यकताएँ

- **Python 3.13+** (Veles को `>=3.13` चाहिए)।
- एक LLM API key। हम **OpenRouter** (default provider) उपयोग करेंगे; कोई भी
  [other providers](../reference/providers.md) भी चलता है, जिनमें बिना key वाले पूरी तरह
  local providers भी शामिल हैं।

## 1. Install

Veles [uv](https://docs.astral.sh/uv/) के ज़रिए एक global `veles` command के रूप में
इंस्टॉल होता है:

```bash
# install uv if you don't have it
curl -LsSf https://astral.sh/uv/install.sh | sh

# from the Veles source directory
uv tool install .

# verify
veles --help
```

बाद में update करने के लिए: `uv tool install . --reinstall`।

## 2. Veles को एक API key दें

[openrouter.ai](https://openrouter.ai) से एक key लें और उसे export करें:

```bash
export OPENROUTER_API_KEY=sk-or-v1-...
```

आप इसे OS keychain में भी स्टोर कर सकते हैं ताकि हर shell में दोबारा export न करना पड़े:

```bash
veles secret set OPENROUTER_API_KEY
```

(बिना key वाला पूरी तरह local setup पसंद है? [Ollama](https://ollama.com) इंस्टॉल करें,
`ollama pull qwen3:4b-instruct`, और नीचे `--provider ollama` उपयोग करें।)

## 3. अपना पहला project बनाएँ

एक Veles project बस एक डायरेक्टरी है जिसमें `.veles/` state folder होता है। एक बनाएँ:

```bash
mkdir my-notes && cd my-notes
veles init my-notes
```

यह `AGENTS.md` (आपका project context), `sources/` और `wiki/` (default
[LLM-Wiki layout](../explanation/layout-packs-and-llm-wiki.md)), और `.veles/`
(machine state) बनाता है। देखें [project layout](../reference/project-layout.md)।

## 4. अपना पहला prompt चलाएँ

```bash
veles run "Read AGENTS.md and describe this project in three sentences."
```

Veles आपका project context load करता है, model को call करता है, और जवाब प्रिंट करता है।
यह turn project की memory में सेव हो जाता है।

tokens को आते ही देखने के लिए `--stream` जोड़ें, या per-turn progress के लिए `--verbose`:

```bash
veles run --stream "What files exist in this project right now?"
```

## 5. interactive REPL खोलें

multi-turn बातचीत के लिए, TUI खोलें:

```bash
veles tui
```

एक message टाइप करें और Enter दबाएँ। उपयोगी keys: exit के लिए `Ctrl+D`,
[run modes](../explanation/modes.md) cycle करने के लिए `Shift+Tab`, slash commands की सूची
के लिए `/help`। पूरी सूची [TUI reference](../reference/tui.md) में है।

## 6. देखें Veles क्या याद रखता है

हर run सेव होता है। अपनी sessions की सूची देखें और search करें:

```bash
veles sessions list
veles sessions search "three sentences"
```

## आगे कहाँ जाएँ

- **[Building a knowledge base](building-a-knowledge-base.md)** — sources को wiki में
  ingest करें और उनके बारे में सवाल पूछें।
- **[Configure providers](../how-to/configure-providers.md)** — Anthropic, OpenAI,
  Gemini, या पूरी तरह local model पर स्विच करें।
- **[Architecture overview](../explanation/architecture.md)** — समझें कि Veles अंदर
  क्या कर रहा है।

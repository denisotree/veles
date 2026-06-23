# शुरुआत करना

> 🌐 **भाषाएँ:** [English](../../en/tutorials/getting-started.md) · [简体中文](../../zh-CN/tutorials/getting-started.md) · [繁體中文](../../zh-TW/tutorials/getting-started.md) · [日本語](../../ja/tutorials/getting-started.md) · [한국어](../../ko/tutorials/getting-started.md) · [Español](../../es/tutorials/getting-started.md) · [Français](../../fr/tutorials/getting-started.md) · [Italiano](../../it/tutorials/getting-started.md) · [Português (BR)](../../pt-BR/tutorials/getting-started.md) · [Português (PT)](../../pt-PT/tutorials/getting-started.md) · [Русский](../../ru/tutorials/getting-started.md) · [العربية](../../ar/tutorials/getting-started.md) · **हिन्दी** · [বাংলা](../../bn/tutorials/getting-started.md) · [Tiếng Việt](../../vi/tutorials/getting-started.md)

इस tutorial में आप Veles install करेंगे, उसे एक API key देंगे, अपना पहला प्रोजेक्ट
बनाएँगे, और अपना पहला prompt चलाएँगे। लगभग 10 मिनट। अंत में आपके पास एक working Veles
प्रोजेक्ट होगा जिससे आप बात कर सकते हैं।

## पूर्वापेक्षाएँ

- **Python 3.13+** (Veles को `>=3.13` चाहिए)।
- एक LLM API key। हम **OpenRouter** (default provider) का उपयोग करेंगे; कोई भी
  [अन्य provider](../reference/providers.md) भी काम करता है, जिसमें बिना key वाले
  पूरी तरह local providers भी शामिल हैं।

## 1. Install

Veles [uv](https://docs.astral.sh/uv/) के ज़रिए एक global `veles` command के रूप में install होता है:

```bash
# install uv if you don't have it
curl -LsSf https://astral.sh/uv/install.sh | sh

# install veles (published as `veles-ai`; the command is `veles`)
uv tool install veles-ai
# …or from a source checkout: uv tool install .

# verify
veles --help
```

बाद में अपडेट करने के लिए: `uv tool upgrade veles-ai`।

## 2. Veles को एक API key दें

[openrouter.ai](https://openrouter.ai) से एक key लें और उसे export करें:

```bash
export OPENROUTER_API_KEY=sk-or-v1-...
```

आप इसे OS keychain में भी संग्रहित कर सकते हैं ताकि हर shell में दोबारा export न करना पड़े:

```bash
veles secret set OPENROUTER_API_KEY
```

(बिना key वाला पूरी तरह local setup पसंद है? [Ollama](https://ollama.com) install करें,
`ollama pull qwen3:4b-instruct` चलाएँ, और नीचे `--provider ollama` का उपयोग करें।)

## 3. अपना पहला प्रोजेक्ट बनाएँ

एक Veles प्रोजेक्ट बस एक `.veles/` state folder वाली directory है। एक बनाएँ:

```bash
mkdir my-notes && cd my-notes
veles init my-notes
```

यह `AGENTS.md` (आपका प्रोजेक्ट context), `sources/` और `wiki/` (default
[LLM-Wiki layout](../explanation/layout-packs-and-llm-wiki.md)), तथा `.veles/`
(machine state) बनाता है। देखें [project layout](../reference/project-layout.md)।

## 4. अपना पहला prompt चलाएँ

```bash
veles run "Read AGENTS.md and describe this project in three sentences."
```

Veles आपका प्रोजेक्ट context load करता है, model को call करता है, और उत्तर प्रिंट करता
है। यह turn प्रोजेक्ट की memory में सहेजा जाता है।

tokens को आते ही देखने के लिए `--stream` जोड़ें, या प्रति-turn प्रगति के लिए `--verbose`:

```bash
veles run --stream "What files exist in this project right now?"
```

## 5. interactive REPL खोलें

multi-turn बातचीत के लिए, TUI खोलें:

```bash
veles tui
```

एक message टाइप करें और Enter दबाएँ। उपयोगी keys: बाहर निकलने के लिए `Ctrl+D`,
[run modes](../explanation/modes.md) के बीच घूमने के लिए `Shift+Tab`, slash commands
सूचीबद्ध करने के लिए `/help`। पूरी सूची [TUI संदर्भ](../reference/tui.md) में।

## 6. देखें कि Veles क्या याद रखता है

हर run सहेजा जाता है। अपनी sessions सूचीबद्ध करें और खोजें:

```bash
veles sessions list
veles sessions search "three sentences"
```

## आगे कहाँ जाएँ

- **[Building a knowledge base](building-a-knowledge-base.md)** — sources को wiki में
  ingest करें और उनके बारे में सवाल पूछें।
- **[Configure providers](../how-to/configure-providers.md)** — Anthropic,
  OpenAI, Gemini, या एक पूरी तरह local model पर switch करें।
- **[Architecture overview](../explanation/architecture.md)** — समझें कि Veles
  परदे के पीछे क्या कर रहा है।

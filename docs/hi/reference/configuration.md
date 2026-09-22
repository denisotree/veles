# Configuration संदर्भ

> 🌐 **भाषाएँ:** [English](../../en/reference/configuration.md) · [简体中文](../../zh-CN/reference/configuration.md) · [繁體中文](../../zh-TW/reference/configuration.md) · [日本語](../../ja/reference/configuration.md) · [한국어](../../ko/reference/configuration.md) · [Español](../../es/reference/configuration.md) · [Français](../../fr/reference/configuration.md) · [Italiano](../../it/reference/configuration.md) · [Português (BR)](../../pt-BR/reference/configuration.md) · [Português (PT)](../../pt-PT/reference/configuration.md) · [Русский](../../ru/reference/configuration.md) · [العربية](../../ar/reference/configuration.md) · **हिन्दी** · [বাংলা](../../bn/reference/configuration.md) · [Tiếng Việt](../../vi/reference/configuration.md)

Veles को दो TOML files और कुछ state directories के ज़रिए configure किया जाता है।
Secrets (API keys, bot tokens) इन files में **कभी** नहीं लिखे जाते — वे OS keychain
या environment variables में रहते हैं (देखें [environment variables](environment-variables.md))।

## State कहाँ रहती है

| Path | Scope | सामग्री |
|---|---|---|
| `~/.veles/` | User-global | `config.toml`, trust grants, cross-project skills/tools, model cache, locales, registry |
| `<project>/.veles/` | Project-local | `project.toml`, `config.toml`, `memory.db`, project skills/tools, plans, runtime artefacts |
| `<project>/AGENTS.md` | Project | agent में inject होने वाली context file (`CLAUDE.md` / `GEMINI.md` से symlinked) |
| `<project>/wiki/`, `sources/` | Project | user content (default LLM-Wiki layout) |

`VELES_USER_HOME` `~` को redirect करता है (ताकि user state `<override>/.veles/` में रहे)।
पूरे tree के लिए देखें [project layout](project-layout.md)।

---

## User config — `~/.veles/config.toml`

पहली बार चलने वाले wizard द्वारा लिखा जाता है; हाथ से edit करना सुरक्षित है।

```toml
[user]
language = "en"                  # "en" | "ru" — UI string locale
default_provider = "openrouter"  # default provider for new projects
default_model = "anthropic/claude-sonnet-4.6"
first_project_name = "myorg"     # recorded by the wizard
tui_theme = "everforest"         # everforest | dracula | gruvbox | tokyo-night | catppuccin

[permissions]                    # optional per-tool policy
fetch_url  = "approval_required" # allow | approval_required | always_confirm
write_file = "always_confirm"

[routing.tasks]                  # optional user-scope routing (see below)
compressor = "openrouter:anthropic/claude-haiku-4.5"

[mcp.servers.my-server]          # optional user-scope MCP servers
transport = "stdio"
command = "python"               # executable only — arguments go in `args`
args = ["-m", "my_mcp_server"]
```

| Key | प्रकार | उद्देश्य |
|---|---|---|
| `[user] language` | `"en"` \| `"ru"` | UI strings के लिए locale (`VELES_LOCALE` से overridable) |
| `[user] default_provider` | string | जब कोई न दिया हो तब उपयोग होने वाला provider |
| `[user] default_model` | string | जब कोई न दिया हो तब उपयोग होने वाला model |
| `[user] tui_theme` | string | Default TUI color theme |
| `[permissions] <tool>` | policy | प्रति-tool permission policy (देखें [trust & sandbox](../explanation/trust-and-sandbox.md)) |

---

## Project config — `<project>/.veles/config.toml`

```toml
[engine]
provider = "openrouter"                               # provider name for the main agent + routing base
model = "anthropic/claude-sonnet-4.6"                # model id (omit to require --model or the user default_model)
request_timeout_s = 180                              # वैकल्पिक; एक उत्तर के लिए कितनी प्रतीक्षा
max_retries = 1                                      # वैकल्पिक; प्रति अनुरोध पुनः प्रयास

[routing.tasks]                  # per-task overrides (highest priority below explicit flags)
default    = "openrouter:anthropic/claude-sonnet-4.6"
compressor = "openrouter:anthropic/claude-haiku-4.5"
insights   = "openrouter:anthropic/claude-haiku-4.5"
advisor    = "openrouter:anthropic/claude-opus-4.8"
vision     = "openai:gpt-4o"
embedding  = "openai:text-embedding-3-small"

[daemon]                         # the unnamed/"default" daemon
enabled = true
host = "127.0.0.1"
port = 8765
autostart = false

[daemon.api]                     # a named daemon session ("api")
provider = "anthropic"
model = "claude-opus-4.8"
host = "127.0.0.1"
port = 8801
mode = "auto"

[channels.telegram]              # global channels (served by the unnamed daemon)
enabled = true
whitelist = ["@alice", "123456789"]

[daemon.api.channels.telegram]   # channels bound to a named daemon session
enabled = true
whitelist = ["@bob"]

[mcp.servers.github]             # external MCP servers (project scope)
transport = "stdio"             # stdio | http | sse
command = "npx"                  # executable only — arguments go in `args`
args = ["-y", "@modelcontextprotocol/server-github"]
env = { GITHUB_TOKEN = "${GITHUB_TOKEN}" }   # ${VAR} interpolates from the environment
```

### Sections

| Section | उद्देश्य |
|---|---|
| `[engine]` | main agent और routing cascade के लिए base provider (`provider` = provider name) + model (`model` = model id), साथ ही क्लाइंट बजट `request_timeout_s` / `max_retries` |
| `[routing.tasks]` | प्रति-task `provider:model` overrides — देखें [per-task routing](../how-to/per-task-routing.md) |
| `[permissions]` | प्रति-tool permission policy (project scope) |
| `[daemon]` | unnamed/"default" daemon का bind + autostart |
| `[daemon.<name>]` | एक नामित daemon session (अपना model/provider/host/port/mode) |
| `[channels.<type>]` | unnamed daemon द्वारा served एक channel (जैसे `telegram`) |
| `[daemon.<name>.channels.<type>]` | किसी नामित daemon session से bound एक channel |
| `[mcp.servers.<name>]` | एक बाहरी MCP server (tool source) |

`[routing.tasks]` के लिए task types: `default`, `curator`, `compressor`, `insights`,
`skills`, `advisor`, `vision`, `embedding`।

> `AGENTS.md` में natural-language routing hints एक auto-generated `routing.nl.toml`
> में parse की जाती हैं; explicit `[routing.tasks]` entries हमेशा जीतती हैं। फिर से
> parse करने हेतु `veles route refresh` चलाएँ। देखें [per-task routing](../how-to/per-task-routing.md)।

### उत्तर के लिए कितनी प्रतीक्षा, और कितने पुनः प्रयास

```toml
[engine]
request_timeout_s = 180
max_retries = 1
```

दोनों **क्लाइंट** पैरामीटर हैं, इसीलिए वे `[engine.request.<provider>]` के भीतर नहीं
बल्कि सीधे `[engine]` के नीचे रहते हैं: वह सेक्शन अनुरोध की *बॉडी* है, और टाइमआउट
कभी बॉडी में यात्रा नहीं करता।

इनके बिना टाइमआउट मॉडल id से अनुमानित होता है: रीज़निंग परिवार को 900 सेकंड, उसी का
`flash`/`mini` संस्करण 450 सेकंड, बाकी सब 120 सेकंड। यह अनुमान संरचनात्मक रूप से
कमज़ोर है: **नाम एक परिवार का वर्णन करता है, जबकि उत्तर का समय उसे सर्व करने वाला
बैकएंड तय करता है।** एक ही id एक बैकएंड पर 33 टोकन/सेकंड और दूसरे पर 0.8 टोकन/सेकंड
देता है। जब अनुमानित संख्या आपके रन के लिए ठीक न हो, उसे स्वयं सेट करें; और यदि आप
चाहते हैं कि वह संख्या दो बार एक ही अर्थ रखे, तो नीचे बताए अनुसार बैकएंड पिन करें।

`max_retries` भी इसी कारण मायने रखता है। इसके बिना SDK दो बार पुनः प्रयास करता है,
यानी 450 सेकंड का टाइमआउट एक ही टर्न में वास्तव में 1350 सेकंड तक हो सकता है — जो
उदार दिखने वाले बजट को उड़ाने के लिए काफी है। `0` एक वैध मान है और कुंजी छोड़ देने के
बराबर नहीं है।

दोनों की प्राथमिकता: कोड में स्पष्ट आर्गुमेंट → `[engine]` → मॉडल-आधारित डिफ़ॉल्ट।
ऐसा मान जो धनात्मक संख्या न हो (या `max_retries` के लिए अऋणात्मक पूर्णांक न हो),
फ़ाइल का नाम बताते हुए `ConfigError` के साथ रन रोक देता है।

**दायरा:** आज ये कुंजियाँ केवल OpenRouter अडैप्टर पढ़ता है। Anthropic, OpenAI और
Gemini के क्लाइंट दोनों पैरामीटर के बिना बनते हैं और इन्हें अनदेखा करते हैं।

### बैकएंड पिन करना, और रिक्वेस्ट बॉडी की अन्य कुंजियाँ

`[engine.request.<provider>]` उस प्रोवाइडर की रिक्वेस्ट बॉडी में **ज्यों का त्यों**
भेजा जाता है। Veles अपस्ट्रीम के स्कीमा का मॉडल नहीं बनाता, इसलिए प्रोवाइडर जो भी
विकल्प स्वीकार करता है वह तुरंत काम करता है — Veles के उसे जानने का इंतज़ार किए बिना:

```toml
[engine.request.openrouter.provider]
order = ["GMICloud"]
allow_fallbacks = false

[engine.request.openrouter.reasoning]
enabled = false
```

यह सेक्शन **प्रोवाइडर के नाम** से कुंजीबद्ध है (`openrouter`, `anthropic`, `openai`,
`gemini`, `ollama`, `llamacpp`, `openai-compat`), ताकि एक ही प्रोजेक्ट कॉन्फ़िग
बैकएंड बदलने पर भी टिकी रहे: OpenRouter का `provider` ब्लॉक llama.cpp को भेजने पर
400 मिलेगा, इसलिए हर बैकएंड सिर्फ़ अपना ही सब-सेक्शन पढ़ता है। सेक्शन घोषित न होने पर
रिक्वेस्ट बाइट-दर-बाइट पहले जैसी ही रहती हैं।

**इसकी ज़रूरत कब पड़ती है: दोहराए जा सकने वाले माप।** OpenRouter जैसा रिले एक ही मॉडल
को अलग-अलग क्वांटाइज़ेशन वाले कई बैकएंड पर बाँटता है, इसलिए एक ही इनपुट पर दो रन ऐसे
कारणों से अलग हो सकते हैं जिनका इनपुट से कोई लेना-देना नहीं। `session_id` आधारित
स्टिकी रूटिंग एक बातचीत को एक ही बैकएंड पर टिकाए रखती है, पर यह नहीं बताती कि वह
**कौन-सा** है।

`quantizations` से नहीं, `order` से पिन करें। 18-09-2026 तक `z-ai/glm-5.3-flash`
के 29 एंडपॉइंट हैं: 16 `fp8` पर, 3 `fp4` पर, एक `nvfp4`, **9 ऐसे जो कोई क्वांटाइज़ेशन
घोषित ही नहीं करते**, और `bf16` पर एक भी नहीं। यानी `quantizations = ["fp8"]` के बाद
भी 16 उम्मीदवार बचते हैं, जिनकी कॉन्टेक्स्ट विंडो 262144 से 1310720 टोकन तक फैली है;
जबकि एक ही तत्व वाला `order` और `allow_fallbacks = false` मिलकर बैकएंड को निश्चित कर
देते हैं। किसी मॉडल के एंडपॉइंट देखने के लिए:

```bash
curl -s https://openrouter.ai/api/v1/models/<author>/<slug>/endpoints \
  -H "Authorization: Bearer $OPENROUTER_API_KEY" | jq '.data.endpoints[]
  | {provider_name, quantization, context_length}'
```

पिन सिर्फ़ माप वाले प्रोजेक्ट में रखें — प्रोडक्शन को स्टिकी रूटिंग चाहिए, जो
उपलब्धता और फ़ॉलबैक बनाए रखती है।

**यह जाँचना कि पिन टिका या नहीं।** हर मॉडल-कॉल मंशा और परिणाम दोनों
`.veles/traces.jsonl` में लिखता है: `request_extra` यानी क्या भेजा गया,
`upstream_provider` यानी किसने जवाब दिया। एक पंक्ति काफ़ी है:

```bash
jq -r 'select(.session_id=="<sid>") | .upstream_provider' .veles/traces.jsonl | sort -u
```

एक से ज़्यादा पंक्तियाँ मतलब उस रन ने बैकएंड मिला दिए। उन्हीं रिकॉर्ड्स में
`reasoning_tokens` (बजट का कितना हिस्सा सोचने में गया) और `est_cost_usd` (अपस्ट्रीम
द्वारा बताई गई असल लागत) भी होते हैं।

**गलतियाँ जानबूझकर शोर मचाती हैं।** प्रोवाइडर के नाम की स्पेलिंग गलत हो या सेक्शन के
पथ में टाइपो हो (`[engine.reqest.…]`), रन `ConfigError` के साथ रुक जाता है जो फ़ाइल और
ज्ञात प्रोवाइडरों के नाम बताता है: जो पिन तार तक पहुँचा ही नहीं, वह चुपचाप उसी माप को
बेकार कर देता जिसके लिए उसे लिखा गया था। प्रोवाइडर के सब-सेक्शन के *भीतर* की कुंजियाँ
Veles नहीं जाँचता, क्योंकि अपस्ट्रीम जाँचता है: OpenRouter अनजानी कुंजी पर
`400 provider: Unrecognized key: "quantization"` और बेमेल मान पर
`404 No endpoints found …` लौटाता है।

### बातचीत के रिकॉर्ड कितने समय रखे जाते हैं

**जब तक आप न कहें, कुछ भी नहीं मिटाया जाता।** `turn_retention_days` का डिफ़ॉल्ट `0`
है, यानी सभी संवाद-टर्न हमेशा के लिए रखे जाते हैं। `memory.db` पर सीमा लगानी हो तो
दिनों की संख्या दें:

```toml
[memory]
turn_retention_days = 90   # 0 (डिफ़ॉल्ट) सब कुछ रखता है
```

चालू करने पर उतने दिनों से पुराने कच्चे संवाद-टर्न हटा दिए जाते हैं; जबकि उनसे निकाले
गए **इनसाइट्स** और नियम हर हाल में हमेशा के लिए रखे जाते हैं। रिकॉर्ड कच्चा माल है और
इनसाइट्स वह वजह जिसके लिए उसे पढ़ा गया।

रिकॉर्ड हटाने के लिए **दोनों** शर्तें पूरी होनी चाहिए: वह विंडो से पुराना हो, **और**
क्यूरेटर उस सत्र को पहले ही प्रोसेस कर चुका हो। जिस सत्र तक क्यूरेटर पहुँचा ही नहीं,
वह कभी नहीं हटता, चाहे कितना भी पुराना हो — वरना रिकॉर्ड उससे कुछ सीखने से पहले ही
नष्ट हो जाता।

चालू करने की कीमत: `veles sessions search` सिर्फ़ विंडो के भीतर का टेक्स्ट ढूँढ पाता
है। `veles sessions list` पुराने रन फिर भी दिखाता रहता है, क्योंकि सत्र की पंक्तियाँ
(id, शीर्षक, टाइमस्टैम्प) बनी रहती हैं — सिर्फ़ संदेशों का मूल पाठ जाता है। सफ़ाई
`veles dream` के दौरान होती है, इनसाइट निकालने के बाद।

### लॉग रोटेशन

`traces.jsonl` और `events.jsonl` 50 MB पर `<नाम>.<unix_ts>` में रोटेट होते हैं, और
सबसे नई **10** रोटेशन रखी जाती हैं — उससे पुरानी अगली रोटेशन के समय हटा दी जाती हैं।
पहले वे हमेशा के लिए रखी जाती थीं।

सामान्य उपयोग पर कुछ भी कॉन्फ़िगर करने की ज़रूरत नहीं: प्रति trace रिकॉर्ड ~530 बाइट और
एजेंट के प्रति टर्न ~1.1 KB इवेंट के हिसाब से पहली रोटेशन बरसों दूर है। यह सेटिंग
इसलिए है क्योंकि बिना नीति के असीमित वृद्धि एक रिसाव है, जिसे आख़िर में उसी को खोजना
पड़ेगा जिसे यह मशीन विरासत में मिलेगी।

### छवियाँ

किसी चैनल पर भेजी गई फ़ोटो का वर्णन टर्न शुरू होने से पहले ही बन जाता है — उस मॉडल से
जिसकी ओर `[routing.tasks].vision` इशारा करता है, और स्पष्ट रूट न होने पर वह आपका
`[engine]` मॉडल ही है। इसलिए मल्टीमॉडल इंजन को कोई कॉन्फ़िगरेशन चाहिए ही नहीं।

`[vision] mode` पाइपलाइन चुनता है:

- `model` (डिफ़ॉल्ट) — विज़न मॉडल छवि का वर्णन करता है।
- `ocr` — सिर्फ़ Tesseract। लोकल, मुफ़्त, कोई LLM कॉल नहीं; टेक्स्ट के स्कैन के लिए
  अच्छा।
- `ocr+model` — पहले हूबहू टेक्स्ट, फिर मॉडल का वर्णन।
- `off` — कुछ नहीं पढ़ा जाता; फ़ाइल फिर भी सहेजी जाती है और एजेंट चाहे तो खुद
  `image_describe` / `image_ocr` बुला सकता है।

जब इंजन सिर्फ़ टेक्स्ट वाला हो तो `[vision] model` सेट करें। विज़न-सक्षम कोई भी
प्रोवाइडर चलेगा, लोकल सर्वर समेत: `ollama:llava`, `llamacpp:…`, `openai-compat:…`।

### `project.toml`

`<project>/.veles/project.toml` में अपरिवर्तनीय project metadata (`name`,
`created_at`, `schema_version`, `layout`) रहता है। आम तौर पर आप इसे हाथ से edit नहीं करते।

---

## AGENTS.md

प्रोजेक्ट root में प्रोजेक्ट context file। यह startup पर agent के system prompt में
inject होती है और `CLAUDE.md` तथा `GEMINI.md` से symlinked होती है ताकि उस directory
में शुरू किया गया `claude` या `gemini` CLI वही context उठा ले।

इसे छोटा रखें — auxiliary `.md` files (जैसे `wiki/INDEX.md`) माँग पर load होती हैं।
आवश्यक sections को `veles schema validate` से validate करें। देखें
[layout packs & the LLM-Wiki](../explanation/layout-packs-and-llm-wiki.md)।

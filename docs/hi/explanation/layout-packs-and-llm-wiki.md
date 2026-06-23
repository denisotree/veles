# Layout packs और LLM-Wiki

> 🌐 **भाषाएँ:** **English** · [Русский](../../ru/explanation/layout-packs-and-llm-wiki.md)

एक **layout pack** यह परिभाषित करता है कि किसी project का *user content* कैसे
व्यवस्थित होता है — कौन-सी directories मौजूद हैं, agent किनमें लिख सकता है, और
वह कौन-से operations प्रदान करता है। डिफ़ॉल्ट **LLM-Wiki** है। यह एक content
विकल्प है, Veles का कोई core सिद्धांत **नहीं**।

## Layout pack क्या होता है

एक layout pack एक directory होती है जिसमें `layout.toml` manifest होता है
(साथ ही वैकल्पिक skill और template फ़ाइलें)। यह manifest घोषित करता है:

- **Writable zones** — वे directories जिनमें agent content लिख सकता है
  (हर `write_file` पर लागू किया जाता है)।
- **Read-only zones** — वह सामग्री जिसे agent पढ़ता है पर कभी संशोधित नहीं करता।
- **Operations** — नामित workflows, जो pack के भीतर skills के रूप में आते हैं।
- **Scaffold** (`[layout.scaffold]`) — `veles init` क्या बनाता है: directories
  और एक वैकल्पिक `AGENTS.md` template (`{name}` को प्रतिस्थापित किया जाता है)।
- **Engines** (`[layout.engines]`) — pack कौन-सी core content machinery सक्रिय
  करता है। आज एक engine है: `wiki`। इसके बिना project में कोई wiki tools,
  कोई wiki recall, कोई INDEX injection मौजूद नहीं होता।
- **Context file** (`context_file`) — एक फ़ाइल जो agent के stable system prompt
  में inject की जाती है (LLM-Wiki `INDEX.md` का उपयोग करता है)।

## Builtin packs

| Pack | `veles init --layout <name>` क्या बनाता है |
|---|---|
| `llm-wiki` *(default)* | [Karpathy-style LLM-Wiki](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f): `sources/` (read-only), `wiki/` (agent-writable), prompt में inject किया गया `INDEX.md`, `ingest`/`query`/`lint` skills, wiki engine चालू। |
| `notes` | एक एकल flat `notes/` directory जिसमें agent लिखता है। कोई wiki machinery नहीं। |
| `bare` | बिल्कुल कोई content scaffold नहीं — code repositories और free-form काम के लिए। project root के भीतर writes अनुमतिपूर्ण होती हैं (फिर भी trust ladder के अधीन)। |

## Custom layouts

एक pack को `~/.veles/layouts/<name>/layout.toml` (user-global) या
`<project>/.veles/layouts/<name>/` (project-local; समान नाम के user और builtin
packs को छाया देता है) में रखें और `veles init --layout <name>` पास करें।
`notes` builtin कॉपी करने के लिए न्यूनतम उदाहरण है। आप conventions को
`AGENTS.md` में भी वर्णित कर सकते हैं — layout zones लागू करता है, AGENTS.md
व्यवहार का मार्गदर्शन करता है।

## यह क्या *नहीं* है

Layout केवल **आपके content** को नियंत्रित करता है। Veles की अपनी project memory —
`memory.db` और `.veles/memory/` artefact tree (insights, session digests,
proposals, system-ops journal) — system-side है और किसी भी layout के अंतर्गत
समान रूप से काम करती है। Layouts बदलने से learning loop, sessions, या registries
पर कभी असर नहीं पड़ता। देखें [architecture](architecture.md) और
[project layout](../reference/project-layout.md)।

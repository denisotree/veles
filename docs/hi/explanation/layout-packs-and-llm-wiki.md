# Layout packs और LLM-Wiki

> 🌐 **भाषाएँ:** [English](../../en/explanation/layout-packs-and-llm-wiki.md) · [简体中文](../../zh-CN/explanation/layout-packs-and-llm-wiki.md) · [繁體中文](../../zh-TW/explanation/layout-packs-and-llm-wiki.md) · [日本語](../../ja/explanation/layout-packs-and-llm-wiki.md) · [한국어](../../ko/explanation/layout-packs-and-llm-wiki.md) · [Español](../../es/explanation/layout-packs-and-llm-wiki.md) · [Français](../../fr/explanation/layout-packs-and-llm-wiki.md) · [Italiano](../../it/explanation/layout-packs-and-llm-wiki.md) · [Português (BR)](../../pt-BR/explanation/layout-packs-and-llm-wiki.md) · [Português (PT)](../../pt-PT/explanation/layout-packs-and-llm-wiki.md) · [Русский](../../ru/explanation/layout-packs-and-llm-wiki.md) · [العربية](../../ar/explanation/layout-packs-and-llm-wiki.md) · **हिन्दी** · [বাংলা](../../bn/explanation/layout-packs-and-llm-wiki.md) · [Tiếng Việt](../../vi/explanation/layout-packs-and-llm-wiki.md)

एक **layout pack** यह परिभाषित करता है कि किसी project का *user content* कैसे
व्यवस्थित होता है — कौन-सी directories मौजूद हैं, agent किनमें लिख सकता है, और
वह कौन-से operations प्रदान करता है। डिफ़ॉल्ट **`bare`** है, जो आपकी directory में
`.veles/` और `AGENTS.md` के अलावा कुछ नहीं जोड़ता। **LLM-Wiki** extension
registry का एक विकल्प है, Veles का कोई core सिद्धांत **नहीं**।

## Layout pack क्या होता है

एक layout pack एक directory होती है जिसमें `layout.toml` manifest होता है
(साथ ही वैकल्पिक skill और template फ़ाइलें)। यह manifest घोषित करता है:

- **Writable zones** — वे directories जिनमें agent content लिख सकता है
  (हर `write_file` पर लागू किया जाता है)।
- **Read-only zones** — वह सामग्री जिसे agent पढ़ता है पर कभी संशोधित नहीं करता।
- **Operations** — नामित workflows, जो pack के भीतर skills के रूप में आते हैं।
- **Scaffold** (`[layout.scaffold]`) — `veles init` क्या बनाता है: directories
  और एक वैकल्पिक `AGENTS.md` template (`{name}` को प्रतिस्थापित किया जाता है)।
- **Engines** (`[layout.engines]`) — pack कौन-सी content machinery माँगता है।
  engine को एक module उपलब्ध कराता है (registry का `wiki` module `wiki`
  उपलब्ध कराता है)। इसके बिना project में कोई wiki tools, कोई wiki recall,
  कोई INDEX injection मौजूद नहीं होता।
- **Context file** (`context_file`) — एक फ़ाइल जो agent के stable system prompt
  में inject की जाती है (LLM-Wiki `INDEX.md` का उपयोग करता है)।

## उपलब्ध packs

| Pack | कहाँ से | `veles init --layout <name>` क्या बनाता है |
|---|---|---|
| `bare` *(default)* | built in | बिल्कुल कोई content scaffold नहीं — code repositories और free-form काम के लिए। project root के भीतर writes अनुमतिपूर्ण होती हैं (फिर भी trust ladder के अधीन)। |
| `llm-wiki` | registry (`public:official/llm-wiki`, साथ में `wiki` module आता है) | [Karpathy-style LLM-Wiki](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f): `sources/` (raw, convention से read-only — लागू नहीं किया जाता), `wiki/` (agent-writable), prompt में inject किया गया `INDEX.md`, `ingest`/`query`/`lint`/`organize`/`structure_design` skills, wiki engine चालू, `veles add` और `/wiki`। layout द्वारा घोषित एक behavioural prompt (`templates/behaviour.md`) sources/wiki अनुशासन और migration/log-patch नियम रखता है। |
| `notes` | registry (`public:official/notes`) | एक एकल flat `notes/` directory जिसमें agent लिखता है। कोई wiki machinery नहीं। |

terminal पर `veles init` पूछता है कि कौन-सा pack उपयोग करना है (installed packs और
आपकी registries में मौजूद packs); जो pack installed नहीं है उसे चुनने पर install
करने का प्रस्ताव मिलता है। `veles registry install llm-wiki` उसे पहले से install कर देता है।

## 1.2.3 से पहले के projects

जिस project का layout installed नहीं है (upgrade के बाद `llm-wiki` project, या बिना
`layout` key वाला project — ये सब wiki projects थे) वह फिर भी खुलता है। terminal पर
`veles` और `veles run` एक ही confirmation में pack (उसके लिए ज़रूरी engine के साथ)
install करने का प्रस्ताव देते हैं; अन्यथा — daemon, channels, अन्य verbs में — Veles
install command एक बार print करता है और wiki के बिना चलता है। `wiki/` में कुछ भी
नहीं छुआ जाता।

## Custom layouts

एक pack को `~/.veles/layouts/<name>/layout.toml` (user-global) या
`<project>/.veles/layouts/<name>/` (project-local; समान नाम के user और builtin
packs को छाया देता है) में रखें और `veles init --layout <name>` पास करें।
registry का `notes` pack कॉपी करने के लिए न्यूनतम उदाहरण है। जो pack ऐसा engine
माँगता है जिसे कोई installed module उपलब्ध नहीं कराता, उसे भी वही install प्रस्ताव
मिलता है। आप conventions को
`AGENTS.md` में भी वर्णित कर सकते हैं — layout zones लागू करता है, AGENTS.md
व्यवहार का मार्गदर्शन करता है।

## यह क्या *नहीं* है

Layout केवल **आपके content** को नियंत्रित करता है। Veles की अपनी project memory —
`memory.db` और `.veles/memory/` artefact tree (insights, session digests,
proposals, system-ops journal) — system-side है और किसी भी layout के अंतर्गत
समान रूप से काम करती है। Layouts बदलने से learning loop, sessions, या registries
पर कभी असर नहीं पड़ता। देखें [architecture](architecture.md) और
[project layout](../reference/project-layout.md)।

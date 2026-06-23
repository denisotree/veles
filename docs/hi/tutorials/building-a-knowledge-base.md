# एक knowledge base बनाना

> 🌐 **भाषाएँ:** **English** · [Русский](../../ru/tutorials/building-a-knowledge-base.md)

इस tutorial में आप एक Veles project को एक जीवंत knowledge base में बदलेंगे: कुछ sources
ingest करेंगे, Veles को wiki pages लिखने देंगे, सवाल पूछेंगे, और जो सीखा उसे consolidate
करेंगे। यह default **LLM-Wiki** workflow है। लगभग 15 मिनट।

आपको पहले [Getting started](getting-started.md) पूरा कर लेना चाहिए।

## मूल विचार

एक Veles project में दो content zones होते हैं:

- `sources/` — raw, immutable material जो आप उसे देते हैं (agent के लिए read-only)।
- `wiki/` — agent की अपनी, LLM-generated knowledge (एकमात्र zone जिसमें वह content
  लिखता है)।

आप sources feed करते हैं; Veles उन्हें linked wiki pages में distill करता है; आप wiki से
natural language में query करते हैं। इसका कारण जानने के लिए देखें
[layout packs & the LLM-Wiki](../explanation/layout-packs-and-llm-wiki.md)।

## 1. एक source ingest करें

`veles add` एक file या URL पढ़ता है और उसका सारांश देने वाला wiki page लिखता है:

```bash
veles add https://en.wikipedia.org/wiki/Knowledge_management
veles add ./notes/meeting-2026-06-01.md
```

हर `add` `wiki/` के अंदर एक page बनाता है और उसे wiki graph में link करता है।

## 2. wiki को बढ़ते देखें

जो लिखा गया उसे देखें:

```bash
ls wiki/concepts wiki/entities wiki/sources
```

Pages एक-दूसरे को cross-reference करते हैं। on-demand `wiki/INDEX.md` catalog एक map
बनाए रखता है जिसे agent ज़रूरत पड़ने पर load करता है (monolithic context dump नहीं)।

## 3. सवाल पूछें

अब अपनी knowledge base से natural language में query करें:

```bash
veles run "Using the wiki, summarise the main approaches to knowledge management
and cite the pages you used."
```

Veles wiki को search करता है, relevant pages पढ़ता है, और जवाब देता है — केवल अपने
training data के बजाय आपके द्वारा ingest किए गए पर आधारित।

interactive आगे-पीछे बातचीत के लिए, TUI में वही करें (`veles tui`)।

## 4. sessions को consolidate करें

जैसे-जैसे आप काम करते हैं, conversations जमा होती जाती हैं। उन्हें durable wiki pages में
compact करने और lessons निकालने के लिए curator चलाएँ:

```bash
veles curate
```

यह `wiki/sessions/` pages लिखता है और project के insights और rules अपडेट करता है। Veles
समय के साथ यह स्वतः भी करता है — देखें
[project memory & the learning loop](../explanation/project-memory-and-learning-loop.md)।

## 5. wiki को स्वस्थ रखें

समय के साथ pages stale या orphan हो जाते हैं। `lint` operation उन्हें ढूँढता है:

```bash
veles run "lint"
```

(`ingest`, `query`, और `lint` LLM-Wiki layout के साथ bundled skills हैं; आप उन्हें
`veles run "<operation>"` से invoke करते हैं या agent को उन्हें call करने देते हैं।)

## आपने क्या बनाया

एक self-organising knowledge base: sources अंदर, linked wiki pages बाहर, natural
language में queryable, जो Veles के consolidate करने के साथ और साफ-सुथरी होती जाती है।
यहाँ से आगे:

- **[Manage skills, tools, and modules](../how-to/manage-skills-and-tools.md)** —
  Veles को reusable workflows सिखाएँ।
- **[Run as a daemon](../how-to/run-as-daemon.md)** + **[connect Telegram](../how-to/connect-telegram.md)** —
  अपने phone से अपनी knowledge base से बात करें।
- **[Multiple projects & subprojects](../how-to/multi-project-and-subprojects.md)** —
  कई knowledge bases तक scale करें।

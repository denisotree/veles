# Project memory और learning loop

> 🌐 **भाषाएँ:** [English](../../en/explanation/project-memory-and-learning-loop.md) · [简体中文](../../zh-CN/explanation/project-memory-and-learning-loop.md) · [繁體中文](../../zh-TW/explanation/project-memory-and-learning-loop.md) · [日本語](../../ja/explanation/project-memory-and-learning-loop.md) · [한국어](../../ko/explanation/project-memory-and-learning-loop.md) · [Español](../../es/explanation/project-memory-and-learning-loop.md) · [Français](../../fr/explanation/project-memory-and-learning-loop.md) · [Italiano](../../it/explanation/project-memory-and-learning-loop.md) · [Português (BR)](../../pt-BR/explanation/project-memory-and-learning-loop.md) · [Português (PT)](../../pt-PT/explanation/project-memory-and-learning-loop.md) · [Русский](../../ru/explanation/project-memory-and-learning-loop.md) · [العربية](../../ar/explanation/project-memory-and-learning-loop.md) · **हिन्दी** · [বাংলা](../../bn/explanation/project-memory-and-learning-loop.md) · [Tiếng Việt](../../vi/explanation/project-memory-and-learning-loop.md)

Veles की परिभाषक विशेषता यह है कि यह प्रति project **याद रखता है** और **सीखता
है**। यह पेज समझाता है कि वह memory क्या है और learning loop उसे उपयोगी कैसे
बनाए रखता है।

## Memory एक संरचित artefact है

Project memory `<project>/.veles/` में रहती है — `memory.db` (SQLite, source
of truth) और एक मानव-पठनीय `.veles/memory/` tree (rendered insight views,
session digests, proposals, एक system-ops journal)। यह **आपके content से अलग**
है और किसी भी layout (wiki, notes, या bare) के अंतर्गत समान रूप से काम करती है।
यह कोई chat transcript का ढेर नहीं है — यह संरचित परतों का एक समूह है:

- **Session log** — हर बातचीत, प्रति turn एक row, full-text indexed।
- **Rules** — संक्षिप्त निर्देश जिनका agent को पालन करना चाहिए (`format`, `do`,
  `don't`, `preference`), stable system prompt में inject किए जाते हैं।
- **Insights** — sessions से निचोड़े गए सबक। SQL row canonical होती है
  (recall, aging, और dedup उसी पर काम करते हैं); मनुष्यों और exports के लिए एक
  markdown view `.veles/memory/insights/` में render की जाती है।
- **Project tree map** — एक cached, semantically-tagged file map ताकि agent
  पूरे tree के बजाय 3–5 प्रासंगिक फ़ाइलें पढ़े।
- **Skill & tool registries** — telemetry के साथ (use/success/error counts) जिसका
  उपयोग ranking और dedup करते हैं।

[project layout](../reference/project-layout.md#project-memory-velesmemorydb) में
table सूची देखें।

## Recall: छोटा context, माँग पर खींचा गया

`AGENTS.md` जानबूझकर छोटा रखा गया है। जब आप कुछ पूछते हैं, Veles केवल वही खींचता
है जो प्रासंगिक है: मिलते-जुलते पिछले turns (full-text + वैकल्पिक vector
reranking), लागू rules और insights, और वे फ़ाइलें जिन्हें project-tree map सबसे
अधिक स्कोर देता है। यह हर model call को सब कुछ उड़ेलने के बजाय केंद्रित और सस्ता
रखता है।

## Learning loop

अनुभव तीन तंत्रों के माध्यम से टिकाऊ ज्ञान बनता है:

### Insights — सबक पकड़ना
किसी run के बाद, एक extractor याद रखने योग्य चीज़ें ढूँढता है: स्पष्ट "remember
X" / "never Y" feedback, और tool-error→recovery patterns (एक विफलता जिसके बाद
सुधार आया)। यह इन्हें insights और rules में निचोड़ता है ताकि वही गलती दोहराई न
जाए।

### Curator — sessions को समेकित करना
Curator पुरानी sessions को टिकाऊ memory में निचोड़ता है: SQL insights और rules
हमेशा; इसके अतिरिक्त एक `wiki/sessions/` पेज जब project का layout wiki engine
सक्षम करता है। यह idle/post-turn timers पर चलता है, या `veles curate` के साथ
माँग पर।

### Dreaming — पृष्ठभूमि रखरखाव
`veles dream` (और idle होने पर daemon) insights निकालता है, skills और insights
को deduplicate करता है, promotions सुझाता है, और (wiki layout के अंतर्गत) wiki
को lint करता है — आपको रोके बिना memory को ताज़ा रखता है। गहरे LLM pass के लिए
`--include-consolidation` जोड़ें।

## Context compression

लंबी बातचीतें एक sliding-window compressor द्वारा model की context सीमा के नीचे
रखी जाती हैं: जब in-memory history एक token threshold पार करती है, तो बीच का हिस्सा
(एक सस्ते routed model द्वारा) सारांशित किया जाता है और `.veles/memory/sessions/`
में सहेजे गए सारांश के pointer से बदल दिया जाता है। पूरी history हमेशा `memory.db`
में बनी रहती है — केवल in-memory window संपीड़ित होती है, इसलिए यह disk पर
lossless है।

## यह क्यों मायने रखता है

चूँकि memory संरचित है और loop निरंतर चलता है, एक Veles project को आप **जितना
अधिक उपयोग करते हैं उतना ही अधिक उपयोगी** होता जाता है — यह आपके conventions
सीखता है, दोहराई जाने वाली गलतियों से बचता है, और उत्तरों को उसी में आधारित करता
है जो उसने वास्तव में देखा है।

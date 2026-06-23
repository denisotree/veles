# संचित होती क्षमता के रूप में Skills और tools

> 🌐 **भाषाएँ:** **English** · [Русский](../../ru/explanation/skills-and-tools.md)

Veles tools और skills के एक न्यूनतम सेट से शुरू होता है और काम करते-करते उसे
**बढ़ाता** है। यह पेज दोनों के बीच के अंतर को समझाता है और वे कैसे संचित होते
हैं। commands के लिए, देखें
[manage skills & tools](../how-to/manage-skills-and-tools.md)।

## Tools बनाम skills

- एक **tool** एकल निष्पादन-योग्य क्रिया है — एक फ़ाइल पढ़ना, एक shell command
  चलाना, एक URL लाना, web खोजना, एक wiki पेज लिखना। Tools वही हैं जिन्हें model
  कॉल करता है।
- एक **skill** एक औपचारिक *process* है — एक `SKILL.md` जिसमें एक prompt body
  और एक allowed-tool सूची होती है जो एक केंद्रित sub-agent के रूप में चलती है।
  Skills tools को एक दोहराने योग्य workflow में जोड़ते हैं (उदा. LLM-Wiki के
  `ingest`/`query`/`lint`)।

## न्यूनतम startup, माँग पर विस्तार

Veles बस इतना ही लेकर boot होता है जितना उपयोगी होने के लिए ज़रूरी है, साथ ही
अधिक खींचने के लिए एक ज्ञात स्थान। अतिरिक्त चीज़ें (एक skill, एक tool, एक module)
इंस्टॉल करना डिफ़ॉल्ट रूप से अनुमोदन माँगता है; आप स्थायी autonomy दे सकते हैं।
यह एक नए project को दुबला रखता है जबकि जहाँ ज़रूरत हो वहाँ क्षमता बढ़ने देता है।

## क्षमता कैसे संचित होती है

1. **Veles अपने tools खुद लिखता है।** जब उसे कोई दोहराने वाला task दिखता है, तो
   वह `<project>/.veles/tools/` में एक साफ़, typed, पुनः-उपयोग्य Python tool
   लिख सकता है (एक advisor code-review pass के साथ)। यह tool telemetry के साथ
   registry में शामिल हो जाता है।
2. **दोहराने वाली processes skills बन जाती हैं।** एक pattern detector आवर्ती
   tool sequences को पहचानता है और उन्हें एक skill के रूप में औपचारिक बनाने का
   प्रस्ताव देता है; skills किसी अन्य skill को `extends:` कर सकते हैं ताकि उसका
   body और tools विरासत में मिलें।
3. **Telemetry ranking चलाती है।** हर tool/skill use/success/error counts रखता
   है। ये dedup (`veles skill dedup`) और promotion सुझावों को feed करते हैं।

## दो scopes, promotion के साथ

Tools और skills दोनों दो स्तरों पर मौजूद होते हैं:

- **Project-local** (`<project>/.veles/`) — केवल यहीं दिखाई देते हैं।
- **User-global** (`~/.veles/`) — हर project में उपलब्ध।

जो क्षमता किसी एक project में खुद को सिद्ध कर देती है उसे user scope में
**promote** किया जा सकता है ताकि सभी projects लाभान्वित हों
(`veles skill promote`, `veles tool promote`), या वापस **demote** किया जा सकता
है। इसी तरह Veles कठिनाई से अर्जित workflows को projects के बीच ले जाता है।

## सिर्फ़ फ़ाइलें नहीं, registry क्यों

Skills/tools को सादा फ़ाइलों के रूप में संग्रहीत करना उन्हें निरीक्षण और संपादन
योग्य रखता है; उनकी *telemetry* को `memory.db` में संग्रहीत करना Veles को यह
तर्क करने देता है कि वास्तव में कौन-से काम करते हैं। यही संयोजन "scripts का एक
folder" को संचित होती, स्व-curated क्षमता में बदल देता है।

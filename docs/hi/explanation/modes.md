# Run modes

> 🌐 **भाषाएँ:** [English](../../en/explanation/modes.md) · [简体中文](../../zh-CN/explanation/modes.md) · [繁體中文](../../zh-TW/explanation/modes.md) · [日本語](../../ja/explanation/modes.md) · [한국어](../../ko/explanation/modes.md) · [Español](../../es/explanation/modes.md) · [Français](../../fr/explanation/modes.md) · [Italiano](../../it/explanation/modes.md) · [Português (BR)](../../pt-BR/explanation/modes.md) · [Português (PT)](../../pt-PT/explanation/modes.md) · [Русский](../../ru/explanation/modes.md) · [العربية](../../ar/explanation/modes.md) · **हिन्दी** · [বাংলা](../../bn/explanation/modes.md) · [Tiếng Việt](../../vi/explanation/modes.md)

TUI में, प्रत्येक prompt को एक **run mode** द्वारा संभाला जाता है — एक रणनीति जो
तय करती है कि उस turn को कितनी स्वायत्तता और कौन-से tools मिलें। modes को
`Shift+Tab` से बदलें; क्रम है `auto → planning → writing → goal`।

## चार modes

### `writing` — सीधी चैट
सीधा-सादा mode: आपका prompt पूरे toolset के साथ agent तक जाता है, और वह जवाब देता
है। इसे सामान्य काम के लिए उपयोग करें जहाँ आप चाहते हैं कि agent कार्य करे।

### `planning` — read-only research + एक plan
Mutations ब्लॉक रहती हैं (कोई `write_file` नहीं, कोई `run_shell` नहीं)। agent
context जुटाने के लिए read/search tools का उपयोग करता है, फिर एक संरचित plan
artefact तैयार करता है। किसी चीज़ को छूने से पहले सोचने के लिए इसका उपयोग करें —
या CLI पर वही प्रभाव पाने के लिए `veles run` को `--plan` पास करें।

### `auto` — smart routing (default)
एक त्वरित वर्गीकरण तय करता है कि आपका prompt एक सीधा अनुरोध है या उसे planning की
ज़रूरत है, फिर तदनुसार `writing` या `planning` को dispatch करता है। जब आपने अपना
इरादा व्यक्त नहीं किया हो तो यह सबसे समझदार fallback है, इसीलिए यह cycle में
default पहला पड़ाव है।

### `goal` — long-horizon उद्देश्य
एक बहु-चरणीय उद्देश्य के लिए एक finite-state machine चलाता है: यह स्पष्ट करने के
लिए आपका साक्षात्कार लेता है, एक plan की पुष्टि करता है, चरणों को निष्पादित करता
है (advisor checks के साथ), और done-condition को सत्यापित करता है — यह सब स्पष्ट
बजट के अंतर्गत। CLI समकक्ष है
[`veles goal`](../how-to/long-running-tasks.md#goals--objectives-with-budgets-and-checkpoints)
command परिवार।

## modes क्यों मौजूद हैं

अलग-अलग अनुरोधों को अलग-अलग मात्रा में सावधानी चाहिए। एक त्वरित सवाल को
औपचारिकता की ज़रूरत नहीं होनी चाहिए; एक जोखिम भरे बदलाव को पहले एक read-only
planning पास से लाभ होता है; एक बड़े उद्देश्य को बजट और checkpoints चाहिए। modes
इस चुनाव को स्पष्ट और प्रति-turn स्विच करने योग्य बनाते हैं, बजाय इसके कि पूरे
session में एक ही व्यवहार बेक कर दिया जाए।

जब आप session के बीच में स्विच करते हैं, तो agent को नए नियम बता दिए जाते हैं ताकि
उसका व्यवहार तुरंत बदल जाए।

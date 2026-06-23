# Trust और sandbox

> 🌐 **भाषाएँ:** [English](../../en/explanation/trust-and-sandbox.md) · [简体中文](../../zh-CN/explanation/trust-and-sandbox.md) · [繁體中文](../../zh-TW/explanation/trust-and-sandbox.md) · [日本語](../../ja/explanation/trust-and-sandbox.md) · [한국어](../../ko/explanation/trust-and-sandbox.md) · [Español](../../es/explanation/trust-and-sandbox.md) · [Français](../../fr/explanation/trust-and-sandbox.md) · [Italiano](../../it/explanation/trust-and-sandbox.md) · [Português (BR)](../../pt-BR/explanation/trust-and-sandbox.md) · [Português (PT)](../../pt-PT/explanation/trust-and-sandbox.md) · [Русский](../../ru/explanation/trust-and-sandbox.md) · [العربية](../../ar/explanation/trust-and-sandbox.md) · **हिन्दी** · [বাংলা](../../bn/explanation/trust-and-sandbox.md) · [Tiếng Việt](../../vi/explanation/trust-and-sandbox.md)

Veles आपकी मशीन पर एक स्वायत्त agent चलाता है, इसलिए वह agent क्या कर सकता है उसे
सीमित करता है। दो तंत्र मिलकर काम करते हैं: संवेदनशील क्रियाओं के लिए एक **trust
ladder** और filesystem के लिए एक **sandbox**। commands के लिए, देखें
[security & permissions](../how-to/security-and-permissions.md)।

## Trust ladder

हर tool समान नहीं है। एक फ़ाइल पढ़ना हानिरहित है; एक shell command चलाना या disk
पर लिखना नहीं। संवेदनशील tools (`run_shell`, `write_file`, `fetch_url`, …) चलने
से पहले रुककर पूछते हैं, चार विकल्प देते हुए:

- **Once** — इस एकल call की अनुमति दें।
- **Always for this project** — एक project-scoped grant बनाए रखें।
- **Always everywhere** — एक user-scoped grant बनाए रखें।
- **Refuse** — इसे अस्वीकार करें।

Grants संग्रहीत किए जाते हैं ताकि आपसे फिर न पूछा जाए। यह आपको क्रमिक नियंत्रण
देता है: किसी tool पर एक बार, एक project में, या वैश्विक रूप से भरोसा करें —
आपकी पसंद, जब वह पहली बार मायने रखे तब की गई।

### Always-confirm क्रियाएँ

कुछ operations इतने जोखिमपूर्ण हैं कि Veles उनकी पुष्टि **grant होने पर भी**
करता है: फ़ाइलें हटाना, URLs लाना, एक नई skill/tool/module इंस्टॉल करना, एक
channel जोड़ना, और project के बाहर लिखना। ये बाहरमुखी या कठिनाई से प्रतिवर्ती
हैं, इसलिए एक स्थायी grant को इन्हें चुपचाप कवर नहीं करना चाहिए।

### Non-interactive सुरक्षा

किसी daemon, batch, या अन्य non-TTY संदर्भ में पूछने के लिए कोई मनुष्य नहीं होता,
इसलिए Veles डिफ़ॉल्ट रूप से संवेदनशील क्रियाओं को **अस्वीकार** करता है — भटका हुआ
stdin किसी approval को चुपके से नहीं ला सकता। जानबूझकर अनुपस्थित-निगरानी में चलाने
के लिए, एक [autopilot](../how-to/security-and-permissions.md#autopilot--a-time-boxed-bypass)
window खोलें; हर autopilot क्रिया समीक्षा के लिए logged की जाती है।

## Filesystem sandbox

एक path guard सीमित करता है कि tools कहाँ पढ़ और लिख सकते हैं:

- **Read** — सक्रिय project (और उसके subprojects) के भीतर साथ ही `~/.veles/`।
- **Write** — केवल layout के writable zones (उदा. `wiki/`); machine state के लिए
  `.veles/` हमेशा writable होता है।

Sandbox से बच निकलने वाले symlinks अस्वीकार किए जाते हैं, और `..` traversal
resolution से पहले ही अस्वीकार कर दिया जाता है। URL fetches एक SSRF deny-list
रखते हैं। उन्नत setups roots को `VELES_SANDBOX_ROOTS` से override कर सकते हैं, या
private-network block को `VELES_FETCH_ALLOW_PRIVATE=1` से हटा सकते हैं — दोनों
opt-in हैं।

## यह design क्यों

लक्ष्य है **बुरे आश्चर्यों के बिना उपयोगी autonomy**: agent हर read पर एक prompt
के बिना असली काम कर सकता है, पर जो कुछ भी आपकी मशीन को नुकसान पहुँचा सकता है, पैसे
खर्च कर सकता है, या बॉक्स से बाहर जा सकता है उसे gate किया जाता है — एक बार, और फिर
आपकी पसंद के अनुसार याद रखा जाता है।

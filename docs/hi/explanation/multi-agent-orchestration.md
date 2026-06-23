# Multi-agent orchestration

> 🌐 **भाषाएँ:** **English** · [Русский](../../ru/explanation/multi-agent-orchestration.md)

जटिल काम के लिए, Veles सब कुछ एक ही context में करने के बजाय किसी task को एक
**manager** और विशेषीकृत **worker** sub-agents के बीच बाँट सकता है। यह पेज इस
model को समझाता है; इसे चालू करने के लिए देखें
[manager mode](../how-to/long-running-tasks.md#manager-mode--decompose-any-prompt)।

## स्वरूप

```
            manager  (decomposes the task, never writes the final answer)
           /    |    \
    explorer  writer  advisor   (specialised workers, run in parallel)
```

- **manager** decomposition की योजना बनाता है और समन्वय करता है — पर वह स्वयं
  अंतिम deliverable **नहीं** लिखता।
- **Workers** के पास role-specific system prompts होते हैं: `explorer` जानकारी
  जुटाता है, `writer` उत्तर तैयार करता है, `advisor` समीक्षा करता है। यह सेट
  विस्तार योग्य है।
- अंत में, manager memory में एक संक्षिप्त रिपोर्ट लिखता है।

## कोई telephone game नहीं

एक मुख्य नियम: मध्यवर्ती artefacts synthesiser तक **हू-ब-हू (verbatim)** पहुँचते
हैं, manager के paraphrase के रूप में नहीं। एक explorer के निष्कर्ष सीधे writer
को सौंपे जाते हैं, ताकि summaries की श्रृंखला से विवरण न खोएँ। यही वह बात है जो
decomposition को गुणवत्ता घटाने के बजाय बढ़ाने वाली बनाती है।

## "manager कभी नहीं लिखता" क्यों

अगर coordinator स्वयं भी उत्तर लिखता, तो वह workers को छोड़ शॉर्टकट लेने को
प्रलोभित होता और विशेषीकरण का लाभ खो देता। synthesis को एक समर्पित `writer`
में रखना (जिसे verbatim inputs दिए जाते हैं) श्रम-विभाजन को लागू करता है। Veles
इसे एक runtime गारंटी बनाता है।

## यह कब मदद करता है — और कब नहीं

Decomposition व्यापक या बहुआयामी tasks के लिए फलदायी होता है (इस codebase का
audit करना, इस सवाल को कई दृष्टिकोणों से शोधना)। एक त्वरित, single-context
अनुरोध के लिए यह बस overhead जोड़ता है — यही कारण है कि manager mode **स्पष्ट
opt-in** है, डिफ़ॉल्ट रूप से बंद (`veles run --manager` या `VELES_MANAGER_MODE=1`)।

# सुरक्षा कैसे संभालें: trust, autopilot, secrets

> 🌐 **भाषाएँ:** [English](../../en/how-to/security-and-permissions.md) · [简体中文](../../zh-CN/how-to/security-and-permissions.md) · [繁體中文](../../zh-TW/how-to/security-and-permissions.md) · [日本語](../../ja/how-to/security-and-permissions.md) · [한국어](../../ko/how-to/security-and-permissions.md) · [Español](../../es/how-to/security-and-permissions.md) · [Français](../../fr/how-to/security-and-permissions.md) · [Italiano](../../it/how-to/security-and-permissions.md) · [Português (BR)](../../pt-BR/how-to/security-and-permissions.md) · [Português (PT)](../../pt-PT/how-to/security-and-permissions.md) · [Русский](../../ru/how-to/security-and-permissions.md) · [العربية](../../ar/how-to/security-and-permissions.md) · **हिन्दी** · [বাংলা](../../bn/how-to/security-and-permissions.md) · [Tiếng Việt](../../vi/how-to/security-and-permissions.md)

Veles खतरनाक कार्रवाइयों को एक **trust ladder** के पीछे रखता है, file access को
sandbox करता है, और secrets को OS keychain में रखता है। इसके पीछे की वजह जानने के
लिए देखें [trust & the sandbox](../explanation/trust-and-sandbox.md)।

## Trust ladder

संवेदनशील tools (`run_shell`, `write_file`, `fetch_url`, …) चलने से पहले prompt
करते हैं। आप चुनते हैं: **once** (एक बार) अनुमति दें, **इस project के लिए हमेशा**,
**हर जगह हमेशा**, या **मना करें**। Grants बने रहते हैं इसलिए आपसे दोबारा नहीं पूछा
जाता।

Prompt का इंतज़ार किए बिना grants संभालें:

```bash
veles trust list                          # मौजूदा grants (user + project)
veles trust set run_shell --scope project # इस project के लिए pre-grant
veles trust set write_file --scope user   # हर जगह pre-grant
veles trust revoke run_shell              # एक grant हटाएँ
veles trust clear --scope all             # सब कुछ मिटाएँ
```

कुछ कार्रवाइयाँ grant होने पर भी **हमेशा confirm** की जाती हैं — files हटाना, URLs
fetch करना, कोई नया skill/tool/module install करना, channel connect करना, और
project के बाहर लिखना।

## Autopilot — एक time-boxed bypass

किसी बिना-निगरानी रन (रात भर चलने वाले batch) के लिए, एक window खोलें जहाँ trust
prompts अपने-आप allow हो जाएँ:

```bash
veles autopilot enable --until +2h
veles autopilot enable --until 2026-12-31T23:00:00Z
veles autopilot status
veles autopilot disable
```

हर autopilot कार्रवाई बाद में समीक्षा के लिए log की जाती है। Non-interactive
contexts (daemon, batch) डिफ़ॉल्ट रूप से मना कर देते हैं जब तक autopilot सक्रिय न
हो।

## Secrets

API keys और bot tokens OS keychain में रहते हैं, कभी config files में नहीं:

```bash
veles secret set OPENROUTER_API_KEY       # prompt करता है (या stdin से pipe करें)
veles secret list                         # कौन-से secrets configured हैं
veles secret get OPENROUTER_API_KEY --reveal
veles secret delete OPENROUTER_API_KEY
```

जब तक आप `--no-env-fallback` पास न करें, lookup मिलते-जुलते
[environment variable](../reference/environment-variables.md) पर fallback कर जाता
है।

## Sandbox

Tools सक्रिय project और `~/.veles/` के अंदर पढ़ सकते हैं, और केवल layout के
writable zones (डिफ़ॉल्ट रूप से `wiki/`, `.veles/`) में लिख सकते हैं। उन्नत setups
के लिए roots को `VELES_SANDBOX_ROOTS` (`:`-separated) से override करें। URL
fetches एक SSRF deny-list रखते हैं; `VELES_FETCH_ALLOW_PRIVATE=1`
private-network block को हटा देता है।

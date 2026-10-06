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
veles secret set OPENROUTER_API_KEY --project myproj   # सिर्फ़ एक project के लिए key
```

जब तक आप `--no-env-fallback` पास न करें, lookup मिलते-जुलते
[environment variable](../reference/environment-variables.md) पर fallback कर जाता
है।

## Sandbox

Tools सक्रिय project, `~/.veles/skills/` और `~/.veles/locales/` के अंदर पढ़ सकते हैं,
और केवल project के अंदर लिख सकते हैं — या केवल layout के writable zones में, जब layout
उन्हें declare करता हो। उन्नत setups के लिए roots को `VELES_SANDBOX_ROOTS`
(`:`-separated) से override करें। URL fetches एक SSRF deny-list रखते हैं;
`VELES_FETCH_ALLOW_PRIVATE=1` private-network block को हटा देता है।

project के `.veles/` के अंदर agent के file tools केवल `skills/`, `tools/`, `tmp/`,
`plans/`, `memory/` और `artifacts/` में लिख सकते हैं। वहाँ बाकी सब —
`trust.json`, `config.toml`, `project.toml`, `modules/`, `wiki.toml`, `memory.db` —
केवल `veles` commands और Veles के अपने tools से बदलता है। file tools project की किसी भी
अन्य `.veles/` directory को भी (किसी subproject की, या जिसे agent `wiki/` में रोप दे) किसी भी
गहराई पर अस्वीकार करते हैं। इसलिए अपने file tools से agent न खुद को trust दे सकता है, न ऐसा code
जोड़ सकता है जिसे Veles चलाए (`.veles/tools/` में लिखा गया tool तभी load होता है जब आप उसकी
file approve करें)। उसी file की अन्य spellings (case, `..`, symlink) भी अस्वीकार की जाती हैं।

ऐसी files जो बिना explicit command के चलती हैं या किसी agent CLI को steer करती हैं — `.git/`,
`.githooks/`, `.claude/`, `.gemini/`, `.agents/`, `.codex/`, `.vscode/`, `.devcontainer/`, `.husky/` के
अंतर्गत सब कुछ, और `.envrc`, `.mcp.json`, `.pre-commit-config.yaml`, `lefthook.yml`, किसी भी
गहराई पर, साथ ही repo की `core.hooksPath` directory और वह जगह जहाँ symlinked `.git` इशारा करता
है — agent के file tools इनमें तभी लिखते हैं जब आप उस write को confirm करें। Trust grants और
autopilot इसे cover नहीं करते; daemon channel में पूछता है, और जिस batch run में पूछने वाला कोई
न हो वह अस्वीकार कर देता है।

`claude-cli`, `codex` और `antigravity-cli` providers केवल Veles के tools वाले model की तरह चलते हैं: उनके अपने
shell, file-edit और web tools, project की `.claude/` settings और hooks, और अन्य MCP servers
लागू नहीं होते, और उनके द्वारा बुलाया गया हर Veles tool ऊपर की trust ladder से गुज़रता है (वहाँ
कोई prompt का जवाब नहीं दे सकता, इसलिए जो पहले से granted नहीं है वह अस्वीकार हो जाता है)।
उनका MCP config `.veles/tmp/delegate-<pid>/` में रहता है, हर चल रहे process के लिए एक, जिसमें
agent के file tools नहीं लिख सकते। `agy` project के बाहर, `~/.veles/tmp/` के अंतर्गत, एक scratch
workspace में चलता है, इसलिए project के अपने `.agents/` hooks और MCP servers उस तक कभी नहीं
पहुँचते। जब उसके पास Veles के tools हों तब वह `--dangerously-skip-permissions` के साथ चलता है —
वरना agy headless MCP calls अस्वीकार कर देता है — और उस workspace का एक hook उसके अपने हर tool को
deny करता है; जो hook fail हो वह भी deny करता है। Veles के file tools project के बाहर नहीं लिखते,
इसलिए agy उस hook को उनके ज़रिए दोबारा नहीं लिख सकता। `codex` भी project के बाहर चलता है, आपका codex
config अनदेखा करके, read-only sandbox के साथ और उसके अपने tools feature flags से बंद करके, जिनके
नाम Veles हर पहले run से पहले जाँचता है — जिस codex ने अपने इस्तेमाल का कोई flag rename कर दिया हो
उसे अस्वीकार कर दिया जाता है, खुला नहीं चलाया जाता। उसका MCP server उसके arguments में जाता है
(कोई config file नहीं), केवल उसी server के tools approve होते हैं, और उस server को मिलने वाला
environment नाम से forward किया जाता है — `VELES_TRUST_AUTO_ALLOW` कभी नहीं।

ज्ञात सीमाएँ:

- `run_shell` एक shell है: एक बार आप इसे grant कर दें (या autopilot में), यह ऊपर की किसी भी
  file को per-file confirmation के बिना लिख सकता है।
- MCP approval server की command line को pin करता है, उन files को नहीं जिन्हें वह project से
  चलाता है (`args` में नामित script) — उन्हें भी review करें।
- CLI provider के साथ, जो runs tools को केवल अपने लिए pre-authorise करते हैं (daemon background
  jobs, `veles research`) वे इसे delegated CLI तक नहीं पहुँचाते: pre-authorisation Veles process में
  रहता है, और CLI जो MCP server start करता है वह एक अलग process है, इसलिए उसके Veles tools को
  standing `veles trust set` grant या autopilot window चाहिए। parent run का planning mode भी उन तक
  नहीं पहुँचता।
- `antigravity-cli` इस पर निर्भर है कि agy अपने workspace की `.agents/hooks.json` का सम्मान करे;
  agy का कोई release जो workspace hooks पढ़ना बंद कर दे, `--dangerously-skip-permissions` के तहत
  उसके अपने tools को खुला छोड़ देगा।

control characters वाले paths (terminal escapes, bidi overrides) अस्वीकार किए जाते हैं, और
confirmations, trust prompt और diff preview ऐसे characters को escaped दिखाते हैं — कोई tool call
उस text को forge नहीं कर सकता जिसे आप approve करते हैं।

config के MCP servers तभी start होते हैं जब आप उन्हें approve करें — देखें
[external MCP servers](external-mcp-servers.md)।

# Veles को daemon के रूप में कैसे चलाएँ

> 🌐 **भाषाएँ:** [English](../../en/how-to/run-as-daemon.md) · [简体中文](../../zh-CN/how-to/run-as-daemon.md) · [繁體中文](../../zh-TW/how-to/run-as-daemon.md) · [日本語](../../ja/how-to/run-as-daemon.md) · [한국어](../../ko/how-to/run-as-daemon.md) · [Español](../../es/how-to/run-as-daemon.md) · [Français](../../fr/how-to/run-as-daemon.md) · [Italiano](../../it/how-to/run-as-daemon.md) · [Português (BR)](../../pt-BR/how-to/run-as-daemon.md) · [Português (PT)](../../pt-PT/how-to/run-as-daemon.md) · [Русский](../../ru/how-to/run-as-daemon.md) · [العربية](../../ar/how-to/run-as-daemon.md) · **हिन्दी** · [বাংলা](../../bn/how-to/run-as-daemon.md) · [Tiếng Việt](../../vi/how-to/run-as-daemon.md)

daemon एक वैकल्पिक, दीर्घजीवी HTTP+WS server है जो agent को एक API के रूप में उजागर
करता है — यह [channels](connect-telegram.md) (Telegram, …), scheduled
[jobs](long-running-tasks.md), और remote/headless उपयोग की नींव है।

## शुरू और बंद करना

```bash
veles daemon start              # detaches by default; binds 127.0.0.1:8765
veles daemon status             # is it running?
veles daemon stop               # SIGTERM via the pid file
```

`start` detach होकर आपका shell लौटा देता है। एक foreground process के लिए (systemd
`Type=simple`, Docker, debugging) `--foreground` दें। bind override करें:

```bash
veles daemon start --host 0.0.0.0 --port 9000
```

daemon का model और provider प्रोजेक्ट config से आते हैं और **उसके जीवनकाल भर fixed
रहते हैं** — उन्हें शुरू करने से पहले set करें:

```toml
# <project>/.veles/config.toml
[engine]
provider = "ollama"            # provider name
model = "qwen3:4b-instruct"   # model id
```

## Authentication tokens

API clients एक bearer token से authenticate होते हैं:

```bash
veles daemon token add tui-client     # mint a token
veles daemon token list               # list (masked)
veles daemon token remove tui-client
```

## daemon picker (TUI)

control panel खोलने के लिए बिना किसी subcommand के `veles daemon` चलाएँ — यह आपके
प्रोजेक्ट के daemons और प्रत्येक daemon के channels का एक tree है:

```
Project: my-project
  default   running  pid=…  up 1.2h  qwen3:4b-instruct
    chan: telegram
  api       stopped
Other projects
  other-proj  running
```

Keys: `Enter` किसी daemon का log खोलता है; `s`/`t`/`r` start/stop/restart; `d` delete;
`c`/`x` एक channel add/remove; `q` quit।

## प्रति प्रोजेक्ट कई daemons (नामित sessions)

एक प्रोजेक्ट एक साथ अलग-अलग models/ports वाले कई daemons चला सकता है। एक नामित session
घोषित करें, फिर उसे शुरू करें:

```bash
veles daemon session create api --port 8801 --provider anthropic --model claude-opus-4.8
veles daemon start --name api
veles daemon session list
```

प्रत्येक नामित session का अपना `[daemon.<name>]` config block और अपने channels
(`[daemon.<name>.channels.*]`) होते हैं।

## प्रोजेक्ट्स के पार daemons सूचीबद्ध करें

```bash
veles daemon list
veles daemon restart <project-or-slug>
veles daemon delete  <project-or-slug>
```

## आगे

- [एक Telegram channel जोड़ें](connect-telegram.md)
- [Jobs schedule करें](long-running-tasks.md)

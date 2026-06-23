# Veles को daemon के रूप में कैसे चलाएँ

> 🌐 **भाषाएँ:** **English** · [Русский](../../ru/how-to/run-as-daemon.md)

Daemon एक वैकल्पिक, लंबे समय तक चलने वाला HTTP+WS server है जो agent को एक API के
रूप में expose करता है — यह [channels](connect-telegram.md) (Telegram, …),
scheduled [jobs](long-running-tasks.md), और remote/headless उपयोग की नींव है।

## Start और stop

```bash
veles daemon start              # डिफ़ॉल्ट रूप से detach होता है; 127.0.0.1:8765 पर bind करता है
veles daemon status             # क्या यह चल रहा है?
veles daemon stop               # pid file के ज़रिए SIGTERM
```

`start` detach हो जाता है और आपका shell वापस कर देता है। एक foreground process के
लिए (systemd `Type=simple`, Docker, debugging) `--foreground` पास करें। Bind को
override करें:

```bash
veles daemon start --host 0.0.0.0 --port 9000
```

Daemon का मॉडल और provider project config से आते हैं और उसके **पूरे जीवनकाल के लिए
fixed** रहते हैं — start करने से पहले उन्हें सेट करें:

```toml
# <project>/.veles/config.toml
[provider]
default = "ollama:qwen3:4b-instruct"
```

## Authentication tokens

API clients एक bearer token से authenticate करते हैं:

```bash
veles daemon token add tui-client     # एक token बनाएँ
veles daemon token list               # सूची (masked)
veles daemon token remove tui-client
```

## Daemon picker (TUI)

बिना किसी subcommand के `veles daemon` चलाएँ ताकि control panel खुले — आपके
project के daemons और हर daemon के channels का एक tree:

```
Project: my-project
  default   running  pid=…  up 1.2h  qwen3:4b-instruct
    chan: telegram
  api       stopped
Other projects
  other-proj  running
```

Keys: `Enter` किसी daemon का log खोलता है; `s`/`t`/`r` start/stop/restart; `d`
delete; `c`/`x` एक channel जोड़ें/हटाएँ; `q` quit।

## प्रति project कई daemons (named sessions)

एक project एक साथ अलग-अलग models/ports के साथ कई daemons चला सकता है। एक named
session घोषित करें, फिर उसे start करें:

```bash
veles daemon session create api --port 8801 --provider anthropic --model claude-opus-4.8
veles daemon start --name api
veles daemon session list
```

प्रत्येक named session का अपना `[daemon.<name>]` config block और अपने channels
(`[daemon.<name>.channels.*]`) होते हैं।

## Projects के बीच daemons की सूची

```bash
veles daemon list
veles daemon restart <project-or-slug>
veles daemon delete  <project-or-slug>
```

## आगे

- [Telegram channel जोड़ें](connect-telegram.md)
- [Jobs schedule करें](long-running-tasks.md)

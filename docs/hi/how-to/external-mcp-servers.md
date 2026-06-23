# External MCP servers कैसे connect करें

> 🌐 **भाषाएँ:** [English](../../en/how-to/external-mcp-servers.md) · [简体中文](../../zh-CN/how-to/external-mcp-servers.md) · [繁體中文](../../zh-TW/how-to/external-mcp-servers.md) · [日本語](../../ja/how-to/external-mcp-servers.md) · [한국어](../../ko/how-to/external-mcp-servers.md) · [Español](../../es/how-to/external-mcp-servers.md) · [Français](../../fr/how-to/external-mcp-servers.md) · [Italiano](../../it/how-to/external-mcp-servers.md) · [Português (BR)](../../pt-BR/how-to/external-mcp-servers.md) · [Português (PT)](../../pt-PT/how-to/external-mcp-servers.md) · [Русский](../../ru/how-to/external-mcp-servers.md) · [العربية](../../ar/how-to/external-mcp-servers.md) · **हिन्दी** · [বাংলা](../../bn/how-to/external-mcp-servers.md) · [Tiếng Việt](../../vi/how-to/external-mcp-servers.md)

Veles एक [MCP](https://modelcontextprotocol.io/) **client** है: यह external MCP servers से
connect कर सकता है और उनके tools को agent के सामने ऐसे expose कर सकता है मानो वे built-in हों
(GitHub, library docs, web search, आपकी अपनी services, …)।

## एक server configure करें

`<project>/.veles/config.toml` (या user-global `~/.veles/config.toml`) में एक
`[mcp.servers.<name>]` block जोड़ें। `<name>` को
`[A-Za-z0-9][A-Za-z0-9_-]{0,31}` से मेल खाना चाहिए — यह हर tool के नाम का हिस्सा बन जाता है।
तीन transports समर्थित हैं: `stdio` (default), `http`, `sse`।

| Key | Transport | Default | Purpose |
|---|---|---|---|
| `transport` | — | `"stdio"` | `stdio` \| `http` \| `sse` |
| `command` | stdio (required) | — | launch करने वाला executable — **सिर्फ़ program, उसके arguments नहीं** |
| `args` | stdio | `[]` | argument list, प्रति item एक token |
| `env` | stdio | `{}` | subprocess के लिए अतिरिक्त environment (inherited env के ऊपर merged) |
| `url` | http/sse (required) | — | server endpoint |
| `timeout_s` | — | `120` | एक single tool call के लिए budget |
| `connect_timeout_s` | — | `30` | शुरुआती connection के लिए budget |
| `enabled` | — | `true` | entry रखने पर connect न करने के लिए `false` सेट करें |

`command`, `args`, `env`, और `url` के string values environment से `${VAR}` को
interpolate करते हैं (unset variable warning के साथ खाली string बन जाता है) — secrets को
file से बाहर रखें।

> **`command` बनाम `args`.** Veles program को सीधे चलाता है (कोई shell नहीं), इसलिए
> executable और उसके arguments **अलग-अलग** fields हैं। लिखें
> `command = "npx"`, `args = ["-y", "pkg"]` — **न कि** `command = "npx -y pkg"`।

### stdio (local subprocess)

```toml
[mcp.servers.github]
transport = "stdio"
command = "npx"
args = ["-y", "@modelcontextprotocol/server-github"]
env = { GITHUB_TOKEN = "${GITHUB_TOKEN}" }
```

आपका खुद चलाया गया server भी इसी तरह काम करता है — `command`/`args` को उस पर point करें:

```toml
[mcp.servers.mytools]
transport = "stdio"
command = "python"
args = ["-m", "my_mcp_server"]
```

### एक server जिसे API key चाहिए (context7)

[Context7](https://context7.com) up-to-date library documentation देता है। key को
एक argument के रूप में पास करें ताकि `${VAR}` इसे file से बाहर रखे:

```toml
[mcp.servers.context7]
transport = "stdio"
command = "npx"
args = ["-y", "@upstash/context7-mcp", "--api-key", "${CONTEXT7_API_KEY}"]
```

```bash
export CONTEXT7_API_KEY=...   # then start veles
```

### http / sse (remote)

```toml
[mcp.servers.search]
transport = "http"            # streamable HTTP; use "sse" for an SSE endpoint
url = "https://mcp.example.com/mcp"
```

> **अभी कोई custom headers नहीं।** `http`/`sse` transports सिर्फ़ `url` भेजते हैं —
> Veles कोई `Authorization` header attach नहीं कर सकता। ऐसे remote server के लिए जिसे
> key चाहिए, उसका `stdio` (जैसे `npx`) variant `args`/`env` में key के साथ इस्तेमाल करना बेहतर है, या ऐसा
> endpoint जो URL में key स्वीकार करे।

## specific tools छिपाएँ

`[mcp] disabled_tools` सेट करें — एक table जो हर server को skip किए जाने वाले tool नामों से map करती है:

```toml
[mcp]
disabled_tools = { github = ["delete_repository"], search = ["raw_query"] }
```

## निरीक्षण और test

```bash
veles mcp list              # every configured server: transport, status, tool count
veles mcp test github       # connect to one server and list its tools
```

`veles mcp list` हमेशा 0 के साथ exit करता है — यह एक inspector है, health gate नहीं।
`veles mcp test` connection fail होने पर 1 और अज्ञात server name के लिए 2 के साथ exit करता है।

## tools कैसे दिखते हैं

एक बार configure होने पर, servers अगले `veles run` / TUI / daemon start पर
**अपने आप** mount हो जाते हैं — कोई अलग "enable MCP" flag नहीं है, config की मौजूदगी ही
switch है। हर tool normal registry में `mcp_<server>_<tool>` के रूप में आता है
और agent द्वारा किसी भी builtin की तरह callable होता है। Schemas sanitise की जाती हैं
(name/length limits, control-char stripping) ताकि कोई untrusted server prompt में inject न कर सके।
Tool hints trust ladder से map होते हैं: destructive tools हमेशा confirm करते हैं, read-only
tools बिना prompt के चलते हैं, बाकी सब सामान्य
[trust](security-and-permissions.md) flow से गुज़रते हैं — अगर आप हर बार पूछा जाना नहीं चाहते तो
`veles trust set` के साथ standing approval दें।

## विफलता संभालना

connect करने में fail होने वाला server — किसी missing `command`, गलत `url`, या किसी भी invalid
entry के कारण — warning के रूप में log होता है और skip कर दिया जाता है। यह कभी startup या agent को block नहीं करता।
status और error देखने के लिए `veles mcp list` दोबारा चलाएँ।

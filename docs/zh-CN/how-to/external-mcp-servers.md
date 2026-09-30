# 如何接入外部 MCP 服务器

> 🌐 **语言：** [English](../../en/how-to/external-mcp-servers.md) · **简体中文** · [繁體中文](../../zh-TW/how-to/external-mcp-servers.md) · [日本語](../../ja/how-to/external-mcp-servers.md) · [한국어](../../ko/how-to/external-mcp-servers.md) · [Español](../../es/how-to/external-mcp-servers.md) · [Français](../../fr/how-to/external-mcp-servers.md) · [Italiano](../../it/how-to/external-mcp-servers.md) · [Português (BR)](../../pt-BR/how-to/external-mcp-servers.md) · [Português (PT)](../../pt-PT/how-to/external-mcp-servers.md) · [Русский](../../ru/how-to/external-mcp-servers.md) · [العربية](../../ar/how-to/external-mcp-servers.md) · [हिन्दी](../../hi/how-to/external-mcp-servers.md) · [বাংলা](../../bn/how-to/external-mcp-servers.md) · [Tiếng Việt](../../vi/how-to/external-mcp-servers.md)

Veles 是一个 [MCP](https://modelcontextprotocol.io/) **客户端**：它可以连接到外部 MCP 服务器，并把它们的工具暴露给智能体，就好像这些工具是内置的一样（GitHub、库文档、网络搜索、你自己的服务……）。

## 配置一个服务器

在 `<project>/.veles/config.toml`（或用户全局的 `~/.veles/config.toml`）中添加一个 `[mcp.servers.<name>]` 块。`<name>` 必须匹配 `[A-Za-z0-9][A-Za-z0-9_-]{0,31}`——它会成为每个工具名称的一部分。支持三种传输方式：`stdio`（默认）、`http`、`sse`。

| 键 | 传输方式 | 默认值 | 用途 |
|---|---|---|---|
| `transport` | — | `"stdio"` | `stdio` \| `http` \| `sse` |
| `command` | stdio（必填） | — | 要启动的可执行程序——**只填程序本身，不含参数** |
| `args` | stdio | `[]` | 参数列表，每项一个 token |
| `env` | stdio | `{}` | 子进程的额外环境变量（合并叠加在继承的环境之上） |
| `url` | http/sse（必填） | — | 服务器端点 |
| `timeout_s` | — | `120` | 单次工具调用的预算 |
| `connect_timeout_s` | — | `30` | 初始连接的预算 |
| `enabled` | — | `true` | 设为 `false` 可保留该条目但跳过连接 |

`command`、`args`、`env` 和 `url` 中的字符串值会从环境插值 `${VAR}`（未设置的变量会变成空字符串并给出警告）——请把密钥放在文件之外。

> **`command` 与 `args`。** Veles 直接运行程序（不经过 shell），因此可执行程序及其参数是**分开的**字段。要写成 `command = "npx"`，`args = ["-y", "pkg"]`——**而不是** `command = "npx -y pkg"`。

### stdio（本地子进程）

```toml
[mcp.servers.github]
transport = "stdio"
command = "npx"
args = ["-y", "@modelcontextprotocol/server-github"]
env = { GITHUB_TOKEN = "${GITHUB_TOKEN}" }
```

你自己运行的服务器也以同样方式工作——让 `command`/`args` 指向它即可：

```toml
[mcp.servers.mytools]
transport = "stdio"
command = "python"
args = ["-m", "my_mcp_server"]
```

### 需要 API 密钥的服务器（context7）

[Context7](https://context7.com) 提供最新的库文档。将密钥作为参数传入，这样 `${VAR}` 能让它留在文件之外：

```toml
[mcp.servers.context7]
transport = "stdio"
command = "npx"
args = ["-y", "@upstash/context7-mcp", "--api-key", "${CONTEXT7_API_KEY}"]
```

```bash
export CONTEXT7_API_KEY=...   # then start veles
```

### http / sse（远程）

```toml
[mcp.servers.search]
transport = "http"            # streamable HTTP; use "sse" for an SSE endpoint
url = "https://mcp.example.com/mcp"
```

> **暂不支持自定义请求头。** `http`/`sse` 传输只发送 `url`——Veles 无法附加 `Authorization` 请求头。对于需要密钥的远程服务器，优先使用其 `stdio`（例如 `npx`）变体并把密钥放在 `args`/`env` 中，或使用一个接受在 URL 中携带密钥的端点。

## 隐藏特定工具

设置 `[mcp] disabled_tools`——一个把每个服务器映射到要跳过的工具名称的表：

```toml
[mcp]
disabled_tools = { github = ["delete_repository"], search = ["raw_query"] }
```

## 批准、检查与测试

```bash
veles mcp approve github    # review the recipe, type `yes` — the server may now start
veles mcp list              # every configured server: transport, approved, status, tool count
veles mcp test github       # connect to one server and list its tools
```

服务器只有在你批准了它的确切配方后才会启动。`veles mcp approve` 会显示整张表——`command`、`args`、`env` 的值（其中的 `PATH` 决定运行哪个二进制文件；`${VAR}` 引用按原样显示）、`url`、`transport` 以及其他任何键——并记录 `config.toml` 中该表原样内容的哈希，即在 `${VAR}` 展开之前计算，因此轮换令牌不会使批准失效，而对该表的任何修改（克隆来的项目、改动过的参数）都会使服务器变为 `changed`，在你重新批准之前不会启动。批准只覆盖命令行；它从项目中运行的文件（`args` 里的脚本）不会被固定——也请审查它们。批准记录保存在 `~/.veles/mcp-approvals.json`。安装 MCP 扩展的 `veles registry install` 会在确认时显示同样的配方并完成批准；`veles registry uninstall` 会撤销批准。

`veles mcp list` 始终以 0 退出——它是一个检查器，而非健康门禁；它绝不会启动未批准的服务器。当服务器未批准或连接失败时 `veles mcp test` 以 1 退出，当服务器名称未知时以 2 退出。

## 工具如何出现

配置并批准后，服务器会在下一次 `veles run` / TUI / 守护进程启动时**自动**挂载——没有单独的“启用 MCP”开关。未批准的服务器会被跳过，每个进程只给出一次警告。每个工具以 `mcp_<server>_<tool>` 的形式进入正常的注册表，可由智能体像任何内置工具一样调用。Schema 会经过净化（名称/长度限制、控制字符剥离），这样不受信任的服务器无法注入到提示中。工具提示会映射到信任阶梯：破坏性工具始终需要确认，只读工具无需提示，其余一切走常规的[信任](security-and-permissions.md)流程——如果你不想每次都被询问，可用 `veles trust set` 授予长期批准。

## 故障处理

连接失败的服务器——缺少 `command`、错误的 `url`，或任何无效条目——会被记录为警告并跳过。它绝不会阻塞启动或智能体。重新运行 `veles mcp list` 即可查看状态和错误。

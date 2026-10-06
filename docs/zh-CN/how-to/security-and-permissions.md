# 如何管理安全：信任、自动驾驶、密钥

> 🌐 **语言：** [English](../../en/how-to/security-and-permissions.md) · **简体中文** · [繁體中文](../../zh-TW/how-to/security-and-permissions.md) · [日本語](../../ja/how-to/security-and-permissions.md) · [한국어](../../ko/how-to/security-and-permissions.md) · [Español](../../es/how-to/security-and-permissions.md) · [Français](../../fr/how-to/security-and-permissions.md) · [Italiano](../../it/how-to/security-and-permissions.md) · [Português (BR)](../../pt-BR/how-to/security-and-permissions.md) · [Português (PT)](../../pt-PT/how-to/security-and-permissions.md) · [Русский](../../ru/how-to/security-and-permissions.md) · [العربية](../../ar/how-to/security-and-permissions.md) · [हिन्दी](../../hi/how-to/security-and-permissions.md) · [বাংলা](../../bn/how-to/security-and-permissions.md) · [Tiếng Việt](../../vi/how-to/security-and-permissions.md)

Veles 将危险操作置于**信任阶梯**之后进行管控，对文件访问做沙箱隔离，
并将密钥保存在操作系统钥匙串中。关于其设计原理，参见
[信任与沙箱](../explanation/trust-and-sandbox.md)。

## 信任阶梯

敏感工具（`run_shell`、`write_file`、`fetch_url` 等）在运行前会先征求许可。
你可以选择：**仅此一次**允许、**对本项目始终**允许、**在所有地方始终**允许，
或**拒绝**。授权会被持久化，因此不会再次询问你。

无需等待提示即可管理授权：

```bash
veles trust list                          # 当前授权（用户 + 项目）
veles trust set run_shell --scope project # 为本项目预先授权
veles trust set write_file --scope user   # 在所有地方预先授权
veles trust revoke run_shell              # 移除一项授权
veles trust clear --scope all             # 清空所有
```

某些操作即使已授权也**始终需要确认** —— 删除文件、抓取
URL、安装新的技能/工具/模块、连接频道，以及写入到项目之外。

## 自动驾驶 —— 一个限时的绕过窗口

对于无人值守的运行（例如通宵的批处理），可以开启一个让信任提示
自动放行的窗口：

```bash
veles autopilot enable --until +2h
veles autopilot enable --until 2026-12-31T23:00:00Z
veles autopilot status
veles autopilot disable
```

自动驾驶模式下的每一个操作都会被记录下来以便日后审查。非交互式环境
（守护进程、批处理）在自动驾驶未激活时默认拒绝。

## 密钥

API 密钥和机器人令牌保存在操作系统钥匙串中，绝不写入配置文件：

```bash
veles secret set OPENROUTER_API_KEY       # 提示输入（或通过 stdin 传入）
veles secret list                         # 已配置了哪些密钥
veles secret get OPENROUTER_API_KEY --reveal
veles secret delete OPENROUTER_API_KEY
veles secret set OPENROUTER_API_KEY --project myproj   # 仅用于某个项目的密钥
```

除非你传入 `--no-env-fallback`，否则查找会回退到对应的
[环境变量](../reference/environment-variables.md)。

## 沙箱

工具可以读取激活项目内部、`~/.veles/skills/` 和 `~/.veles/locales/` 的内容，
并且只能写入项目内部——若布局声明了可写区域，则只能写入这些区域。对于高级配置，可用
`VELES_SANDBOX_ROOTS`（以 `:` 分隔）来覆盖这些根目录。URL 抓取会维护一份
SSRF 拒绝列表；`VELES_FETCH_ALLOW_PRIVATE=1` 可解除对私有网络的封锁。

在项目的 `.veles/` 内部，智能体的文件工具只能写入 `skills/`、`tools/`、`tmp/`、
`plans/`、`memory/` 和 `artifacts/`。其余一切——`trust.json`、`config.toml`、
`project.toml`、`modules/`、`wiki.toml`、`memory.db`——只能通过 `veles` 命令和
Veles 自己的工具修改。文件工具还会拒绝项目中任何其他 `.veles/` 目录（子项目的，
或智能体在 `wiki/` 中植入的），无论嵌套多深。因此智能体无法通过文件工具授予自己信任，
也无法添加 Veles 会运行的代码（它写入 `.veles/tools/` 的工具只有在你批准其文件后才会加载）。
同一文件的其他写法（大小写、`..`、符号链接）同样会被拒绝。

无需显式命令就会运行、或会左右智能体 CLI 的文件——`.git/`、`.githooks/`、`.claude/`、
`.gemini/`、`.agents/`、`.codex/`、`.vscode/`、`.devcontainer/`、`.husky/` 下的任何内容，以及任意深度的
`.envrc`、`.mcp.json`、`.pre-commit-config.yaml`、`lefthook.yml`，外加仓库的
`core.hooksPath` 目录以及符号链接的 `.git` 所指向的位置——智能体的文件工具只有在你确认该次写入后才会写入。
信任授权和 autopilot 都不涵盖这一点；守护进程会在频道中询问，而无人可问的批处理运行则会拒绝。

`claude-cli`、`codex` 和 `antigravity-cli` 提供方仅以只带 Veles 工具的模型身份运行：它们自带的
shell、文件编辑和网络工具、项目的 `.claude/` 设置和钩子，以及其他 MCP 服务器都不适用，
并且它们调用的每个 Veles 工具都要经过上述信任阶梯（那里没人能回答提示，因此任何尚未授予的操作都会被拒绝）。
它们的 MCP 配置位于 `.veles/tmp/delegate-<pid>/` 中，每个运行中的进程一份，智能体的文件工具无法写入该目录。`agy` 在项目之外、
`~/.veles/tmp/` 下的临时工作区里运行，因此项目自己的 `.agents/` 钩子和 MCP 服务器不会触及它。
它在拥有 Veles 的工具时会带上 `--dangerously-skip-permissions`——否则 agy 在无界面模式下会拒绝 MCP 调用——
并且该工作区中的一个钩子会拒绝它自带的每个工具；钩子本身失败时同样会拒绝。Veles 的文件工具无法在项目之外写入，
因此 agy 无法通过它们改写该钩子。`codex` 同样在项目之外运行，忽略你的 codex 配置，使用只读沙箱，
并通过功能标志关闭它自带的工具；Veles 在每次首次运行前都会检查这些标志的名称——重命名了它所依赖标志的
codex 会被拒绝，而不是在开放状态下运行。它的 MCP 服务器通过参数传入（没有配置文件），只批准该服务器的工具，
并且该服务器获得的环境变量按名称转发——绝不会包含 `VELES_TRUST_AUTO_ALLOW`。

已知限制：

- `run_shell` 就是一个 shell：一旦你授予它（或处于 autopilot 下），它就能在没有逐文件确认的情况下写入上述任何文件——以及 `~/.veles/` 中的批准存储。`veles … approve` 需要终端或已审阅的哈希（`--sha256`），并会拒绝由 agent 的 shell 启动的命令，但获得授权的 shell 可以抹掉该标记或直接写入这些文件。
- MCP 批准固定的是服务器的命令行，而不是它从项目中运行的文件（`args` 中指定的脚本）——也请审查这些文件。
- 使用 CLI 提供方时，仅为自身预先授权工具的运行（守护进程后台作业、`veles research`）不会把授权传递给被委派的 CLI：
  预先授权存在于 Veles 进程中，而该 CLI 启动的 MCP 服务器是另一个独立进程，因此其 Veles 工具需要长期的
  `veles trust set` 授权或 autopilot 窗口。父运行的规划模式同样不会传递给它们。
- `antigravity-cli` 依赖 agy 遵守其工作区的 `.agents/hooks.json`；如果某个 agy 版本不再读取工作区钩子，
  它自带的工具在 `--dangerously-skip-permissions` 下就会处于开放状态。

包含控制字符（终端转义、双向覆盖）的路径会被拒绝，确认、信任提示和 diff 预览会以转义形式显示此类字符——
工具调用无法伪造你所批准的文本。

配置中的 MCP 服务器只有在你批准后才会启动——参见
[外部 MCP 服务器](external-mcp-servers.md#批准检查与测试)。

# 如何管理安全：信任、自动驾驶、密钥

> 🌐 **Languages:** **English** · [Русский](../../ru/how-to/security-and-permissions.md)

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
```

除非你传入 `--no-env-fallback`，否则查找会回退到对应的
[环境变量](../reference/environment-variables.md)。

## 沙箱

工具可以读取激活项目内部以及 `~/.veles/` 的内容，并且只能写入到布局的
可写区域（默认是 `wiki/`、`.veles/`）。对于高级配置，可用
`VELES_SANDBOX_ROOTS`（以 `:` 分隔）来覆盖这些根目录。URL 抓取会维护一份
SSRF 拒绝列表；`VELES_FETCH_ALLOW_PRIVATE=1` 可解除对私有网络的封锁。

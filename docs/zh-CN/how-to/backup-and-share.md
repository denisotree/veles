# 如何备份和分享项目

> 🌐 **语言：** [English](../../en/how-to/backup-and-share.md) · [Русский](../../ru/how-to/backup-and-share.md) · **简体中文**

Veles 项目是可移植的。你可以将项目导出为单个 `.tar.gz` 包用于备份或迁移，也可以导出一份经过脱敏处理的模板，在不泄露你的数据的前提下分享。

## 完整备份

打包整个项目（`.veles/` + `AGENTS.md`），排除运行时的临时数据（锁文件、预算状态）：

```bash
veles export full ./my-project-backup.tar.gz
```

在任意位置恢复：

```bash
veles import ./my-project-backup.tar.gz                # into cwd
veles import ./my-project-backup.tar.gz --into ./restored
veles import ./my-project-backup.tar.gz --force        # overwrite an existing .veles/
```

完整备份包含你的 `memory.db`（会话、洞见），因此请将其视为私密数据。

## 可分享的模板

只打包可复用的脚手架部分——schema、技能、模块以及非会话的 wiki 页面。它会**剥离** `memory.db`、`sources/`、`sessions/`、信任授权，并对文本做 PII 脱敏：

```bash
veles export template ./my-template.tar.gz
```

把模板交给同事；他们用 `veles import` 导入后，即可获得你的结构和技能，而不会得到你的对话历史或原始来源。

## 该用哪一个

| 目标 | 命令 |
|---|---|
| 完整备份 / 迁移项目 | `veles export full` |
| 分享结构 + 技能，但不含数据 | `veles export template` |

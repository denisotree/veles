# 如何備份與分享專案

> 🌐 **語言：** **English** · [Русский](../../ru/how-to/backup-and-share.md)

Veles 專案是可攜的。你可以把專案匯出成單一的 `.tar.gz` 套件以供
備份或遷移，或匯出成一份去敏感化的範本，以便分享而不外洩你的資料。

## 完整備份

打包整個專案（`.veles/` + `AGENTS.md`），扣除執行期的暫存物（locks、
budget 狀態）：

```bash
veles export full ./my-project-backup.tar.gz
```

在任何地方還原它：

```bash
veles import ./my-project-backup.tar.gz                # into cwd
veles import ./my-project-backup.tar.gz --into ./restored
veles import ./my-project-backup.tar.gz --force        # overwrite an existing .veles/
```

完整套件包含你的 `memory.db`（sessions、insights），因此請把它當作
私密資料看待。

## 可分享的範本

只打包可重複使用的骨架——schema、skills、modules，以及非 session 的
wiki 頁面。它會**剝除** `memory.db`、`sources/`、`sessions/`、信任授權，並
對文字進行 PII 去識別化：

```bash
veles export template ./my-template.tar.gz
```

把範本交給同事；他們用 `veles import` 匯入後，就能取得你的結構
與 skills，而不會拿到你的對話歷史或原始來源。

## 該用哪一個

| 目標 | 指令 |
|---|---|
| 完整備份／搬移專案 | `veles export full` |
| 分享結構 + skills，但不含資料 | `veles export template` |

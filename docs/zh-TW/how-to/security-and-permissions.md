# 如何管理安全性：trust、autopilot、secrets

> 🌐 **語言：** **English** · [Русский](../../ru/how-to/security-and-permissions.md)

Veles 透過 **trust ladder（信任階梯）** 把關危險操作、對檔案存取進行沙箱化，
並將 secrets 保存在作業系統的 keychain 中。其背後的理念請參閱
[trust 與沙箱](../explanation/trust-and-sandbox.md)。

## trust ladder（信任階梯）

敏感工具（`run_shell`、`write_file`、`fetch_url` 等）在執行前會先詢問。
你可以選擇：允許**一次**、**永遠允許此專案**、**永遠允許所有地方**，或
**拒絕**。授權會被保留，因此不會再次詢問你。

不必等到出現提示，也能管理授權：

```bash
veles trust list                          # current grants (user + project)
veles trust set run_shell --scope project # pre-grant for this project
veles trust set write_file --scope user   # pre-grant everywhere
veles trust revoke run_shell              # remove a grant
veles trust clear --scope all             # wipe everything
```

有些操作即使已授權也**始終會再次確認**——刪除檔案、抓取
URL、安裝新的 skill／tool／module、連接 channel，以及寫入
專案以外的位置。

## autopilot——有時限的旁路

對於無人值守的執行（例如過夜的批次作業），可以開一個讓 trust 提示
自動允許的時間窗：

```bash
veles autopilot enable --until +2h
veles autopilot enable --until 2026-12-31T23:00:00Z
veles autopilot status
veles autopilot disable
```

每一次 autopilot 操作都會被記錄下來以供事後檢視。非互動式情境
（daemon、批次）在 autopilot 未啟用時預設一律拒絕。

## Secrets

API 金鑰與 bot token 存放於作業系統的 keychain，絕不會寫進設定檔：

```bash
veles secret set OPENROUTER_API_KEY       # prompts (or pipe via stdin)
veles secret list                         # which secrets are configured
veles secret get OPENROUTER_API_KEY --reveal
veles secret delete OPENROUTER_API_KEY
```

查找時會退而求其次使用對應的[環境變數](../reference/environment-variables.md)，
除非你傳入 `--no-env-fallback`。

## 沙箱

工具可以讀取使用中專案內部與 `~/.veles/` 的內容，而只能寫入
該 layout 的可寫區域（預設為 `wiki/`、`.veles/`）。進階情境可用
`VELES_SANDBOX_ROOTS`（以 `:` 分隔）覆寫這些根目錄。URL 抓取維持一份
SSRF 拒絕清單；`VELES_FETCH_ALLOW_PRIVATE=1` 會解除對私有網路的封鎖。

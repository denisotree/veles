# 如何管理安全性：trust、autopilot、secrets

> 🌐 **語言：** [English](../../en/how-to/security-and-permissions.md) · [简体中文](../../zh-CN/how-to/security-and-permissions.md) · **繁體中文** · [日本語](../../ja/how-to/security-and-permissions.md) · [한국어](../../ko/how-to/security-and-permissions.md) · [Español](../../es/how-to/security-and-permissions.md) · [Français](../../fr/how-to/security-and-permissions.md) · [Italiano](../../it/how-to/security-and-permissions.md) · [Português (BR)](../../pt-BR/how-to/security-and-permissions.md) · [Português (PT)](../../pt-PT/how-to/security-and-permissions.md) · [Русский](../../ru/how-to/security-and-permissions.md) · [العربية](../../ar/how-to/security-and-permissions.md) · [हिन्दी](../../hi/how-to/security-and-permissions.md) · [বাংলা](../../bn/how-to/security-and-permissions.md) · [Tiếng Việt](../../vi/how-to/security-and-permissions.md)

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
veles secret set OPENROUTER_API_KEY --project myproj   # a key for one project only
```

查找時會退而求其次使用對應的[環境變數](../reference/environment-variables.md)，
除非你傳入 `--no-env-fallback`。

## 沙箱

工具可以讀取使用中專案內部、`~/.veles/skills/` 與 `~/.veles/locales/` 的內容，
而只能寫入專案內部 — 若 layout 宣告了可寫區域，則只能寫入這些區域。進階情境可用
`VELES_SANDBOX_ROOTS`（以 `:` 分隔）覆寫這些根目錄。URL 抓取維持一份
SSRF 拒絕清單；`VELES_FETCH_ALLOW_PRIVATE=1` 會解除對私有網路的封鎖。

在專案的 `.veles/` 內部，agent 的檔案工具只能寫入 `skills/`、`tools/`、`tmp/`、
`plans/`、`memory/` 與 `artifacts/`。其餘一切 — `trust.json`、`config.toml`、
`project.toml`、`modules/`、`wiki.toml`、`memory.db` — 只能透過 `veles` 指令與
Veles 自己的工具修改。檔案工具也會拒絕專案中任何其他 `.veles/` 目錄（子專案的，
或 agent 在 `wiki/` 中植入的），無論巢狀多深。因此 agent 無法透過檔案工具授予自己信任，
也無法加入 Veles 會執行的程式碼（它寫入 `.veles/tools/` 的 tool 只有在你核可其檔案後才會載入）。
同一檔案的其他寫法（大小寫、`..`、符號連結）同樣會被拒絕。

無需明確指令就會執行、或會左右 agent CLI 的檔案 — `.git/`、`.githooks/`、`.claude/`、
`.gemini/`、`.codex/`、`.vscode/`、`.devcontainer/`、`.husky/` 底下的任何內容，以及任意深度的
`.envrc`、`.mcp.json`、`.pre-commit-config.yaml`、`lefthook.yml`，加上儲存庫的
`core.hooksPath` 目錄以及符號連結的 `.git` 所指向的位置 — agent 的檔案工具只有在你確認該次寫入後才會寫入。
信任授權與 autopilot 都不涵蓋這一點；daemon 會在頻道中詢問，而無人可問的批次執行則會拒絕。

`claude-cli` 與 `gemini-cli` provider 僅以只帶 Veles 工具的模型身分執行：它們自帶的
shell、檔案編輯與網路工具、專案的 `.claude/` 設定與 hooks，以及其他 MCP 伺服器都不適用，
而且它們呼叫的每個 Veles 工具都要經過上述 trust ladder（那裡沒人能回答提示，因此任何尚未授予的操作都會被拒絕）。

已知限制：

- `run_shell` 就是一個 shell：一旦你授予它（或處於 autopilot 之下），它就能在沒有逐檔確認的情況下寫入上述任何檔案。
- MCP 核可固定的是伺服器的命令列，而不是它從專案中執行的檔案（`args` 中指定的腳本）— 也請審查這些檔案。
- 使用 CLI provider 時，僅為自身預先授權工具的執行（daemon 背景工作、`veles research`）不會把授權傳遞給被委派的 CLI：
  其 Veles 工具需要常駐的 `veles trust set` 授權或 autopilot 視窗。父執行的規劃模式同樣不會傳遞給它們。
- `gemini-cli` 會在其執行期間信任專案資料夾，因此 gemini 也會讀取專案的 `.env` — 請把你不希望 agent 左右的 gemini 設定放在它之外。
- 在帶有受管（系統層級）gemini 政策的機器上，gemini 會忽略 Veles 傳入的政策，因此那裡的 `gemini-cli` 不再僅限於 Veles 的工具。

包含控制字元（終端機跳脫序列、雙向覆寫）的路徑會被拒絕，確認、信任提示與 diff 預覽會以跳脫形式顯示這類字元 —
tool 呼叫無法偽造你所核可的文字。

設定中的 MCP 伺服器只有在你核可後才會啟動 — 參見
[外部 MCP 伺服器](external-mcp-servers.md#核可檢視與測試)。

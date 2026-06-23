# 信任機制與 sandbox

> 🌐 **語言：** [English](../../en/explanation/trust-and-sandbox.md) · [简体中文](../../zh-CN/explanation/trust-and-sandbox.md) · **繁體中文** · [日本語](../../ja/explanation/trust-and-sandbox.md) · [한국어](../../ko/explanation/trust-and-sandbox.md) · [Español](../../es/explanation/trust-and-sandbox.md) · [Français](../../fr/explanation/trust-and-sandbox.md) · [Italiano](../../it/explanation/trust-and-sandbox.md) · [Português (BR)](../../pt-BR/explanation/trust-and-sandbox.md) · [Português (PT)](../../pt-PT/explanation/trust-and-sandbox.md) · [Русский](../../ru/explanation/trust-and-sandbox.md) · [العربية](../../ar/explanation/trust-and-sandbox.md) · [हिन्दी](../../hi/explanation/trust-and-sandbox.md) · [বাংলা](../../bn/explanation/trust-and-sandbox.md) · [Tiếng Việt](../../vi/explanation/trust-and-sandbox.md)

Veles 會在你的機器上執行一個自主的 agent，因此它會限制該 agent
能做的事。有兩套機制協同運作：用於敏感動作的**信任階梯（trust ladder）**與
用於檔案系統的 **sandbox**。若需相關指令，請參閱
[安全性與權限](../how-to/security-and-permissions.md)。

## 信任階梯

並非每個 tool 都同等對待。讀取檔案無害；執行 shell 指令或
寫入磁碟則不然。敏感的 tools（`run_shell`、`write_file`、`fetch_url`……）
會在執行前停下並詢問，提供四種選擇：

- **Once（這一次）**——僅允許這一次呼叫。
- **Always for this project（本專案永遠允許）**——保存一項專案範圍的授權。
- **Always everywhere（到處都允許）**——保存一項使用者範圍的授權。
- **Refuse（拒絕）**——拒絕它。

授權會被儲存下來，因此你不會被再次詢問。這給了你分級的控制：
信任某個 tool 一次、在某個專案中、或全域信任——任你選擇，在它
第一次重要的時候做出決定。

### 永遠需要確認的動作

有些操作風險高到 Veles 即使**已有授權仍會確認**：
刪除檔案、抓取 URL、安裝新的 skill/tool/module、連接一個
channel，以及寫入專案之外。這些動作對外或難以復原，
因此一項長期授權不應在無聲中涵蓋它們。

### 非互動式的安全機制

在 daemon、批次或其他非 TTY 的情境中，沒有人類可以接受提示，因此 Veles
預設會**拒絕**敏感動作——避免任意的 stdin 偷偷送出核可。若要刻意
無人值守地執行，請開啟一段 [autopilot](../how-to/security-and-permissions.md#autopilot--a-time-boxed-bypass)
時段；每一個 autopilot 動作都會被記錄以供檢視。

## 檔案系統 sandbox

一道 path guard 會限制 tools 能讀寫的範圍：

- **讀取**——在當前作用中的專案（及其子專案）內，外加 `~/.veles/`。
- **寫入**——僅限該 layout 的可寫區域（例如 `wiki/`）；`.veles/` 永遠
  可寫，以存放機器狀態。

逃出 sandbox 的 symlink 會被拒絕，而 `..` 走訪會在解析前就被拒絕。
URL 抓取會維持一份 SSRF 拒絕清單。進階設定可以用 `VELES_SANDBOX_ROOTS`
覆寫根目錄，或以 `VELES_FETCH_ALLOW_PRIVATE=1` 解除私有網路的封鎖——
兩者皆為選擇性啟用。

## 為何如此設計

目標是**有用的自主性，且沒有討厭的意外**：agent 可以做真正的工作，
而不必在每次讀取時都跳出提示，但任何可能損害你機器、花錢，
或離開這台機器的動作都會被把關——一次，然後依你的偏好被記住。

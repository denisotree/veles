# 作為累積能力的 skills 與 tools

> 🌐 **語言：** **English** · [Русский](../../ru/explanation/skills-and-tools.md)

Veles 以一組最小的 tools 與 skills 啟動，並在運作過程中持續**成長**。
本頁說明兩者的差異，以及它們如何累積。若需相關指令，請參閱
[管理 skills 與 tools](../how-to/manage-skills-and-tools.md)。

## tools 與 skills 的差別

- **tool** 是單一可執行的動作——讀取檔案、執行 shell 指令、
  抓取 URL、搜尋網路、寫一頁 wiki。tools 是模型實際呼叫的對象。
- **skill** 是一個被形式化的*流程*——一份 `SKILL.md`，包含 prompt 主體與
  一份允許使用的 tool 清單，並以一個聚焦的 sub-agent 形式執行。skills 把多個 tools
  組合成可重複執行的工作流（例如 LLM-Wiki 的 `ingest`/`query`/`lint`）。

## 最小啟動，按需擴充

Veles 以剛好足以發揮作用的配置啟動，並搭配一個已知的來源處可以拉取更多能力。
安裝額外項目（一個 skill、一個 tool、一個 module）預設會徵求核可；你也可以
授予長期自主權。如此能讓全新專案保持精簡，同時又能在需要的地方擴增能力。

## 能力如何累積

1. **Veles 撰寫自己的 tools。** 當它注意到某項任務反覆出現時，便能將一個
   乾淨、具型別、可重複使用的 Python tool 撰寫到 `<project>/.veles/tools/`（並經過
   advisor 的程式碼審查流程）。該 tool 會帶著 telemetry 加入 registry。
2. **重複的流程成為 skills。** pattern detector 會偵測反覆出現的 tool
   序列，並提議將其形式化為一個 skill；skill 可以 `extends:`
   另一個 skill 來繼承其主體與 tools。
3. **telemetry 驅動排名。** 每個 tool/skill 都帶有使用次數／成功次數／錯誤
   次數。這些資料會餵給去重（`veles skill dedup`）與晉升建議。

## 兩種範圍，可互相晉升

tools 與 skills 都存在於兩個層級：

- **專案本地**（`<project>/.veles/`）——僅在此處可見。
- **使用者全域**（`~/.veles/`）——在每個專案中皆可使用。

在某個專案中證明自己價值的能力，可以被**晉升**到使用者範圍，讓
所有專案都受益（`veles skill promote`、`veles tool promote`），或**降級**
回去。這正是 Veles 在專案之間傳遞得來不易的工作流的方式。

## 為何用 registry，而不只是檔案

把 skills/tools 以純檔案形式儲存，能讓它們易於檢視與編輯；而把
它們的 *telemetry* 存放在 `memory.db`，則讓 Veles 能推理哪些確實有效。
這樣的組合，才能把「一堆腳本的資料夾」變成會累積、可自我策展的
能力。

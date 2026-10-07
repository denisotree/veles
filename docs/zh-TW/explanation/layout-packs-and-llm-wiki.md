# Layout pack 與 LLM-Wiki

> 🌐 **語言：** [English](../../en/explanation/layout-packs-and-llm-wiki.md) · [简体中文](../../zh-CN/explanation/layout-packs-and-llm-wiki.md) · **繁體中文** · [日本語](../../ja/explanation/layout-packs-and-llm-wiki.md) · [한국어](../../ko/explanation/layout-packs-and-llm-wiki.md) · [Español](../../es/explanation/layout-packs-and-llm-wiki.md) · [Français](../../fr/explanation/layout-packs-and-llm-wiki.md) · [Italiano](../../it/explanation/layout-packs-and-llm-wiki.md) · [Português (BR)](../../pt-BR/explanation/layout-packs-and-llm-wiki.md) · [Português (PT)](../../pt-PT/explanation/layout-packs-and-llm-wiki.md) · [Русский](../../ru/explanation/layout-packs-and-llm-wiki.md) · [العربية](../../ar/explanation/layout-packs-and-llm-wiki.md) · [हिन्दी](../../hi/explanation/layout-packs-and-llm-wiki.md) · [বাংলা](../../bn/explanation/layout-packs-and-llm-wiki.md) · [Tiếng Việt](../../vi/explanation/layout-packs-and-llm-wiki.md)

**layout pack** 定義了一個專案的*使用者內容*如何組織——有哪些目錄、agent 可以寫入哪些目錄,以及它提供哪些操作。預設是 **`bare`**,除了 `.veles/` 和 `AGENTS.md` 之外不會在你的目錄中新增任何東西。**LLM-Wiki** 是擴充登錄表(extension registry)中的一個選項,**並非** Veles 的核心原則。

## layout pack 是什麼

一個 layout pack 是一個目錄,內含一份 `layout.toml` 清單(加上可選的 skill 與範本檔案)。該清單宣告:

- **可寫入區域**——agent 可以將內容寫入的目錄(在每次 `write_file` 時強制執行)。
- **唯讀區域**——agent 會讀取但絕不修改的材料。
- **操作**——具名的工作流程,以 pack 內的 skills 形式提供。
- **Scaffold**(`[layout.scaffold]`)——`veles init` 會建立什麼:目錄,以及一個可選的 `AGENTS.md` 範本(`{name}` 會被替換)。
- **Engines**(`[layout.engines]`)——pack 要求哪些內容機制。engine 由模組提供(登錄表中的 `wiki` 模組提供 `wiki`)。沒有它,專案中就不存在 wiki tools、wiki recall 或 INDEX 注入。
- **Context 檔案**(`context_file`)——注入到 agent 穩定系統 prompt 的檔案(LLM-Wiki 使用 `INDEX.md`)。

## 可用的 packs

| Pack | 來源 | `veles init --layout <name>` 產生的內容 |
|---|---|---|
| `bare` *(預設)* | 內建 | 完全沒有內容 scaffold——適用於程式碼倉庫與自由形式的工作。在專案根目錄內寫入是寬鬆的(仍受 trust ladder 約束)。 |
| `llm-wiki` | 登錄表(`public:official/llm-wiki`,會帶上 `wiki` 模組) | [Karpathy 風格的 LLM-Wiki](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f):`sources/`(依慣例唯讀,不強制)、`wiki/`(agent 可寫入)、注入到 prompt 的 `INDEX.md`、`ingest`/`query`/`lint`/`organize`/`structure_design` skills、wiki engine 開啟、`veles add` 與 `/wiki`。由 layout 宣告的行為 prompt(`templates/behaviour.md`)承載 sources/wiki 的紀律以及遷移/日誌補丁規則。 |
| `notes` | 登錄表(`public:official/notes`) | 單一扁平的 `notes/` 目錄供 agent 寫入。沒有 wiki 機制。 |

在終端機中,`veles init` 會詢問要使用哪個 pack(已安裝的與你的登錄表中的);選擇尚未安裝的 pack 時會提議安裝。`veles registry install llm-wiki` 可事先安裝。

## 1.2.3 之前的專案

layout 未安裝的專案(升級後的 `llm-wiki` 專案,或沒有 `layout` 鍵的專案——它們當時都是 wiki 專案)仍可開啟。在終端機中,`veles` 與 `veles run` 會在一次確認下提議安裝該 pack(連同它所需的 engine);在其他情況——daemon、channels、其他指令——Veles 只會印出一次安裝指令,並在沒有 wiki 的情況下繼續運作。`wiki/` 中的任何內容都不會被動到。

## 自訂佈局

把一個 pack 放到 `~/.veles/layouts/<name>/layout.toml`(使用者全域),或放到 `<project>/.veles/layouts/<name>/`(專案本地;會遮蔽同名的使用者與內建 packs),然後傳入 `veles init --layout <name>`。登錄表中的 `notes` pack 是可供複製的最簡範例。要求某個 engine、但已安裝模組都不提供它的 pack,會得到同樣的安裝提議。你也可以在 `AGENTS.md` 中描述慣例——佈局強制區域,AGENTS.md 引導行為。

## 它*不是*什麼

佈局只管理**你的內容**。Veles 自己的專案記憶——`memory.db` 加上 `.veles/memory/` 產物樹(insights、session digest、proposal、system-ops journal)——屬於系統側,在任何佈局下都以相同方式運作。切換佈局絕不會觸及學習迴圈、sessions 或登錄表。參見[架構](architecture.md)與[專案佈局](../reference/project-layout.md)。

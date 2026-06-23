# Layout pack 與 LLM-Wiki

> 🌐 **語言:** **English** · [Русский](../../ru/explanation/layout-packs-and-llm-wiki.md)

**layout pack** 定義了一個專案的*使用者內容*如何組織——有哪些目錄、agent 可以寫入哪些目錄,以及它提供哪些操作。預設是 **LLM-Wiki**。這是一個內容選項,**並非** Veles 的核心原則。

## layout pack 是什麼

一個 layout pack 是一個目錄,內含一份 `layout.toml` 清單(加上可選的 skill 與範本檔案)。該清單宣告:

- **可寫入區域**——agent 可以將內容寫入的目錄(在每次 `write_file` 時強制執行)。
- **唯讀區域**——agent 會讀取但絕不修改的材料。
- **操作**——具名的工作流程,以 pack 內的 skills 形式提供。
- **Scaffold**(`[layout.scaffold]`)——`veles init` 會建立什麼:目錄,以及一個可選的 `AGENTS.md` 範本(`{name}` 會被替換)。
- **Engines**(`[layout.engines]`)——pack 啟用哪些核心內容機制。目前只有一個 engine:`wiki`。沒有它,專案中就不存在 wiki tools、wiki recall 或 INDEX 注入。
- **Context 檔案**(`context_file`)——注入到 agent 穩定系統 prompt 的檔案(LLM-Wiki 使用 `INDEX.md`)。

## 內建 packs

| Pack | `veles init --layout <name>` 產生的內容 |
|---|---|
| `llm-wiki` *(預設)* | [Karpathy 風格的 LLM-Wiki](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f):`sources/`(唯讀)、`wiki/`(agent 可寫入)、注入到 prompt 的 `INDEX.md`、`ingest`/`query`/`lint` skills、wiki engine 開啟。 |
| `notes` | 單一扁平的 `notes/` 目錄供 agent 寫入。沒有 wiki 機制。 |
| `bare` | 完全沒有內容 scaffold——適用於程式碼倉庫與自由形式的工作。在專案根目錄內寫入是寬鬆的(仍受 trust ladder 約束)。 |

## 自訂佈局

把一個 pack 放到 `~/.veles/layouts/<name>/layout.toml`(使用者全域),或放到 `<project>/.veles/layouts/<name>/`(專案本地;會遮蔽同名的使用者與內建 packs),然後傳入 `veles init --layout <name>`。`notes` 內建是可供複製的最簡範例。你也可以在 `AGENTS.md` 中描述慣例——佈局強制區域,AGENTS.md 引導行為。

## 它*不是*什麼

佈局只管理**你的內容**。Veles 自己的專案記憶——`memory.db` 加上 `.veles/memory/` 產物樹(insights、session digest、proposal、system-ops journal)——屬於系統側,在任何佈局下都以相同方式運作。切換佈局絕不會觸及學習迴圈、sessions 或登錄表。參見[架構](architecture.md)與[專案佈局](../reference/project-layout.md)。

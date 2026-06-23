# 專案結構與狀態

> 🌐 **語言：** **English** · [Русский](../../ru/reference/project-layout.md)

`veles init` 會建立什麼、Veles 把狀態存放在哪裡，以及專案記憶的 schema。

## `veles init` 會產生什麼

使用者內容那一半取決於所選的 layout pack（`--layout`，預設為 `llm-wiki`）；而 `.veles/` 狀態那一半在任何情況下都相同。

```
my-project/                  # veles init  (default llm-wiki layout)
├── AGENTS.md                # project context (injected into the agent)
├── CLAUDE.md → AGENTS.md    # symlink, so a `claude` CLI picks up the same context
├── GEMINI.md → AGENTS.md    # symlink, for a `gemini` CLI
├── sources/                 # raw, immutable source material (agent-readonly)
├── wiki/                    # the LLM-writable knowledge zone
│   ├── concepts/ entities/ queries/ self-doc/ sessions/ sources/
└── .veles/                  # project state (do not commit; machine-managed)
    ├── project.toml         # name, created_at, schema_version, layout
    ├── memory.db            # SQLite: sessions, turns, insights, rules, telemetry
    ├── memory/              # the agent's own memory artefacts:
    │   ├── LOG.md           #   append-only system-ops journal
    │   ├── insights/        #   rendered views of `insights` rows
    │   ├── sessions/        #   compaction summaries
    │   └── proposals/       #   subproject / skill-promotion proposals
    ├── jobs/                # scheduled-job outputs
    └── skills/              # project-local skills
```

使用 `--layout notes` 時，內容那一半是單一的 `notes/` 目錄；使用 `--layout bare` 時則完全沒有任何內容 scaffold。`wiki/INDEX.md`（隨選載入的目錄）會隨著 wiki 成長而產生；當你設定了某項組態、agent 寫出一個 tool，或你執行了一個 goal 之後，`config.toml`、`tools/` 與 `plans/` 才會出現在 `.veles/` 底下。

## 狀態目錄

| Path | Scope | Committed? |
|---|---|---|
| `<project>/AGENTS.md` + layout content (`wiki/`, `sources/`, `notes/`, …) | 專案內容 | **是** — 這是你的知識庫 |
| `<project>/.veles/` | 專案機器狀態（記憶、組態、專案本地 skills/tools） | 否 |
| `~/.veles/` | 使用者全域：`config.toml`、trust 授權、跨專案 skills/tools、layout packs、模型快取、locales | 否 |

`VELES_USER_HOME` 會為使用者全域樹重新導向 `~`（用於測試、sandbox）。

## 專案記憶（`.veles/memory.db` + `.veles/memory/`）

Veles 的專案記憶是一個**結構化的 artefact**，與你的內容分離且與 layout 無關。SQLite 資料庫（WAL 模式）是真實來源；`.veles/memory/` 則持有人類可讀的那一側（渲染後的 insight 檢視、session 摘要、proposals、system-ops 日誌）。主要的資料表：

| Table | Holds |
|---|---|
| `sessions`, `turns` | 對話歷史（每個 turn 一列） |
| `turns_fts` | turns 的全文索引（驅動 `veles sessions search`） |
| `insights`, `insights_fts`, `insight_refs` | 學到的 insights（標準列；markdown 檢視可重新產生）+ 去重連結 |
| `rules`, `rules_fts` | 注入到 stable prompt 的 format/do/don't/preference 規則 |
| `skills`, `skill_uses`, `skill_tool_refs` | Skill 註冊表 + 遙測 + tool 連結 |
| `tools`, `tool_uses` | Tool 註冊表 + 遙測（使用/成功/錯誤次數） |
| `project_tree` | 快取的專案檔案地圖 + 用於相關性排序的語意標籤 |

關於這些如何被寫入與 recall，請見 [Project memory & the learning loop](../explanation/project-memory-and-learning-loop.md)。

## Layout packs

`veles init --layout {llm-wiki|notes|bare|<custom>}` 選擇內容 layout；pack 擁有 scaffold、AGENTS.md 範本、可寫入區域，以及 wiki engine（wiki tools、INDEX prompt 注入、wiki recall）是否啟用。請見 [layout packs & the LLM-Wiki](../explanation/layout-packs-and-llm-wiki.md)。

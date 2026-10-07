# 如何管理 skills、tools 與 modules

> 🌐 **語言：** [English](../../en/how-to/manage-skills-and-tools.md) · [简体中文](../../zh-CN/how-to/manage-skills-and-tools.md) · **繁體中文** · [日本語](../../ja/how-to/manage-skills-and-tools.md) · [한국어](../../ko/how-to/manage-skills-and-tools.md) · [Español](../../es/how-to/manage-skills-and-tools.md) · [Français](../../fr/how-to/manage-skills-and-tools.md) · [Italiano](../../it/how-to/manage-skills-and-tools.md) · [Português (BR)](../../pt-BR/how-to/manage-skills-and-tools.md) · [Português (PT)](../../pt-PT/how-to/manage-skills-and-tools.md) · [Русский](../../ru/how-to/manage-skills-and-tools.md) · [العربية](../../ar/how-to/manage-skills-and-tools.md) · [हिन्दी](../../hi/how-to/manage-skills-and-tools.md) · [বাংলা](../../bn/how-to/manage-skills-and-tools.md) · [Tiếng Việt](../../vi/how-to/manage-skills-and-tools.md)

Veles 會隨著時間累積能力。**Skills** 是可重複使用的工作流程，
**tools** 是可執行的動作，**modules** 是選用的外掛。每一種都存在於兩個範圍：
project-local（`<project>/.veles/`）與 user-global（`~/.veles/`）。關於這些概念，
請參閱 [skills & tools](../explanation/skills-and-tools.md)。

## Skills

skill 是一個 `SKILL.md`（frontmatter + prompt 主體），agent 可以像呼叫 tool 一樣
呼叫它。

```bash
veles skill list                          # installed skills + telemetry
veles skill show <name>                   # print its SKILL.md
veles skill add https://github.com/org/skill.git
veles skill add ./local-skill --scope user   # install user-global
veles skill remove <name>
```

### 在範圍之間 promote / demote

一個在某個專案中證明有用的 skill 可以移到 user 範圍，讓每個專案都能看到它
（或者反過來）：

```bash
veles skill promote <name>     # project → ~/.veles/skills/
veles skill demote  <name>     # user → this project
```

### 找出重複項與 promotion 候選

```bash
veles skill dedup                         # near-duplicate skills (embedding/TF-IDF)
veles skill suggest-promote --save        # skills that meet the auto-promote bar
```

## Tools

Tools 會連同使用 telemetry 一起編入專案的 `memory.db`。Veles 在工作過程中可以
撰寫自己的 tools；你可以用以下指令管理它們：

```bash
veles tool list                # tools in this project
veles tool show <name>         # manifest + telemetry
veles tool promote <name>      # move to ~/.veles/tools/ (cross-project)
```

敏感的 tools（`run_shell`、`write_file`、`fetch_url`……）會受到
[trust ladder](security-and-permissions.md) 的把關。

## Modules

Module 是在 Veles 內部執行的 Python 程式碼（`module.toml` + 一個進入點）— 在不讓核心臃腫的前提下加入選用能力（memory provider、embeddings、vision、STT）。預設情況下，安裝一個 module 需要確認，而且只有當它的檔案仍與你核可的內容一致時，才會在每次執行中載入（參見[保持安裝可信](extension-registries.md#keep-installs-honest)）。

```bash
veles module list                              # both scopes, with a `scope` column
veles module add https://github.com/org/module.git
veles module add ./local-module --user          # install to ~/.veles/modules/, all projects
veles module show <name> [--user]             # 清單檔 + 檔案 sha256
veles module remove <name> [--user]
veles module approve <name> [--user]          # 在終端機中輸入 `yes`
veles module approve <name> --sha256 <hash>   # 無終端機時：你審閱過的雜湊值
```

Modules 與 skills、tools 一樣存在於兩個作用域：專案本地（`<project>/.veles/modules/`）與使用者全域（`~/.veles/modules/`，在每個專案中載入）。使用者層級的 module 與專案層級的 module 經過同樣的核可閘門，且閘門在比較名稱之前執行。如果專案 module 與使用者 module 同名，已核可的專案 module 會載入，Veles 會警告使用者層級的 module 被遮蔽；未核可的專案 module 會被跳過（警告中會指出其目錄），此時載入使用者 module。同一作用域內兩個已核可的 module 同名時 — 依目錄排序的第一個載入，其餘的發出警告並被跳過。`veles module {show,approve,remove}` 接受 manifest 名稱（`list` 顯示的名稱），並會拒絕該作用域內被多個目錄宣告的名稱，同時列出這些目錄；`veles module add` 會拒絕安裝名稱已被該作用域內另一個目錄宣告的 module。

### 撰寫加入 memory provider 的 module

Module 的 `register(api)` 進入點可以呼叫 `api.add_memory_provider(name, factory)`，把外部記憶來源接入 recall。`name` 必須與 `~/.veles/config.toml` 中的某個 `[memory.external.<name>]` 區段一致；`factory` 會以該區段（一個 `dict`）為引數被呼叫，並且必須回傳一個實作了 Veles 的 `MemoryProvider` protocol（`veles.core.memory.provider`）的物件，或回傳 `None` 以跳過該 provider：

```toml
# module.toml
[module]
name = "my-provider"
description = "Recalls memories from my external store."
entrypoint = "my_provider.py:register"
version = "0.1.0"
```

```python
# my_provider.py
from veles.core.memory.provider import RecallHit


class MyProvider:
    name = "my-provider"

    def recall(self, query: str, *, limit: int) -> list[RecallHit]:
        ...  # query the external store, return RecallHit objects


def _build(cfg: dict) -> MyProvider | None:
    api_key = cfg.get("api_key")
    return MyProvider() if api_key else None


def register(api) -> None:
    api.add_memory_provider("my-provider", _build)
```

```toml
# ~/.veles/config.toml
[memory.external.my-provider]
api_key = "..."
```

如果 provider 還實作了 `ingest(title, body, *, insight_id) -> bool`（`IngestingMemoryProvider` protocol），它也會收到 Veles 的寫入，而不只是讀取。如果兩個 module 註冊了同一個 provider 名稱，第二個 module 會載入失敗 — 它會帶警告被跳過，不會留下任何部分註冊的內容。在 `config.toml` 中設定了某個區段、但對應 module 並未安裝時，會印出一則附安裝指令的警告；recall 照常運作。

Registry 提供 Honcho、Mem0 與 Supermemory 作為現成的 provider module — 用 `veles registry install --user {honcho,mem0,supermemory}` 安裝，然後執行安裝時印出的 `uv tool install veles-ai --with '<package>'` 指令（每個 module 都宣告了一個 SDK — `mem0ai>=2.0`、`honcho-ai>=2.5`、`supermemory>=3.62` — Veles 絕不會替你安裝），並填寫對應的 `[memory.external.<name>]` 區段：

- **mem0**：`api_key`、`user_id`，可選 `agent_id`（同時 recall 該 agent 的記憶）與 `host`。SDK 遙測預設關閉；每次 recall 會多發出一次 `GET /v1/ping/` 請求。
- **supermemory**：`api_key`，可選 `user_id`（作為搜尋的 `container_tag` 傳送）與 `base_url`。
- **honcho**：`api_key`、`workspace_id`，可選 `peer_id`（僅搜尋該 peer 的訊息）與 `base_url`。每次 recall 都會執行一次 workspace get-or-create — 如果 `workspace_id` 尚不存在就會建立它。

## 探索更多

在已連接的 registries 中搜尋：

```bash
veles registry search [query] [--kind module|skill|layout|mcp]
```

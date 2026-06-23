# 如何使用多個專案與子專案

> 🌐 **語言：** **English** · [Русский](../../ru/how-to/multi-project-and-subprojects.md)

Veles 在一個 agent loop 中運行多個專案。每個專案都有自己的記憶、skills 與 tools。
**Subprojects** 是巢狀在某個母專案底下的專案 — 適合用來把一個龐大的 monorepo 或
知識庫拆解成範圍化的記憶。

## Projects

Veles 會從你的 cwd 往上尋找 `.veles/` 目錄（就像 `git` 那樣）來探索目前作用中的
專案。管理 registry：

```bash
veles project list                  # registered projects, most-recent first
veles project add /path/to/project  # register an existing project
veles project add /path --slug web  # with a custom slug
veles project remove <slug>         # unregister (files untouched)
```

`switch` 會印出一個路徑，讓你可以 `cd` 進入某個專案：

```bash
cd "$(veles project switch web)"
```

不必 `cd` 就能對位於別處的專案執行指令：

```bash
veles run --project-root /path/to/project "..."
```

## Subprojects

subproject 是某個母專案內部的子 Veles 專案。建立一個：

```bash
veles subproject init frontend --description "the web client"
veles subproject list
cd "$(veles subproject switch frontend)"
veles subproject remove frontend    # unregister (files untouched)
```

### 讓 Veles 建議一種拆分方式

當一個專案的 wiki 成長時，Veles 可以偵測主題叢集並把它們提議為 subprojects：

```bash
veles subproject suggest            # print candidates
veles subproject suggest --save     # save each to .veles/memory/proposals/ for recall
```

## 該用哪一種

- **分開的專案** — 互不相關的知識庫 / 程式碼庫。
- **Subprojects** — 同一個較大事物的各個部分，它們受益於範圍化的記憶，但共享一個
  母 context。

請參閱 [architecture](../explanation/architecture.md)，了解多專案 context 如何
依需求載入，而非作為單一龐大的傾印。

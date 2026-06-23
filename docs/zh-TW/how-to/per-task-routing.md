# 如何將任務路由到不同的模型

> 🌐 **語言：** **English** · [Русский](../../ru/how-to/per-task-routing.md)

Veles 並不綁定在單一模型上。每個內部 **task** 都可以使用不同的
`provider:model` — 用便宜的模型做 context 壓縮、用強大的模型跑主 agent、用 vision
模型處理圖片。這就是 *ensemble routing* 系統。

## Task 類型

| Task | 用於 |
|---|---|
| `default` | 主 agent loop |
| `curator` | Session → wiki 整併 |
| `compressor` | 滑動視窗 context 壓縮 |
| `insights` | 執行後的 insight 擷取 |
| `skills` | Skill 執行 |
| `advisor` | `advisor_review` 自我檢查 |
| `vision` | `image_describe`（當有接上 vision adapter 時） |
| `embedding` | `veles skill dedup` 相似度 |

## 查看目前的路由

```bash
veles route show
```

這會印出每個 task 解析後的 `provider:model`，以及一個 `source` 標籤，說明是哪一層
決定了它。

## 把某個 task 釘到一個模型

```bash
veles route set compressor openrouter:anthropic/claude-haiku-4.5
veles route set advisor    openrouter:anthropic/claude-opus-4.8
veles route set vision     openai:gpt-4o
```

這些會在 `<project>/.veles/config.toml` 中寫入 `[routing.tasks]`：

```toml
[routing.tasks]
compressor = "openrouter:anthropic/claude-haiku-4.5"
advisor    = "openrouter:anthropic/claude-opus-4.8"
vision     = "openai:gpt-4o"
```

## 重設

```bash
veles route reset compressor   # one task back to default
veles route reset              # all tasks back to default
```

## AGENTS.md 中的自然語言提示

你可以在 `AGENTS.md` 中以散文形式表達路由（例如「壓縮時使用便宜的模型」）。Veles
會把這些解析成一個自動產生的 `routing.nl.toml`：

```bash
veles route refresh            # re-parse AGENTS.md hints
veles route refresh --force    # even if AGENTS.md hasn't changed
```

明確的 `[routing.tasks]` 項目永遠勝過 NL 提示。

## 解析順序

對每個 task 而言，第一個產出規格的層會勝出：

1. project `[routing.tasks][task]`
2. project `[routing.tasks].default`
3. project NL 提示（`routing.nl.toml`）
4. project `[provider]` base
5. user `[routing.tasks][task]` / `.default`
6. user `[user] default_provider` + `default_model`
7. 該 task 的內建預設值

（`embedding` 會跳過 catch-all 層 — chat 模型不是 embedding 模型。）

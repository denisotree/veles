# 如何將任務路由到不同的模型

> 🌐 **語言：** [English](../../en/how-to/per-task-routing.md) · [简体中文](../../zh-CN/how-to/per-task-routing.md) · **繁體中文** · [日本語](../../ja/how-to/per-task-routing.md) · [한국어](../../ko/how-to/per-task-routing.md) · [Español](../../es/how-to/per-task-routing.md) · [Français](../../fr/how-to/per-task-routing.md) · [Italiano](../../it/how-to/per-task-routing.md) · [Português (BR)](../../pt-BR/how-to/per-task-routing.md) · [Português (PT)](../../pt-PT/how-to/per-task-routing.md) · [Русский](../../ru/how-to/per-task-routing.md) · [العربية](../../ar/how-to/per-task-routing.md) · [हिन्दी](../../hi/how-to/per-task-routing.md) · [বাংলা](../../bn/how-to/per-task-routing.md) · [Tiếng Việt](../../vi/how-to/per-task-routing.md)

Veles 並未被綁死在單一模型上。每一個內部**任務**都可以使用不同的 `provider:model`——脈絡壓縮用便宜的模型、主代理用強的模型、影像用視覺模型。這就是*集成路由*系統。

## 任務類型

| 任務 | 用於 |
|---|---|
| `default` | 主代理迴圈 |
| `curator` | 工作階段 → wiki 整併 |
| `compressor` | 滑動視窗脈絡壓縮 |
| `insights` | 執行後的洞見擷取 |
| `skills` | 技能執行 |
| `advisor` | `advisor_review` 自我檢查 |
| `vision` | `image_describe`（當接上視覺轉接器時） |
| `embedding` | `veles skill dedup` 的相似度計算 |

## 查看目前的路由

```bash
veles route show
```

這會印出每個任務已解析的 `provider:model`，以及一個說明是哪一層決定它的 `source` 標籤。

## 將任務固定到某模型

```bash
veles route set compressor openrouter:anthropic/claude-haiku-4.5
veles route set advisor    openrouter:anthropic/claude-opus-4.8
veles route set vision     openai:gpt-4o
```

這些會寫入 `<project>/.veles/config.toml` 中的 `[routing.tasks]`：

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

你可以在 `AGENTS.md` 中以散文表達路由（例如「壓縮用便宜的模型」）。Veles 會將這些解析進一個自動產生的 `routing.nl.toml`：

```bash
veles route refresh            # re-parse AGENTS.md hints
veles route refresh --force    # even if AGENTS.md hasn't changed
```

明確的 `[routing.tasks]` 條目永遠優先於 NL 提示。

## 解析順序

對每個任務而言，第一個產出 spec 的層級勝出：

1. 專案 `[routing.tasks][task]`
2. 專案 `[routing.tasks].default`
3. 專案 NL 提示（`routing.nl.toml`）
4. 專案 `[engine]` 基礎設定
5. 使用者 `[routing.tasks][task]` / `.default`
6. 使用者 `[user] default_provider` ＋ `default_model`

若以上皆無法解析，**沒有硬寫死的退路**——該任務會維持未設定，其呼叫方會降級（跳過該功能）或明確報錯，而不會默默地去動用某個雲端模型。

（`embedding` 會跳過那些通用兜底層——chat 模型並非 embedding 模型——因此只有明確的 `[routing.tasks].embedding` 才能解析它。）

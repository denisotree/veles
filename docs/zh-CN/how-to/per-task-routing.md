# 如何将任务路由到不同的模型

> 🌐 **语言：** [English](../../en/how-to/per-task-routing.md) · **简体中文** · [繁體中文](../../zh-TW/how-to/per-task-routing.md) · [日本語](../../ja/how-to/per-task-routing.md) · [한국어](../../ko/how-to/per-task-routing.md) · [Español](../../es/how-to/per-task-routing.md) · [Français](../../fr/how-to/per-task-routing.md) · [Italiano](../../it/how-to/per-task-routing.md) · [Português (BR)](../../pt-BR/how-to/per-task-routing.md) · [Português (PT)](../../pt-PT/how-to/per-task-routing.md) · [Русский](../../ru/how-to/per-task-routing.md) · [العربية](../../ar/how-to/per-task-routing.md) · [हिन्दी](../../hi/how-to/per-task-routing.md) · [বাংলা](../../bn/how-to/per-task-routing.md) · [Tiếng Việt](../../vi/how-to/per-task-routing.md)

Veles 并不绑定在单一模型上。每种内部**任务**都可以使用不同的 `provider:model`——上下文压缩用便宜的模型，主 agent 用强大的模型，图像用视觉模型。这就是*集成路由*系统。

## 任务类型

| 任务 | 用于 |
|---|---|
| `default` | 主 agent 循环 |
| `curator` | session → wiki 巩固 |
| `compressor` | 滑动窗口上下文压缩 |
| `insights` | 运行后的 insight 提取 |
| `skills` | skill 执行 |
| `advisor` | `advisor_review` 自检 |
| `vision` | `image_describe`（当接入了视觉适配器时） |
| `embedding` | `veles skill dedup` 的相似度计算 |

## 查看当前路由

```bash
veles route show
```

这会打印每个任务解析后的 `provider:model`，以及一个说明由哪一层决定该结果的 `source` 标签。

## 将某个任务固定到一个模型

```bash
veles route set compressor openrouter:anthropic/claude-haiku-4.5
veles route set advisor    openrouter:anthropic/claude-opus-4.8
veles route set vision     openai:gpt-4o
```

这些会向 `<project>/.veles/config.toml` 写入 `[routing.tasks]`：

```toml
[routing.tasks]
compressor = "openrouter:anthropic/claude-haiku-4.5"
advisor    = "openrouter:anthropic/claude-opus-4.8"
vision     = "openai:gpt-4o"
```

## 重置

```bash
veles route reset compressor   # one task back to default
veles route reset              # all tasks back to default
```

## AGENTS.md 中的自然语言提示

你可以在 `AGENTS.md` 中用散文形式表达路由（例如 "use a cheap model for compression"）。Veles 会把这些解析为自动生成的 `routing.nl.toml`：

```bash
veles route refresh            # re-parse AGENTS.md hints
veles route refresh --force    # even if AGENTS.md hasn't changed
```

显式的 `[routing.tasks]` 条目始终优先于 NL 提示。

## 解析顺序

对每个任务，第一个产出规格的层胜出：

1. 项目 `[routing.tasks][task]`
2. 项目 `[routing.tasks].default`
3. 项目 NL 提示（`routing.nl.toml`）
4. 项目 `[engine]` 基础配置
5. 用户 `[routing.tasks][task]` / `.default`
6. 用户 `[user] default_provider` + `default_model`

如果以上都无法解析，则**没有硬编码回退**——该任务保持未设置状态，其调用方会优雅降级（跳过该功能）或清晰报错，而不会悄悄去用某个云端模型。

（`embedding` 会跳过这些兜底项——chat 模型不是 embedding 模型——所以只有显式的 `[routing.tasks].embedding` 才能为它给出答案。）

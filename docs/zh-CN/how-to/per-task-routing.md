# 如何将任务路由到不同的模型

> 🌐 **Languages:** **English** · [Русский](../../ru/how-to/per-task-routing.md)

Veles 并不会被绑定到单一模型。每一个内部**任务**都可以使用不同的
`provider:model` —— 用便宜的模型做上下文压缩、用强大的模型跑主智能体、用视觉模型处理图像。这就是 *ensemble routing*（集成路由）系统。

## 任务类型

| 任务 | 用途 |
|---|---|
| `default` | 主智能体循环 |
| `curator` | 会话 → wiki 整合 |
| `compressor` | 滑动窗口上下文压缩 |
| `insights` | 运行后的洞见提取 |
| `skills` | 技能执行 |
| `advisor` | `advisor_review` 自检 |
| `vision` | `image_describe`（当接入了视觉适配器时） |
| `embedding` | `veles skill dedup` 相似度计算 |

## 查看当前路由

```bash
veles route show
```

这会打印每个任务解析出的 `provider:model`，以及一个 `source` 标签，
说明是哪一层决定了它。

## 将任务固定到某个模型

```bash
veles route set compressor openrouter:anthropic/claude-haiku-4.5
veles route set advisor    openrouter:anthropic/claude-opus-4.8
veles route set vision     openai:gpt-4o
```

这些命令会把内容写入 `<project>/.veles/config.toml` 中的 `[routing.tasks]`：

```toml
[routing.tasks]
compressor = "openrouter:anthropic/claude-haiku-4.5"
advisor    = "openrouter:anthropic/claude-opus-4.8"
vision     = "openai:gpt-4o"
```

## 重置

```bash
veles route reset compressor   # 将单个任务恢复为默认值
veles route reset              # 将所有任务恢复为默认值
```

## AGENTS.md 中的自然语言提示

你可以在 `AGENTS.md` 中用自然语言来表达路由意图（例如“用便宜的模型做
压缩”）。Veles 会把它们解析进一个自动生成的 `routing.nl.toml`：

```bash
veles route refresh            # 重新解析 AGENTS.md 中的提示
veles route refresh --force    # 即使 AGENTS.md 没有变化也重新解析
```

显式的 `[routing.tasks]` 条目始终优先于自然语言提示。

## 解析顺序

对于每个任务，第一个能给出规格的层级胜出：

1. 项目 `[routing.tasks][task]`
2. 项目 `[routing.tasks].default`
3. 项目自然语言提示（`routing.nl.toml`）
4. 项目 `[provider]` 基础配置
5. 用户 `[routing.tasks][task]` / `.default`
6. 用户 `[user] default_provider` + `default_model`
7. 该任务的内置默认值

（`embedding` 会跳过那些兜底项 —— 聊天模型并不是嵌入模型。）

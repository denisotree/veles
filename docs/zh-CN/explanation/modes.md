# 运行模式

> 🌐 **语言：** [English](../../en/explanation/modes.md) · **简体中文** · [繁體中文](../../zh-TW/explanation/modes.md) · [日本語](../../ja/explanation/modes.md) · [한국어](../../ko/explanation/modes.md) · [Español](../../es/explanation/modes.md) · [Français](../../fr/explanation/modes.md) · [Italiano](../../it/explanation/modes.md) · [Português (BR)](../../pt-BR/explanation/modes.md) · [Português (PT)](../../pt-PT/explanation/modes.md) · [Русский](../../ru/explanation/modes.md) · [العربية](../../ar/explanation/modes.md) · [हिन्दी](../../hi/explanation/modes.md) · [বাংলা](../../bn/explanation/modes.md) · [Tiếng Việt](../../vi/explanation/modes.md)

在 TUI 中，每条提示都由一个 **运行模式** 处理 —— 一种决定本轮获得多少自主权、使用哪些工具的策略。用 `Shift+Tab` 循环切换模式；顺序为 `auto → planning → writing → goal`。

## 四种模式

### `writing` —— 直接对话
最直白的模式：你的提示连同完整工具集一起发送给智能体，它据此响应。当你希望智能体动手做事的日常工作时使用它。

### `planning` —— 只读研究 + 计划
变更操作被阻止（没有 `write_file`，没有 `run_shell`）。智能体使用读取/搜索工具收集上下文，然后产出一份结构化的计划产物。用它在动手之前先思考 —— 或者向 `veles run` 传入 `--plan` 在 CLI 上获得相同效果。

### `auto` —— 智能路由（默认）
一次快速分类判断你的提示是直接请求还是需要规划，然后据此分派到 `writing` 或 `planning`。当你没有表达意图时，它是最聪明的兜底，这也是它成为循环中默认首选的原因。

### `goal` —— 长跨度目标
为一个多步目标驱动一个有限状态机：它会访谈你以澄清需求、确认计划、执行各步骤（带顾问检查），并验证完成条件 —— 全部在明确的预算约束之下。其 CLI 等价物是 [`veles goal`](../how-to/long-running-tasks.md#goals--objectives-with-budgets-and-checkpoints) 命令系列。

## 为什么存在模式

不同的请求需要不同程度的谨慎。一个快速提问不应需要繁文缛节；一项有风险的更改先经过一遍只读规划会更有益；一个大目标需要预算和检查点。模式让这一选择变得明确，并可按轮切换，而不是把单一行为固化到整个会话中。

当你在会话中途切换时，智能体会被告知新规则，因此其行为会立即改变。

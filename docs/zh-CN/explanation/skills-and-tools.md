# 作为可累积能力的技能与工具

> 🌐 **语言：** [English](../../en/explanation/skills-and-tools.md) · **简体中文** · [繁體中文](../../zh-TW/explanation/skills-and-tools.md) · [日本語](../../ja/explanation/skills-and-tools.md) · [한국어](../../ko/explanation/skills-and-tools.md) · [Español](../../es/explanation/skills-and-tools.md) · [Français](../../fr/explanation/skills-and-tools.md) · [Italiano](../../it/explanation/skills-and-tools.md) · [Português (BR)](../../pt-BR/explanation/skills-and-tools.md) · [Português (PT)](../../pt-PT/explanation/skills-and-tools.md) · [Русский](../../ru/explanation/skills-and-tools.md) · [العربية](../../ar/explanation/skills-and-tools.md) · [हिन्दी](../../hi/explanation/skills-and-tools.md) · [বাংলা](../../bn/explanation/skills-and-tools.md) · [Tiếng Việt](../../vi/explanation/skills-and-tools.md)

Veles 以一组极简的工具和技能起步，并随着工作 **不断壮大** 它们。本页解释二者的区别以及它们如何累积。关于相关命令，请参阅 [管理技能与工具](../how-to/manage-skills-and-tools.md)。

## 工具 vs 技能

- **工具** 是单个可执行动作 —— 读取文件、运行 shell 命令、抓取 URL、搜索网络、写入 wiki 页面。工具是模型所调用的对象。
- **技能** 是一个形式化的 *流程* —— 一份 `SKILL.md`，包含提示正文和一个允许工具清单，以一个聚焦的子智能体形式运行。技能将工具组合成一个可重复的工作流（例如 LLM-Wiki 的 `ingest`/`query`/`lint`）。

## 极简启动，按需扩展

Veles 以恰好够用的能力启动，外加一个已知的可供拉取更多内容的来源。安装额外项（一项技能、一个工具、一个模块）默认会请求批准；你可以授予长期自主权。这让一个全新项目保持精简，同时让能力在需要之处生长。

## 能力如何累积

1. **Veles 编写自己的工具。** 当它注意到一项重复任务时，它可以将一个干净、带类型、可复用的 Python 工具撰写到 `<project>/.veles/tools/` 中（并经过一遍顾问代码评审）。该工具带着遥测数据加入注册表。
2. **重复流程变为技能。** 一个模式检测器会发现反复出现的工具序列，并提议将它们形式化为一项技能；技能可以通过 `extends:` 另一项技能来继承其正文和工具。
3. **遥测驱动排序。** 每个工具/技能都携带使用/成功/错误计数。这些数据供去重（`veles skill dedup`）和晋升建议使用。

## 两种作用域，可晋升

工具和技能都存在于两个层级：

- **项目本地**（`<project>/.veles/`）—— 仅在此处可见。
- **用户全局**（`~/.veles/`）—— 在每个项目中都可用。

一项在某个项目中证明了自身价值的能力可以被 **晋升** 到用户作用域，从而让所有项目受益（`veles skill promote`、`veles tool promote`），或被 **降级** 回去。Veles 正是这样在项目之间携带来之不易的工作流。

## 为什么用注册表，而不只是文件

将技能/工具存为纯文件，让它们易于检视和编辑；将它们的 *遥测数据* 存于 `memory.db`，让 Veles 能推断出哪些是真正有效的。这种组合正是把"一个脚本文件夹"转变为可累积、自我策展能力的关键。

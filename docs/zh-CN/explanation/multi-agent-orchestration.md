# 多智能体编排

> 🌐 **Languages:** [English](../../en/explanation/multi-agent-orchestration.md) · [Русский](../../ru/explanation/multi-agent-orchestration.md) · **简体中文**

对于复杂工作，Veles 可以将一个任务拆分给一个 **管理者** 和若干专门的 **工作者** 子智能体，而不是在单一上下文中包揽一切。本页解释这一模型；要开启它，请参阅 [管理者模式](../how-to/long-running-tasks.md#manager-mode--decompose-any-prompt)。

## 结构形态

```
            manager  (decomposes the task, never writes the final answer)
           /    |    \
    explorer  writer  advisor   (specialised workers, run in parallel)
```

- **管理者** 规划分解方案并进行协调 —— 但它 **不** 亲自撰写最终交付物。
- **工作者** 拥有各自角色专属的系统提示：`explorer` 负责收集，`writer` 负责产出答案，`advisor` 负责评审。该集合是可扩展的。
- 在结束时，管理者将一份简短报告写入内存。

## 杜绝"传话游戏"

一条关键规则：中间产物以 **逐字原文** 的形式抵达综合者，而非管理者的转述。探索者的发现被直接交给写作者，因此细节不会经由一连串摘要而流失。这正是分解能够提升质量而非稀释质量的原因。

## 为什么"管理者从不写作"

如果协调者同时也撰写答案，它就会被诱使绕过工作者，从而丧失专业化分工带来的好处。把综合工作保留在一个专门的 `writer`（喂以逐字原文输入）中，强制了这一分工。Veles 将其作为运行时保证。

## 何时有用 —— 何时无用

对于宽泛或多面向的任务（审计这个代码库、从多个角度研究这个问题），分解会带来回报。对于一次快速的单上下文请求，它只会增加开销 —— 这正是管理者模式 **需要明确选择启用**、默认关闭的原因（`veles run --manager` 或 `VELES_MANAGER_MODE=1`）。

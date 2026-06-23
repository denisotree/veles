# 如何使用多个项目和子项目

> 🌐 **语言：** [English](../../en/how-to/multi-project-and-subprojects.md) · **简体中文** · [繁體中文](../../zh-TW/how-to/multi-project-and-subprojects.md) · [日本語](../../ja/how-to/multi-project-and-subprojects.md) · [한국어](../../ko/how-to/multi-project-and-subprojects.md) · [Español](../../es/how-to/multi-project-and-subprojects.md) · [Français](../../fr/how-to/multi-project-and-subprojects.md) · [Italiano](../../it/how-to/multi-project-and-subprojects.md) · [Português (BR)](../../pt-BR/how-to/multi-project-and-subprojects.md) · [Português (PT)](../../pt-PT/how-to/multi-project-and-subprojects.md) · [Русский](../../ru/how-to/multi-project-and-subprojects.md) · [العربية](../../ar/how-to/multi-project-and-subprojects.md) · [हिन्दी](../../hi/how-to/multi-project-and-subprojects.md) · [বাংলা](../../bn/how-to/multi-project-and-subprojects.md) · [Tiếng Việt](../../vi/how-to/multi-project-and-subprojects.md)

Veles 在一个智能体循环中运行多个项目。每个项目都有自己的记忆、技能和工具。**子项目（subprojects）**是嵌套在父项目之下的项目——适合把一个大型 monorepo 或知识库拆解为带作用域的多份记忆。

## 项目

Veles 通过从你的 cwd 向上查找一个 `.veles/` 目录（类似 `git`）来发现当前活动的项目。管理注册表：

```bash
veles project list                  # registered projects, most-recent first
veles project add /path/to/project  # register an existing project
veles project add /path --slug web  # with a custom slug
veles project remove <slug>         # unregister (files untouched)
```

`switch` 会打印一个路径，因此你可以 `cd` 进入某个项目：

```bash
cd "$(veles project switch web)"
```

无需 `cd` 即可对位于别处的项目运行命令：

```bash
veles run --project-root /path/to/project "..."
```

## 子项目

子项目是位于父项目内部的一个子级 Veles 项目。创建一个：

```bash
veles subproject init frontend --description "the web client"
veles subproject list
cd "$(veles subproject switch frontend)"
veles subproject remove frontend    # unregister (files untouched)
```

### 让 Veles 建议拆分

当一个项目的 wiki 增长时，Veles 可以检测主题聚类并把它们提议为子项目：

```bash
veles subproject suggest            # print candidates
veles subproject suggest --save     # save each to .veles/memory/proposals/ for recall
```

## 何时用哪一个

- **独立项目**——彼此无关的知识库 / 代码库。
- **子项目**——同一个更大整体的各个部分，它们既能从带作用域的记忆中受益，又共享一个父级上下文。

参见[架构](../explanation/architecture.md)，了解多项目上下文如何按需加载，而非一次性整体倾倒。

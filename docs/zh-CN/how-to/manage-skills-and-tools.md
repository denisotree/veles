# 如何管理技能、工具与模块

> 🌐 **语言：** [English](../../en/how-to/manage-skills-and-tools.md) · [Русский](../../ru/how-to/manage-skills-and-tools.md) · **简体中文**

Veles 会随时间累积能力。**技能（skills）**是可复用的工作流，**工具（tools）**是可执行的动作，**模块（modules）**是可选的插件。每一种都存在于两个作用域：项目本地（`<project>/.veles/`）和用户全局（`~/.veles/`）。关于这些概念，参见[技能与工具](../explanation/skills-and-tools.md)。

## 技能

技能是一个 `SKILL.md`（frontmatter + 提示正文），智能体可以像调用工具一样调用它。

```bash
veles skill list                          # installed skills + telemetry
veles skill show <name>                   # print its SKILL.md
veles skill add https://github.com/org/skill.git
veles skill add ./local-skill --scope user   # install user-global
veles skill remove <name>
```

### 在作用域之间晋升 / 降级

一个在某个项目中被证明有用的技能可以移动到用户作用域，这样每个项目都能看到它（反之亦可）：

```bash
veles skill promote <name>     # project → ~/.veles/skills/
veles skill demote  <name>     # user → this project
```

### 查找重复项和晋升候选

```bash
veles skill dedup                         # near-duplicate skills (embedding/TF-IDF)
veles skill suggest-promote --save        # skills that meet the auto-promote bar
```

## 工具

工具会连同使用遥测一起编目到项目的 `memory.db` 中。Veles 在工作过程中可以编写自己的工具；你可以用以下命令管理它们：

```bash
veles tool list                # tools in this project
veles tool show <name>         # manifest + telemetry
veles tool promote <name>      # move to ~/.veles/tools/ (cross-project)
```

敏感工具（`run_shell`、`write_file`、`fetch_url`……）受[信任阶梯](security-and-permissions.md)管控。

## 模块

模块在不让核心臃肿的前提下添加可选能力（embeddings、vision、STT）。安装一个模块默认需要确认。

```bash
veles module list
veles module add https://github.com/org/module.git
veles module remove <name>
```

## 发现更多

浏览精选的注册表：

```bash
veles browse skills [query]
veles browse modules [query]
```

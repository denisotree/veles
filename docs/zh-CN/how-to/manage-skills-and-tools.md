# 如何管理技能、工具与模块

> 🌐 **语言：** [English](../../en/how-to/manage-skills-and-tools.md) · **简体中文** · [繁體中文](../../zh-TW/how-to/manage-skills-and-tools.md) · [日本語](../../ja/how-to/manage-skills-and-tools.md) · [한국어](../../ko/how-to/manage-skills-and-tools.md) · [Español](../../es/how-to/manage-skills-and-tools.md) · [Français](../../fr/how-to/manage-skills-and-tools.md) · [Italiano](../../it/how-to/manage-skills-and-tools.md) · [Português (BR)](../../pt-BR/how-to/manage-skills-and-tools.md) · [Português (PT)](../../pt-PT/how-to/manage-skills-and-tools.md) · [Русский](../../ru/how-to/manage-skills-and-tools.md) · [العربية](../../ar/how-to/manage-skills-and-tools.md) · [हिन्दी](../../hi/how-to/manage-skills-and-tools.md) · [বাংলা](../../bn/how-to/manage-skills-and-tools.md) · [Tiếng Việt](../../vi/how-to/manage-skills-and-tools.md)

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

模块是在 Veles 内部运行的 Python 代码（`module.toml` + 一个入口点）——在不让核心臃肿的前提下添加可选能力（记忆提供方、embeddings、vision、STT）。安装一个模块默认需要确认，并且只有当它的文件仍与你批准的内容一致时才会在每次运行中加载（参见[保持安装可信](extension-registries.md#keep-installs-honest)）。

```bash
veles module list                              # 两个作用域，带 `scope` 列
veles module add https://github.com/org/module.git
veles module add ./local-module --user          # 安装到 ~/.veles/modules/，对所有项目生效
veles module show <name> [--user]             # 清单 + 文件 sha256
veles module remove <name> [--user]
veles module approve <name> [--user]          # 在终端中输入 `yes`
veles module approve <name> --sha256 <hash>   # 无终端时：你审阅过的哈希
```

与技能和工具一样，模块存在于两个作用域：项目本地（`<project>/.veles/modules/`）和用户全局（`~/.veles/modules/`，在每个项目中加载）。用户级模块与项目级模块经过同样的批准门禁，且门禁在比较名称之前运行。如果项目模块与用户模块同名，已批准的项目模块会加载，Veles 会警告用户级模块被遮蔽；未批准的项目模块会被跳过（警告中会指明其目录），此时加载用户模块。同一作用域内两个已批准的模块同名时——按目录排序的第一个加载，其余的发出警告并被跳过。`veles module {show,approve,remove}` 接受清单名称（`list` 显示的名称），并会拒绝该作用域内被多个目录声明的名称，同时列出这些目录；`veles module add` 会拒绝安装名称已被该作用域内另一个目录声明的模块。

### 编写添加记忆提供方的模块

模块的 `register(api)` 入口点可以调用 `api.add_memory_provider(name, factory)`，把外部记忆源接入召回。`name` 必须与 `~/.veles/config.toml` 中的某个 `[memory.external.<name>]` 段一致；`factory` 会以该段（一个 `dict`）为参数被调用，并且必须返回一个实现了 Veles 的 `MemoryProvider` 协议（`veles.core.memory.provider`）的对象，或返回 `None` 以跳过该提供方：

```toml
# module.toml
[module]
name = "my-provider"
description = "Recalls memories from my external store."
entrypoint = "my_provider.py:register"
version = "0.1.0"
```

```python
# my_provider.py
from veles.core.memory.provider import RecallHit


class MyProvider:
    name = "my-provider"

    def recall(self, query: str, *, limit: int) -> list[RecallHit]:
        ...  # query the external store, return RecallHit objects


def _build(cfg: dict) -> MyProvider | None:
    api_key = cfg.get("api_key")
    return MyProvider() if api_key else None


def register(api) -> None:
    api.add_memory_provider("my-provider", _build)
```

```toml
# ~/.veles/config.toml
[memory.external.my-provider]
api_key = "..."
```

如果提供方还实现了 `ingest(title, body, *, insight_id) -> bool`（`IngestingMemoryProvider` 协议），它也会收到 Veles 的写入，而不只是读取。如果两个模块注册了同一个提供方名称，第二个模块会加载失败——它会带警告被跳过，不会留下任何部分注册的内容。在 `config.toml` 中配置了某个段、但对应模块并未安装时，会打印一条带安装命令的警告；召回照常工作。

注册表提供 Honcho、Mem0 和 Supermemory 作为现成的提供方模块——用 `veles registry install --user {honcho,mem0,supermemory}` 安装，然后运行安装时打印的 `uv tool install veles-ai --with '<package>'` 命令（每个模块都声明了一个 SDK——`mem0ai>=2.0`、`honcho-ai>=2.5`、`supermemory>=3.62`——Veles 绝不会替你安装），并填写对应的 `[memory.external.<name>]` 段：

- **mem0**：`api_key`、`user_id`，可选 `agent_id`（同时召回该智能体的记忆）和 `host`。SDK 遥测默认关闭；每次召回会多发出一次 `GET /v1/ping/` 请求。
- **supermemory**：`api_key`，可选 `user_id`（作为搜索的 `container_tag` 发送）和 `base_url`。
- **honcho**：`api_key`、`workspace_id`，可选 `peer_id`（仅搜索该 peer 的消息）和 `base_url`。每次召回都会执行一次 workspace get-or-create——如果 `workspace_id` 尚不存在就会创建它。

## 发现更多

在已连接的注册表中搜索：

```bash
veles registry search [query] [--kind module|skill|layout|mcp]
```

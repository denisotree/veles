# 项目布局与状态

> 🌐 **语言：** [English](../../en/reference/project-layout.md) · **简体中文** · [繁體中文](../../zh-TW/reference/project-layout.md) · [日本語](../../ja/reference/project-layout.md) · [한국어](../../ko/reference/project-layout.md) · [Español](../../es/reference/project-layout.md) · [Français](../../fr/reference/project-layout.md) · [Italiano](../../it/reference/project-layout.md) · [Português (BR)](../../pt-BR/reference/project-layout.md) · [Português (PT)](../../pt-PT/reference/project-layout.md) · [Русский](../../ru/reference/project-layout.md) · [العربية](../../ar/reference/project-layout.md) · [हिन्दी](../../hi/reference/project-layout.md) · [বাংলা](../../bn/reference/project-layout.md) · [Tiếng Việt](../../vi/reference/project-layout.md)

`veles init` 会创建什么、Veles 把状态保存在哪里，以及项目记忆的架构。

## `veles init` 产出的内容

用户内容那一半取决于所选的布局包（`--layout`，
默认 `llm-wiki`）；而 `.veles/` 状态那一半在任何情况下都是一致的。

```
my-project/                  # veles init  (default llm-wiki layout)
├── AGENTS.md                # project context (injected into the agent)
├── CLAUDE.md → AGENTS.md    # symlink, so a `claude` CLI picks up the same context
├── GEMINI.md → AGENTS.md    # symlink, for a `gemini` CLI
├── sources/                 # raw, immutable source material (agent-readonly)
├── wiki/                    # the LLM-writable knowledge zone
│   ├── concepts/ entities/ queries/ self-doc/ sessions/ sources/
└── .veles/                  # project state (do not commit; machine-managed)
    ├── project.toml         # name, created_at, schema_version, layout
    ├── memory.db            # SQLite: sessions, turns, insights, rules, telemetry
    ├── memory/              # the agent's own memory artefacts:
    │   ├── LOG.md           #   append-only system-ops journal
    │   ├── insights/        #   rendered views of `insights` rows
    │   ├── sessions/        #   compaction summaries
    │   └── proposals/       #   subproject / skill-promotion proposals
    ├── jobs/                # scheduled-job outputs
    └── skills/              # project-local skills
```

使用 `--layout notes` 时，内容那一半是单个 `notes/` 目录；使用
`--layout bare` 时则完全没有内容脚手架。`wiki/INDEX.md`（按需
目录）会随着 wiki 的增长而生成；`config.toml`、`tools/`
和 `plans/` 会在你配置了某些内容、某个智能体
写入了工具，或你运行了某个目标后，出现在 `.veles/` 下。

## 状态目录

| 路径 | 作用域 | 是否提交？ |
|---|---|---|
| `<project>/AGENTS.md` + 布局内容（`wiki/`、`sources/`、`notes/`、…） | 项目内容 | **是**——这是你的知识库 |
| `<project>/.veles/` | 项目机器状态（记忆、配置、本地技能/工具） | 否 |
| `~/.veles/` | 用户全局：`config.toml`、信任授权、跨项目技能/工具、布局包、模型缓存、语言环境 | 否 |

`VELES_USER_HOME` 会为用户全局目录树重定向 `~`（测试、沙箱用）。

## 项目记忆（`.veles/memory.db` + `.veles/memory/`）

Veles 的项目记忆是一份**结构化产物**，与你的
内容相分离且与布局无关。SQLite 数据库（WAL 模式）是
真相来源；`.veles/memory/` 保存可供人阅读的那一侧（渲染后的
洞察视图、会话摘要、提案、系统操作日志）。
关键表：

| 表 | 保存内容 |
|---|---|
| `sessions`、`turns` | 对话历史（每个轮次一行） |
| `turns_fts` | 轮次的全文索引（驱动 `veles sessions search`） |
| `insights`、`insights_fts`、`insight_refs` | 习得的洞察（规范行；markdown 视图可重新生成）+ 去重链接 |
| `rules`、`rules_fts` | 注入到稳定提示中的格式/该做/不该做/偏好规则 |
| `skills`、`skill_uses`、`skill_tool_refs` | 技能注册表 + 遥测 + 工具链接 |
| `tools`、`tool_uses` | 工具注册表 + 遥测（使用/成功/错误计数） |
| `project_tree` | 缓存的项目文件映射 + 用于相关性排序的语义标签 |

关于这些内容如何写入和召回，参见
[项目记忆与学习循环](../explanation/project-memory-and-learning-loop.md)。

## 布局包

`veles init --layout {llm-wiki|notes|bare|<custom>}` 选择内容
布局；布局包拥有脚手架、AGENTS.md 模板、可写区域，
以及 wiki 引擎（wiki 工具、INDEX 提示注入、wiki
召回）是否启用。参见
[布局包与 LLM-Wiki](../explanation/layout-packs-and-llm-wiki.md)。

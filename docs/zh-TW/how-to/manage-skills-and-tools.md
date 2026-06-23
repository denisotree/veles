# 如何管理 skills、tools 與 modules

> 🌐 **語言：** **English** · [Русский](../../ru/how-to/manage-skills-and-tools.md)

Veles 會隨著時間累積能力。**Skills** 是可重複使用的工作流程，
**tools** 是可執行的動作，**modules** 是選用的外掛。每一種都存在於兩個範圍：
project-local（`<project>/.veles/`）與 user-global（`~/.veles/`）。關於這些概念，
請參閱 [skills & tools](../explanation/skills-and-tools.md)。

## Skills

skill 是一個 `SKILL.md`（frontmatter + prompt 主體），agent 可以像呼叫 tool 一樣
呼叫它。

```bash
veles skill list                          # installed skills + telemetry
veles skill show <name>                   # print its SKILL.md
veles skill add https://github.com/org/skill.git
veles skill add ./local-skill --scope user   # install user-global
veles skill remove <name>
```

### 在範圍之間 promote / demote

一個在某個專案中證明有用的 skill 可以移到 user 範圍，讓每個專案都能看到它
（或者反過來）：

```bash
veles skill promote <name>     # project → ~/.veles/skills/
veles skill demote  <name>     # user → this project
```

### 找出重複項與 promotion 候選

```bash
veles skill dedup                         # near-duplicate skills (embedding/TF-IDF)
veles skill suggest-promote --save        # skills that meet the auto-promote bar
```

## Tools

Tools 會連同使用 telemetry 一起編入專案的 `memory.db`。Veles 在工作過程中可以
撰寫自己的 tools；你可以用以下指令管理它們：

```bash
veles tool list                # tools in this project
veles tool show <name>         # manifest + telemetry
veles tool promote <name>      # move to ~/.veles/tools/ (cross-project)
```

敏感的 tools（`run_shell`、`write_file`、`fetch_url`……）會受到
[trust ladder](security-and-permissions.md) 的把關。

## Modules

Modules 在不讓核心臃腫的前提下加入選用能力（embeddings、vision、STT）。
預設情況下，安裝一個 module 需要確認。

```bash
veles module list
veles module add https://github.com/org/module.git
veles module remove <name>
```

## 探索更多

瀏覽經過策劃的 registries：

```bash
veles browse skills [query]
veles browse modules [query]
```

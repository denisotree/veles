---
title: Work across multiple projects and subprojects
topics: [project, subproject, multi-project, switch, register, workspace]
related: ["cmd:project", "cmd:subproject"]
---

Use `veles project {list,add,remove,switch}` to manage the multi-project
registry: `list` shows registered projects most-recent first, `add <dir>`
registers an existing Veles project, `switch <name>` prints its path (for
`cd $(veles project switch name)`).

Use `veles subproject {init,list,switch,remove,suggest}` for vertical
subprojects nested under the active project — each gets its own context and
knowledge base. `veles subproject suggest` detects thematic clusters in the
wiki and proposes them as candidate subprojects.

Example: `veles project switch my-app`.

---
title: Manage agent skills
topics: [skill, skills, capability, promote, demote, extends, install]
related: ["cmd:skill", "skill:tool_authoring", "skill:tool_installer"]
---

Use `veles skill {list,show,add,remove,promote,demote,dedup,suggest-promote}`
to manage the skills available to the agent. A skill is a formalised,
repeating process (`SKILL.md`, optionally with `extends:` a base skill) that
accumulates capability over time.

`veles skill add <git-url-or-dir>` installs a skill; `veles skill promote
<name>` copies a project-scope skill to user-global scope (`~/.veles/skills`)
so every project can reuse it; `veles skill dedup` finds near-duplicates.

Example: `veles skill list` then `veles skill promote my-skill`.

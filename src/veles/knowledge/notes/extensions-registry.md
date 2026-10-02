---
title: Install extensions from registries
topics: [registry, registries, extension, extensions, install, module, marketplace, private, company]
related: ["cmd:registry", "cmd:module"]
---

Extensions (modules, skills, layout packs, MCP recipes) come from git registries.
`public` is built in; connect a private or company one with
`veles registry add <git-url>` (it becomes `private`).

`veles registry search <query>` finds extensions; `veles registry install <name>`
(or `private:<name>`) installs one after you confirm. Add `--user` to install a
module or skill to `~/.veles/`, loaded in every project — that's how you set up
a memory-provider module (Honcho, Mem0, Supermemory). `veles registry verify`
reports changed, yanked, removed or outdated installs (and vendored copies whose
upstream moved ahead); `veles registry upgrade` moves to a
newer version and shows the diff. Layouts come from here too:
`veles registry install llm-wiki` installs the wiki layout together with the
`wiki` module it needs, under one confirmation. A project whose layout isn't
installed offers the install when you open it at a terminal.

A module only loads while its files match what you approved. After editing one on
purpose, run `veles module approve <name>`.

To start your own registry: `veles registry init <dir> --name acme`.

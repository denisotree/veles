---
title: Install extensions from registries
topics: [registry, registries, extension, extensions, install, module, marketplace, private, company]
related: ["cmd:registry", "cmd:module"]
---

Extensions (modules, skills, layout packs, MCP recipes) come from git registries.
`public` is built in; connect a private or company one with
`veles registry add <git-url>` (it becomes `private`).

`veles registry search <query>` finds extensions; `veles registry install <name>`
(or `private:<name>`) installs one after you confirm. `veles registry verify`
reports changed, yanked or outdated installs; `veles registry upgrade` moves to a
newer version and shows the diff.

A module only loads while its files match what you approved. After editing one on
purpose, run `veles module approve <name>`.

To start your own registry: `veles registry init <dir> --name acme`.

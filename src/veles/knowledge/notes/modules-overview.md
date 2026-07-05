---
title: Manage agent modules (plugins)
topics: [module, modules, plugin, install, remove, extension]
related: ["cmd:module"]
---

Use `veles module {list,show,add,remove}` to manage optional, pluggable
modules (gateways, extra tooling) installed into a project.

`veles module add <git-url-or-dir>` installs a module; `veles module show
<name>` prints its manifest; `veles module remove <name>` deletes it. Modules
are separate from skills: skills are behavioural recipes, modules are
installable plugin packages.

Example: `veles module list`.

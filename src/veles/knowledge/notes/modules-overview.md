---
title: Manage agent modules (plugins)
topics: [module, modules, plugin, install, remove, approve, extension]
related: ["cmd:module"]
---

Use `veles module {list,show,add,remove,approve}` to manage optional,
pluggable modules (gateways, extra tooling) installed into a project.
`veles registry install <name>` installs a reviewed module from a connected
registry — see the extensions-registry note.

`veles module add <git-url-or-dir>` installs a module from a raw source;
`veles module show <name>` prints its manifest; `veles module remove <name>`
deletes it. Modules are separate from skills: skills are behavioural
recipes, modules are installable plugin packages.

A module loads only while its files match what was approved (a registry
install, `module add`, or an explicit approval). If you edit a module's code
by hand, it stops loading until you run `veles module approve <name>`.

Example: `veles module list`.

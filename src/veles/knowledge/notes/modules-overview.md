---
title: Manage agent modules (plugins)
topics: [module, modules, plugin, install, remove, approve, extension]
related: ["cmd:module"]
---

Use `veles module {list,show,add,remove,approve}` to manage optional,
pluggable modules (gateways, extra tooling, memory providers) installed into
a project. `veles registry install <name>` installs a reviewed module from a
connected registry — see the extensions-registry note.

`veles module add <git-url-or-dir>` installs a module from a raw source;
`veles module show <name>` prints its manifest; `veles module remove <name>`
deletes it. Modules are separate from skills: skills are behavioural
recipes, modules are installable plugin packages.

Modules live at two scopes: project-local (`<project>/.veles/modules/`) and
user-global (`~/.veles/modules/`, loaded in every project). Add `--user` to
any module subcommand for the user scope; `veles module list` (no flag) shows
both with a `scope` column. A project module overrides a same-named
user-level one, with a warning.

A module loads only while its files match what was approved (a registry
install, `module add`, or an explicit approval). If you edit a module's code
by hand, it stops loading until you run `veles module approve <name>`.

A module can plug a memory source into recall with
`api.add_memory_provider(name, factory)` in its `register(api)`, matched to a
`[memory.external.<name>]` config section — that's how Honcho, Mem0 and
Supermemory work as registry modules. More generally, `api.contribute(point,
name, obj)` adds tools, recall, prompt blocks, dream steps, a curator target,
a page store, a `veles` verb, a REPL `/command`, a scaffold or a daemon job
kind — the registry's wiki engine is a module that does exactly this (see
how-to/extend-veles-with-modules). Modules import Veles through `veles.sdk`.

Example: `veles module list`.

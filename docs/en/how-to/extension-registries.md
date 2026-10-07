# How to install extensions from registries

> 🌐 **Languages:** **English** · [简体中文](../../zh-CN/how-to/extension-registries.md) · [繁體中文](../../zh-TW/how-to/extension-registries.md) · [日本語](../../ja/how-to/extension-registries.md) · [한국어](../../ko/how-to/extension-registries.md) · [Español](../../es/how-to/extension-registries.md) · [Français](../../fr/how-to/extension-registries.md) · [Italiano](../../it/how-to/extension-registries.md) · [Português (BR)](../../pt-BR/how-to/extension-registries.md) · [Português (PT)](../../pt-PT/how-to/extension-registries.md) · [Русский](../../ru/how-to/extension-registries.md) · [العربية](../../ar/how-to/extension-registries.md) · [हिन्दी](../../hi/how-to/extension-registries.md) · [বাংলা](../../bn/how-to/extension-registries.md) · [Tiếng Việt](../../vi/how-to/extension-registries.md)

A registry is a plain git repository that holds reviewed extensions — modules,
skills, layout packs, and MCP server recipes. `veles registry` connects to one,
finds an extension, and installs it after you confirm.

## Connect a registry

The built-in `public` registry (`https://github.com/denisotree/veles-registry`)
is already connected. Add a private or company one:

```bash
veles registry add https://github.com/acme/veles-registry.git   # → named "private"
veles registry add git@github.com:acme/veles-registry.git --name acme --ref main
veles registry list                                              # url, ref, cache commit, fetch date
veles registry remove public                                     # disconnect one you don't want
```

An unnamed `add` becomes `private`; adding a second unnamed registry is an
error asking you to pass `--name`. Clones live outside the sandbox, in
`~/.veles/registries/<name>/` — Veles calls the system `git` and never stores
credentials itself. Private access works through your own SSH keys or git
credential helper (`gh auth setup-git` is the usual one-time setup for
GitHub). A registry is cloned once, on first use (`add`, or the first
`search`/`install` that needs it) — after that, `search` and `install` only
read the local clone and never touch the network again. Run `veles registry
update` to fetch the latest; if that fails, it prints an error for that
registry and leaves the existing clone exactly as it was.

## Find and install

```bash
veles registry search                       # everything in every connected registry
veles registry search slack --kind module    # substring filter + kind (module|skill|layout|mcp)
veles registry install slack                 # bare name — unambiguous if only one registry has it
veles registry install private:vendor/slack  # registry:group/name — the ref search prints
```

`search` prints one entry per hit — `registry:group/name  version  kind`
(plus `[YANKED: reason]` when it's yanked) with the description indented on
the line below. A bare `name` resolves as long as it's unambiguous; if more
than one registry (or, within one registry, more than one group) has an
extension by that name, `install` refuses and lists every matching
`registry:group/name` ref to disambiguate with.

Before installing, Veles checks `requires_veles` against your Veles version
and refuses a yanked extension unless you pass `--force`. It then shows a
summary — kind, version, registry/group, what it provides and requires, and
its license — and asks you to confirm through `confirm_critical`; installing
code always goes through this gate, and `--yes` does not bypass it. Where an
extension declares `requires` (pip packages), Veles prints the `uv tool
install` command to run — it never installs Python dependencies for you.
Each kind lands in its usual place: modules in `<project>/.veles/modules/<name>/`
and skills in `<project>/.veles/skills/<name>/` (`--user` installs either one to
`~/.veles/{modules,skills}/<name>/` instead, loaded in every project), layout
packs in `~/.veles/layouts/<name>/`, and an `mcp` recipe as a
`[mcp.servers.<name>]` block in the project's `config.toml`. A user-level
module is how you install a memory-provider module (Honcho, Mem0, Supermemory,
…) — see [manage skills, tools & modules](manage-skills-and-tools.md#modules).

An extension can need another one (`requires_extensions` in its
`extension.toml`). `veles registry install llm-wiki` installs the `wiki` module
it needs too: one confirmation lists every package, dependencies install first,
and if any of them fails nothing from that call is left behind. A layout's
dependencies install for the user, like the layout itself. `veles registry
uninstall wiki` refuses while an installed extension needs it (`--force`
overrides); `verify` and `doctor` report a missing dependency. A dependency
can be a module, a layout or a skill — a module or a layout can bring the
skills its workflow uses — but not an `mcp` recipe.

When the same name is installed both for the user and in the project,
`uninstall` and `upgrade` ask which one: pass `--user` or `--project`.

A project whose layout or content engine isn't installed (for instance an
`llm-wiki` project after upgrading to 1.2.3) offers the install when you start
`veles` or `veles run` at a terminal; elsewhere Veles prints the install command
once and carries on without it.

The agent has the read-only half of this on its own: it can call
`registry_search` to see what's available and propose `registry_install`, but
the same confirmation gate applies — nothing installs without you approving
it, and autopilot does not skip it.

## Keep installs honest

Every install is recorded with its registry, version, git commit and a
content hash of its files (`tree_sha256`). A module only *loads* while its
files still match that hash — edit one on purpose and it stops loading until
you review the change and run `veles module approve <name>`. Both `veles
registry install` and `veles module add` approve the module automatically
right after installing it, so a normal install just works on the next run;
only a module you drop into `.veles/modules/` by hand, or one you edit after
it was approved, needs an explicit `veles module approve <name>`.

```bash
veles registry verify     # drift, yanked extensions, and available upgrades
veles registry upgrade    # every registry-installed extension, one by one
veles registry upgrade slack   # or just one — shows the file diff before confirming
veles doctor               # includes an "extensions" check
```

A bare `upgrade` walks every registry-installed extension and upgrades each
in turn; a failure on one is reported and does not stop the rest, but the
command exits 1 if any of them failed. `doctor`'s `extensions` check treats a
missing or modified installed extension as an **error** — that fails
`doctor`'s exit code — while a revoked one (marked `yanked`, or whose
directory was deleted from its registry — reported as `removed` once you've
run `veles registry update`) is only a **warning**: `doctor` still exits 0
for it unless you pass `--strict`. A vendored extension whose upstream has
published a newer version is reported as `upstream-ahead` — information,
not a problem.

Skills aren't gated this way — they're text, not executable code — but
`verify` still reports if one has drifted from what you installed.

## Publish an extension

```bash
veles registry scaffold module slack --group community --root ./veles-registry
# … write the module, add tests under its payload's tests/ …
veles registry validate . --base main   # only what changed since the base ref
```

`scaffold` drops a skeleton (`extension.toml` + the kind's payload, e.g.
`module.toml` + Python for a module) under `extensions/<group>/<name>/` in the
registry you point `--root` at. `validate` is the **one** implementation of a
registry's CI checks — the same code you run locally, a reviewer runs
locally, and CI runs — so there's no separate "CI-only" rule set to guess at.
By default it's static: it checks the schema, slugs, semver, uniqueness of
`name`, that a `git`-sourced extension pins a full commit SHA and its tree
hash matches, that the payload matches its `kind` (a module's manifest and
entry point parse, a skill's `SKILL.md` frontmatter is valid, a layout's
`layout.toml` loads, an `mcp` recipe matches the `[mcp.servers]` schema), that
`version` grew if the payload or source changed, that `public = true`
registries only accept permissive licenses, that every `requires_extensions`
ref names an existing module, layout or skill — in the same registry or in the
connected registry it names (a registry not connected where `validate` runs is
left to the reviewer, with a note) — and the refs form no cycle, and that a
module imports Veles **only through `veles.sdk`** (its tests are exempt — they
run against a pinned Veles; see [extend Veles with modules](extend-veles-with-modules.md)).
`--run-code` additionally imports
the module and runs its `tests/` — that flag is meant for CI only, since it
executes the code under review; a local `validate` run by a reviewer stays
static. `--install-requires` (implies `--run-code`) first installs each module's
`requires` into a throwaway directory (pinned to the versions Veles runs with),
so tests that drive a real SDK run instead of skipping; the generated CI passes
it. Test-only dependencies (a mocking library such as `respx`) go into the CI
command with `uvx --with`. `--report FILE` writes a non-blocking Markdown report for the
reviewer: a static scan for `subprocess`/`os.system`, `eval`/`exec`, network
access, writes outside the project, `os.environ` reads, dynamic imports,
native binaries (`.so`/`.pyd`/`.dylib`/`.dll` — code nobody can read), and the
extension's declared `requires`. `search` and `install` warn when a registry
clone hasn't been fetched for a week or more.

From there: fork the registry, open a PR (for a `git`-sourced extension, only
`extension.toml` changes), and let the registry's CI post the validate report
and gate the merge. There is no separate "approved" flag — review means the
PR merged to the registry's main branch, so trust is scoped to the registry,
not to an individual extension.

## Run a company registry

```bash
veles registry init veles-registry --name acme --ci github   # or --ci gitlab / --ci none
cd veles-registry && git init && git add -A && git commit -m "init registry"
# push it, then enable branch protection on the host (Veles doesn't touch the host's API)
```

`init` generates the same template `public` was built from: `registry.toml`,
a working example module and example skill under `extensions/internal/`, a CI
workflow for the chosen host that runs `validate` with the Veles version
pinned at generation time, a `CODEOWNERS` stub (`@<org>/security`), and a PR
template with a reviewer checklist (purpose, permissions and side effects,
where data goes, pip dependencies, tests). Pass `--public` only for a
registry meant to accept permissive-license extensions from outside
contributors — company registries usually leave it off.

Bring in a reviewed external extension without exposing employees to an
upstream you don't control:

```bash
veles registry vendor public:community/slack --into ../veles-registry --group vendor
```

`vendor` copies the extension's payload into your registry as a `path`
source, tagging it with `upstream = "public:slack@<sha>"` so your own
`verify` can tell you later when the upstream has moved on (it compares
versions whenever the upstream registry is connected and fetched). The
alternative — a `git`-sourced record pinned to the upstream commit — works
too, but `vendor` is what security review usually wants: the code lives in,
and is reviewed inside, the company's own repository.

**Private consulting modules.** A closed registry (e.g.
`denisotree/veles-registry-pro`, `license = "Proprietary"`) works exactly
like any other private registry — a client either gets read access and runs
`veles registry add <url> --name pro`, or, preferably for their security
team, you `vendor` the module into *their* registry so the code is reviewed
and hosted on their side.

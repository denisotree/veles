# How to manage security: trust, autopilot, secrets

> 🌐 **Languages:** **English** · [简体中文](../../zh-CN/how-to/security-and-permissions.md) · [繁體中文](../../zh-TW/how-to/security-and-permissions.md) · [日本語](../../ja/how-to/security-and-permissions.md) · [한국어](../../ko/how-to/security-and-permissions.md) · [Español](../../es/how-to/security-and-permissions.md) · [Français](../../fr/how-to/security-and-permissions.md) · [Italiano](../../it/how-to/security-and-permissions.md) · [Português (BR)](../../pt-BR/how-to/security-and-permissions.md) · [Português (PT)](../../pt-PT/how-to/security-and-permissions.md) · [Русский](../../ru/how-to/security-and-permissions.md) · [العربية](../../ar/how-to/security-and-permissions.md) · [हिन्दी](../../hi/how-to/security-and-permissions.md) · [বাংলা](../../bn/how-to/security-and-permissions.md) · [Tiếng Việt](../../vi/how-to/security-and-permissions.md)

Veles gates dangerous actions behind a **trust ladder**, sandboxes file access,
and keeps secrets in the OS keychain. For the rationale, see
[trust & the sandbox](../explanation/trust-and-sandbox.md).

## The trust ladder

Sensitive tools (`run_shell`, `write_file`, `fetch_url`, …) prompt before running.
You choose: allow **once**, **always for this project**, **always everywhere**, or
**refuse**. Grants persist so you're not asked again.

Manage grants without waiting for a prompt:

```bash
veles trust list                          # current grants (user + project)
veles trust set run_shell --scope project # pre-grant for this project
veles trust set write_file --scope user   # pre-grant everywhere
veles trust revoke run_shell              # remove a grant
veles trust clear --scope all             # wipe everything
```

Some actions are **always confirmed** even with a grant — deleting files, fetching
URLs, installing a new skill/tool/module, connecting a channel, and writing
outside the project.

## Autopilot — a time-boxed bypass

For an unattended run (an overnight batch), open a window where trust prompts
auto-allow:

```bash
veles autopilot enable --until +2h
veles autopilot enable --until 2026-12-31T23:00:00Z
veles autopilot status
veles autopilot disable
```

Every autopilot action is logged for later review. Non-interactive contexts
(daemon, batch) refuse by default unless autopilot is active.

## Secrets

API keys and bot tokens live in the OS keychain, never in config files:

```bash
veles secret set OPENROUTER_API_KEY       # prompts (or pipe via stdin)
veles secret list                         # which secrets are configured
veles secret get OPENROUTER_API_KEY --reveal
veles secret delete OPENROUTER_API_KEY
veles secret set OPENROUTER_API_KEY --project myproj   # a key for one project only
```

Lookup falls back to the matching [environment variable](../reference/environment-variables.md)
unless you pass `--no-env-fallback`.

## The sandbox

Tools can read inside the active project, `~/.veles/skills/` and `~/.veles/locales/`,
and write only inside the
project — or only to the layout's writable zones, when the layout declares them. Override the roots for
advanced setups with `VELES_SANDBOX_ROOTS` (`:`-separated). URL fetches keep an
SSRF deny-list; `VELES_FETCH_ALLOW_PRIVATE=1` lifts the private-network block.

Inside the project's `.veles/` the agent's file tools may write only to `skills/`,
`tools/`, `tmp/`, `plans/`, `memory/` and `artifacts/`. Everything else there —
`trust.json`, `config.toml`, `project.toml`, `modules/`, `wiki.toml`, `memory.db` —
changes only through `veles` commands and Veles' own tools. The file tools also refuse
any other `.veles/` directory in the project (a subproject's, or one the agent would plant
in `wiki/`) at any depth. So through its file tools the agent can't grant itself trust
or add code that Veles would run (a tool it writes to `.veles/tools/` loads only after you
approve its file). Other spellings of the same file (case, `..`, a symlink) are refused
too.

Files that run without an explicit command or steer an agent CLI — anything under
`.git/`, `.githooks/`, `.claude/`, `.gemini/`, `.codex/`, `.vscode/`, `.devcontainer/`,
`.husky/`, and `.envrc`, `.mcp.json`, `.pre-commit-config.yaml`, `lefthook.yml`, at any
depth, plus — when the git repo sits at the project root — the `core.hooksPath` set in its
`.git/config` and wherever a symlinked `.git` points —
the agent's file tools write only after you confirm that write. Trust grants and
autopilot don't cover it; the daemon asks in the channel, and a batch run with nobody to
ask refuses.

The `claude-cli` and `gemini-cli` providers run as a model with Veles' tools only: their
own shell, file-edit and web tools, the project's `.claude/` settings and hooks, and
other MCP servers don't apply, and every Veles tool they call goes through the trust
ladder above (nobody can answer a prompt there, so anything not already granted is
refused).

Known limits:

- `run_shell` is a shell: once you grant it (or under autopilot) it can write any of
  the files above without the per-file confirmation.
- An MCP approval pins the server's command line, not the files it runs from the project
  (a script named in `args`) — review those too.
- With a CLI provider, runs that pre-authorise tools only for themselves (daemon
  background jobs, `veles research`) don't pass that on to the delegated CLI: its Veles
  tools need a standing `veles trust set` grant or an autopilot window. The parent run's
  planning mode doesn't reach them either.
- `gemini-cli` trusts the project folder for its run, so gemini also reads the project's
  `.env` — keep gemini settings you don't want the agent to steer out of it.
- On a machine with managed (system) gemini policies, gemini ignores the policy Veles
  passes, so `gemini-cli` isn't limited to Veles' tools there.

Paths with control characters (terminal escapes, bidi overrides) are refused, and
confirmations, the trust prompt and the diff preview show such characters escaped —
a tool call can't forge the text you approve.

MCP servers from a config start only after you approve them — see
[external MCP servers](external-mcp-servers.md#approve-inspect-and-test).

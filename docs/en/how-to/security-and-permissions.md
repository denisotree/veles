# How to manage security: trust, autopilot, secrets

> 🌐 **Languages:** **English** · [Русский](../../ru/how-to/security-and-permissions.md)

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
```

Lookup falls back to the matching [environment variable](../reference/environment-variables.md)
unless you pass `--no-env-fallback`.

## The sandbox

Tools can read inside the active project and `~/.veles/`, and write only to the
layout's writable zones (`wiki/`, `.veles/` by default). Override the roots for
advanced setups with `VELES_SANDBOX_ROOTS` (`:`-separated). URL fetches keep an
SSRF deny-list; `VELES_FETCH_ALLOW_PRIVATE=1` lifts the private-network block.

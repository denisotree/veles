# Trust & the sandbox

> 🌐 **Languages:** **English** · [简体中文](../../zh-CN/explanation/trust-and-sandbox.md) · [繁體中文](../../zh-TW/explanation/trust-and-sandbox.md) · [日本語](../../ja/explanation/trust-and-sandbox.md) · [한국어](../../ko/explanation/trust-and-sandbox.md) · [Español](../../es/explanation/trust-and-sandbox.md) · [Français](../../fr/explanation/trust-and-sandbox.md) · [Italiano](../../it/explanation/trust-and-sandbox.md) · [Português (BR)](../../pt-BR/explanation/trust-and-sandbox.md) · [Português (PT)](../../pt-PT/explanation/trust-and-sandbox.md) · [Русский](../../ru/explanation/trust-and-sandbox.md) · [العربية](../../ar/explanation/trust-and-sandbox.md) · [हिन्दी](../../hi/explanation/trust-and-sandbox.md) · [বাংলা](../../bn/explanation/trust-and-sandbox.md) · [Tiếng Việt](../../vi/explanation/trust-and-sandbox.md)

Veles runs an autonomous agent on your machine, so it constrains what that agent
can do. Two mechanisms work together: a **trust ladder** for sensitive actions and
a **sandbox** for the filesystem. For the commands, see
[security & permissions](../how-to/security-and-permissions.md).

## The trust ladder

Not every tool is equal. Reading a file is harmless; running a shell command or
writing to disk is not. Sensitive tools (`run_shell`, `write_file`, `fetch_url`, …)
stop and ask before they run, offering four choices:

- **Once** — allow this single call.
- **Always for this project** — persist a project-scoped grant.
- **Always everywhere** — persist a user-scoped grant.
- **Refuse** — deny it.

Grants are stored so you aren't asked again. This gives you graduated control:
trust a tool once, in one project, or globally — your choice, made the first time
it matters.

### Always-confirm actions

Some operations are risky enough that Veles confirms them **even with a grant**:
deleting files, fetching URLs, installing a new skill/tool/module, connecting a
channel, and writing outside the project. These are outward-facing or
hard-to-reverse, so a standing grant shouldn't silently cover them.

### Non-interactive safety

In a daemon, batch, or other non-TTY context there's no human to prompt, so Veles
**refuses** sensitive actions by default — stray stdin can't sneak an approval. To
run unattended on purpose, open an [autopilot](../how-to/security-and-permissions.md#autopilot--a-time-boxed-bypass)
window; every autopilot action is logged for review.

## The filesystem sandbox

A path guard bounds where tools can read and write:

- **Read** — inside the active project (and its subprojects) plus `~/.veles/`.
- **Write** — only the layout's writable zones (e.g. `wiki/`); `.veles/` is always
  writable for machine state.

Symlinks that escape the sandbox are rejected, and `..` traversal is refused before
resolution. URL fetches keep an SSRF deny-list. Advanced setups can override the
roots with `VELES_SANDBOX_ROOTS`, or lift the private-network block with
`VELES_FETCH_ALLOW_PRIVATE=1` — both opt-in.

## Why this design

The goal is **useful autonomy without nasty surprises**: the agent can do real work
without a prompt on every read, but anything that could damage your machine, spend
money, or leave the box is gated — once, and then remembered to your taste.

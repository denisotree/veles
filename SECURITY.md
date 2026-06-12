# Security Policy

## Supported versions

Veles is pre-1.0; only the latest release (and `main`) receive security
fixes.

| Version | Supported |
| ------- | --------- |
| latest release / `main` | ✅ |
| older releases | ❌ |

## Reporting a vulnerability

**Please do not report security vulnerabilities through public GitHub
issues.**

Use GitHub's private vulnerability reporting: go to the repository's
**Security** tab → **Report a vulnerability**. You should receive a response
within a few days. Please include reproduction steps and the impact you
believe the issue has.

## Threat model notes

Veles is a local-first CLI agent. Security-relevant surfaces to be aware of
when reporting or reviewing:

- **The agent executes tools** (shell commands, file writes, URL fetches) on
  the user's machine. Sensitive calls are gated by the trust ladder
  (per-call prompts, `veles trust`, `veles autopilot` with audit logging),
  and file access is sandboxed to the active project directory — symlink
  escapes and `..` traversal are blocked (`core/sandbox/path_guard.py`,
  `core/layout/writable.py`). Bypasses of the sandbox or the trust ladder
  are vulnerabilities.
- **Untrusted content boundary.** Web pages and ingested documents are
  wrapped as untrusted input and secrets are redacted
  (`core/untrusted.py`). Prompt-injection escalations that cross this
  boundary into unattended tool execution are in scope.
- **The daemon** (`veles daemon`) binds `127.0.0.1` by default and requires
  bearer tokens for every endpoint except `/v1/health`. Authentication
  bypasses are vulnerabilities.
- **Secrets** are stored in the OS keychain (`veles secret`) — never in
  project files. Anything that causes a key to be written to disk or leak
  into session logs / exports is in scope (`veles export template` must stay
  PII/secret-free).

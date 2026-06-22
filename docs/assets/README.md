# README assets

Demo GIFs used by the top-level `README.md`, recorded with
[VHS](https://github.com/charmbracelet/vhs) from the `.tape` scripts here.

- `tui-hero.gif` — ask a question, get an answer grounded in project memory.
- `tui-tour.gif` — slash inspectors (`/status`, `/context`), mode switch, `/help`.
- `kb-ingest.gif` — `veles add` a source into a wiki page, then query it with a cited answer.
- `daemon-setup.gif` — `veles daemon start` in a fresh dir: the wizard brings up the
  daemon and connects a channel (pick channel type first, then its token + whitelist).
- `daemon-panel.gif` — bare `veles daemon` opens the control panel: a project → daemons →
  channels tree with start/stop/restart/delete and inline channel add/remove.

The TUI tapes type bare `veles` (it launches the TUI; `veles tui` is the long form).

## Regenerate

```bash
brew install vhs                       # ttyd + ffmpeg backend

# A throwaway project with a populated AGENTS.md ("research-vault" demo)
mkdir -p ~/veles-demo && cd ~/veles-demo && veles init
# …edit AGENTS.md, then warm the local model so the recorded turn streams fast:
veles run 'hi' >/dev/null 2>&1

# Run vhs from the project dir so bare `veles` picks it up:
vhs /path/to/repo/docs/assets/tui-hero.tape
vhs /path/to/repo/docs/assets/tui-tour.tape
vhs /path/to/repo/docs/assets/kb-ingest.tape
```

The hero tape assumes a local `ollama/qwen3:4b-instruct`; swap the provider
in the project/user config to record against any other backend.

### Daemon tapes

`daemon-setup.tape` runs in a **fresh, uninitialised** directory (the wizard only
fires when no project exists). `daemon-panel.tape` runs in that same directory
*after* the daemon is up, so the picker has a running daemon + channel to show.

The daemon binds a TCP port (`--port 8799` in the tape) — pick one not already
held by another `veles daemon`. The daemon is a single global instance keyed off
`~/.veles`; to record without colliding with a real daemon, isolate the run with
`VELES_USER_HOME=<tmpdir>` (its own pid file, registry, and config). The tape's
Telegram bot token is fake — fine for the recording (the daemon starts; only live
polling would need a real token), but delete it from the OS keychain afterwards
(`veles`'s `delete_provider_key("telegram", project=<name>)`).

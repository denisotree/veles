# README assets

Demo GIFs used by the top-level `README.md`, recorded with
[VHS](https://github.com/charmbracelet/vhs) from the `.tape` scripts here.

- `tui-hero.gif` — ask a question, get an answer grounded in project memory.
- `tui-tour.gif` — slash inspectors (`/status`, `/context`), mode switch, `/help`.
- `kb-ingest.gif` — `veles add` a source into a wiki page, then query it with a cited answer.

## Regenerate

```bash
brew install vhs                       # ttyd + ffmpeg backend

# A throwaway project with a populated AGENTS.md ("research-vault" demo)
mkdir -p ~/veles-demo && cd ~/veles-demo && veles init
# …edit AGENTS.md, then warm the local model so the recorded turn streams fast:
veles run 'hi' >/dev/null 2>&1

# Run vhs from the project dir so `veles tui` picks it up:
vhs /path/to/repo/docs/assets/tui-hero.tape
vhs /path/to/repo/docs/assets/tui-tour.tape
```

The hero tape assumes a local `ollama/qwen3:4b-instruct`; swap the provider
in the project/user config to record against any other backend.

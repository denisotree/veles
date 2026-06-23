# TUI keybindings & slash commands

> 🌐 **Languages:** **English** · [简体中文](../../zh-CN/reference/tui.md) · [繁體中文](../../zh-TW/reference/tui.md) · [日本語](../../ja/reference/tui.md) · [한국어](../../ko/reference/tui.md) · [Español](../../es/reference/tui.md) · [Français](../../fr/reference/tui.md) · [Italiano](../../it/reference/tui.md) · [Português (BR)](../../pt-BR/reference/tui.md) · [Português (PT)](../../pt-PT/reference/tui.md) · [Русский](../../ru/reference/tui.md) · [العربية](../../ar/reference/tui.md) · [हिन्दी](../../hi/reference/tui.md) · [বাংলা](../../bn/reference/tui.md) · [Tiếng Việt](../../vi/reference/tui.md)

`veles tui` (or bare `veles`) opens the interactive REPL. It is a scrollback chat
with a multi-line composer, a status bar, and a collapsible inspector.

## Keybindings

| Key | Action |
|---|---|
| `Ctrl+D` | Exit |
| `Ctrl+C` | Copy the last assistant reply; press twice within 1.5 s to exit |
| `Ctrl+V` | Paste from the clipboard |
| `Ctrl+Shift+C` / `⌘C` | Copy the current selection (OSC52). On macOS Terminal.app, native drag-select + ⌘C works directly |
| `Ctrl+I` | Toggle the inspector (reasoning, tool activity, token/error log) |
| `Ctrl+R` | Open the session picker (resume a past session) |
| `Ctrl+T` | Open the theme picker |
| `Shift+Tab` | Cycle the run mode: `auto → planning → writing → goal` |
| `Tab` | Cycle slash-command completions |
| `Up` / `Down` | History (and pop queued prompts) |

Run modes are explained in [Run modes](../explanation/modes.md).

## Slash commands

Type `/` in the composer; `Tab` completes. The registered commands are:

| Command | Purpose |
|---|---|
| `/help` | List available commands |
| `/quit`, `/q`, `/exit` | Exit the REPL |
| `/clear` | Clear the chat log |
| `/model` | Open the model picker |
| `/mode` | Switch run mode (auto/planning/writing/goal) |
| `/session` | Open the session picker (resume) |
| `/save` | Save / name the current session |
| `/history` | Show session history |
| `/tokens` | Token usage (in / out / per-turn / per-session) |
| `/context` | Current context size vs the limit |
| `/status` | Snapshot: model, provider, mode, session, busy, queue |
| `/insights` | Show learned insights for the project |
| `/rules` | Show the project's rules digest |
| `/schema` | Validate / fix `AGENTS.md` |
| `/wiki` | Wiki operations for the active layout |
| `/daemon` | Open the daemon control panel (project → daemons → channels) |

> The slash set is the same whether you launch the TUI directly or push it from
> another screen. Channels (e.g. Telegram) expose their own, separate command set.

## Themes

Built-in themes: `everforest` (default), `dracula`, `gruvbox`, `tokyo-night`,
`catppuccin`. Pick one with `Ctrl+T`, `veles tui --theme <name>`, or
`[user] tui_theme` in `~/.veles/config.toml`.

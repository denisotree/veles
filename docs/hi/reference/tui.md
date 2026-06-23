# TUI keybindings और slash commands

> 🌐 **भाषाएँ:** [English](../../en/reference/tui.md) · [简体中文](../../zh-CN/reference/tui.md) · [繁體中文](../../zh-TW/reference/tui.md) · [日本語](../../ja/reference/tui.md) · [한국어](../../ko/reference/tui.md) · [Español](../../es/reference/tui.md) · [Français](../../fr/reference/tui.md) · [Italiano](../../it/reference/tui.md) · [Português (BR)](../../pt-BR/reference/tui.md) · [Português (PT)](../../pt-PT/reference/tui.md) · [Русский](../../ru/reference/tui.md) · [العربية](../../ar/reference/tui.md) · **हिन्दी** · [বাংলা](../../bn/reference/tui.md) · [Tiếng Việt](../../vi/reference/tui.md)

`veles tui` (या केवल `veles`) interactive REPL खोलता है। यह एक scrollback chat है जिसमें
multi-line composer, एक status bar, और एक collapsible inspector होता है।

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

Run modes को [Run modes](../explanation/modes.md) में समझाया गया है।

## Slash commands

Composer में `/` टाइप करें; `Tab` complete करता है। रजिस्टर किए गए commands हैं:

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

> Slash set वही रहता है चाहे आप TUI को सीधे launch करें या किसी और screen से उसे push करें।
> Channels (जैसे Telegram) अपना अलग command set प्रदान करते हैं।

## Themes

Built-in themes: `everforest` (default), `dracula`, `gruvbox`, `tokyo-night`,
`catppuccin`। किसी एक को `Ctrl+T`, `veles tui --theme <name>`, या
`~/.veles/config.toml` में `[user] tui_theme` से चुनें।

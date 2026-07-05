# TUI keybindings & slash commands

> 🌐 **Languages:** **English** · [简体中文](../../zh-CN/reference/tui.md) · [繁體中文](../../zh-TW/reference/tui.md) · [日本語](../../ja/reference/tui.md) · [한국어](../../ko/reference/tui.md) · [Español](../../es/reference/tui.md) · [Français](../../fr/reference/tui.md) · [Italiano](../../it/reference/tui.md) · [Português (BR)](../../pt-BR/reference/tui.md) · [Português (PT)](../../pt-PT/reference/tui.md) · [Русский](../../ru/reference/tui.md) · [العربية](../../ar/reference/tui.md) · [हिन्दी](../../hi/reference/tui.md) · [বাংলা](../../bn/reference/tui.md) · [Tiếng Việt](../../vi/reference/tui.md)

Bare `veles` (no subcommand) opens the interactive REPL — an inline
`prompt_toolkit` composer that renders to the terminal's **normal** screen
buffer and never captures the mouse. That means the terminal itself owns
scrollback, text selection, and clipboard copy (⌘C on macOS, Ctrl+Shift+C on
Linux) — there is no app-level copy binding to learn. A quiet status bar
(mode, tokens, cache) sits under the input box; while a turn runs (and for a
moment after) a live HUD reports elapsed time and tool calls, and Ctrl+I /
Ctrl+O expand it into a collapsible inspector showing per-tool status and
duration.

## Keybindings

| Key | Action |
|---|---|
| `Ctrl+D` | Exit |
| `Ctrl+C` | Cancel an open picker/question, or stop the running generation; otherwise clears the input line; press twice within 1.5 s on an empty line to exit |
| `Esc` | Cancel an open picker/question; during generation, stop it and restore the request into the input box for editing |
| `Ctrl+V` | Paste an image from the clipboard — saved under `.veles/tmp/paste/` and inserted as `@<relative-path>` — or paste plain text if the clipboard holds no image |
| `Ctrl+X Ctrl+E` | Open the current draft in `$EDITOR` |
| `Ctrl+I` / `Ctrl+O` | Toggle the inspector: expands the status HUD into tool activity, per-tool status/duration, and mode switches |
| `@` | Open the project file picker (at the start of input or after whitespace); insert the picked path |
| `Shift+Tab` | Cycle the run mode: `auto → planning → writing → goal` |
| `Tab` | Cycle slash-command completions |
| `Ctrl+J` / `Shift+Enter` | Insert a newline (plain `Enter` submits) |
| `Up` / `Down` | Recall input history, or move within a multi-line draft |

`/theme` and `/model` open their own inline filterable pickers (see below) —
neither has a dedicated keybinding.

Run modes are explained in [Run modes](../explanation/modes.md).

## Slash commands

Type `/` in the composer; `Tab` completes. The registered commands are:

| Command | Purpose |
|---|---|
| `/help`, `/h` | List available commands and keybindings |
| `/quit`, `/q`, `/exit` | Exit the REPL (or `Ctrl+D`) |
| `/clear` | Start a fresh session |
| `/session` | Print the current session id |
| `/sessions` | Open a picker of recent sessions and resume one |
| `/resume <id-prefix>` | Resume a session by id prefix |
| `/history [N]` | List recent sessions (default 20) |
| `/save <slug>` | Save the last answer — a wiki page under `wiki/queries/` on layouts with the wiki engine, otherwise a project-memory insight |
| `/wiki add <path\|url>` / `/wiki query <question>` | Wiki ops — only registered when the active layout enables the wiki engine (e.g. the default `llm-wiki` layout) |
| `/model [<id>]` | No id: open the inline filterable model picker. With an id: set it directly |
| `/theme [<name>]` | No name: open the inline filterable theme picker. With a name: set it directly |
| `/mode [<name>]` | Show or set the run mode (`auto`/`planning`/`writing`/`goal`); `Shift+Tab` cycles |
| `/schema [validate\|fix]` | Inspect or fix `AGENTS.md` sections |
| `/self-doc` | Refresh project self-documentation |
| `/tokens` | Token totals (in/out/last-turn) |
| `/context` | Current context size vs. the model's window |
| `/status` | Snapshot: model/mode/session/provider/busy/queue |
| `/insights [category] [N]` | Recent learned insights |
| `/rules [kind] [N]` | Recent behavioral rules |
| `/errors` | Errors seen in this REPL session |
| `/daemon` | Registered as the daemon control panel's entry point; use `veles daemon` directly for the working Textual picker (project → daemons → channels) |

> The daemon picker and project/channel setup wizards are the one part of the
> old Textual UI that's still Textual — everything else in this list runs
> inline, in the normal terminal buffer.

## Themes

Built-in themes: `everforest` (default), `dracula`, `gruvbox`, `tokyo-night`,
`catppuccin`. Pick one with `/theme` in the REPL, or set `[user] tui_theme` in
`~/.veles/config.toml`.

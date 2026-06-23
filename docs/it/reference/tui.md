# Scorciatoie da tastiera e comandi slash della TUI

> 🌐 **Lingue:** [English](../../en/reference/tui.md) · [简体中文](../../zh-CN/reference/tui.md) · [繁體中文](../../zh-TW/reference/tui.md) · [日本語](../../ja/reference/tui.md) · [한국어](../../ko/reference/tui.md) · [Español](../../es/reference/tui.md) · [Français](../../fr/reference/tui.md) · **Italiano** · [Português (BR)](../../pt-BR/reference/tui.md) · [Português (PT)](../../pt-PT/reference/tui.md) · [Русский](../../ru/reference/tui.md) · [العربية](../../ar/reference/tui.md) · [हिन्दी](../../hi/reference/tui.md) · [বাংলা](../../bn/reference/tui.md) · [Tiếng Việt](../../vi/reference/tui.md)

`veles tui` (o `veles` da solo) apre il REPL interattivo. È una chat con scrollback,
un composer multilinea, una barra di stato e un inspector richiudibile.

## Scorciatoie da tastiera

| Tasto | Azione |
|---|---|
| `Ctrl+D` | Esci |
| `Ctrl+C` | Copia l'ultima risposta dell'assistente; premi due volte entro 1,5 s per uscire |
| `Ctrl+V` | Incolla dagli appunti |
| `Ctrl+Shift+C` / `⌘C` | Copia la selezione corrente (OSC52). Su Terminal.app di macOS, la selezione nativa con trascinamento + ⌘C funziona direttamente |
| `Ctrl+I` | Attiva/disattiva l'inspector (ragionamento, attività dei tool, log token/errori) |
| `Ctrl+R` | Apre il selettore di sessione (riprendi una sessione passata) |
| `Ctrl+T` | Apre il selettore di tema |
| `Shift+Tab` | Cicla la modalità di esecuzione: `auto → planning → writing → goal` |
| `Tab` | Cicla i completamenti dei comandi slash |
| `Up` / `Down` | Cronologia (e ripesca i prompt in coda) |

Le modalità di esecuzione sono spiegate in [Modalità di esecuzione](../explanation/modes.md).

## Comandi slash

Digita `/` nel composer; `Tab` completa. I comandi registrati sono:

| Comando | Scopo |
|---|---|
| `/help` | Elenca i comandi disponibili |
| `/quit`, `/q`, `/exit` | Esce dal REPL |
| `/clear` | Pulisce il log della chat |
| `/model` | Apre il selettore di modello |
| `/mode` | Cambia modalità di esecuzione (auto/planning/writing/goal) |
| `/session` | Apre il selettore di sessione (riprendi) |
| `/save` | Salva / dà un nome alla sessione corrente |
| `/history` | Mostra la cronologia della sessione |
| `/tokens` | Utilizzo dei token (in / out / per-turno / per-sessione) |
| `/context` | Dimensione attuale del contesto vs il limite |
| `/status` | Snapshot: modello, provider, modalità, sessione, occupato, coda |
| `/insights` | Mostra gli insight appresi per il progetto |
| `/rules` | Mostra il digest delle regole del progetto |
| `/schema` | Valida / corregge `AGENTS.md` |
| `/wiki` | Operazioni wiki per il layout attivo |
| `/daemon` | Apre il pannello di controllo del daemon (progetto → daemon → canali) |

> Il set di comandi slash è lo stesso sia che tu lanci la TUI direttamente sia che la spinga da
> un'altra schermata. I canali (es. Telegram) espongono un proprio set di comandi separato.

## Temi

Temi integrati: `everforest` (default), `dracula`, `gruvbox`, `tokyo-night`,
`catppuccin`. Sceglone uno con `Ctrl+T`, `veles tui --theme <name>`, o
`[user] tui_theme` in `~/.veles/config.toml`.

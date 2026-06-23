# Come instradare i task verso modelli diversi

> 🌐 **Lingue:** [English](../../en/how-to/per-task-routing.md) · [简体中文](../../zh-CN/how-to/per-task-routing.md) · [繁體中文](../../zh-TW/how-to/per-task-routing.md) · [日本語](../../ja/how-to/per-task-routing.md) · [한국어](../../ko/how-to/per-task-routing.md) · [Español](../../es/how-to/per-task-routing.md) · [Français](../../fr/how-to/per-task-routing.md) · **Italiano** · [Português (BR)](../../pt-BR/how-to/per-task-routing.md) · [Português (PT)](../../pt-PT/how-to/per-task-routing.md) · [Русский](../../ru/how-to/per-task-routing.md) · [العربية](../../ar/how-to/per-task-routing.md) · [हिन्दी](../../hi/how-to/per-task-routing.md) · [বাংলা](../../bn/how-to/per-task-routing.md) · [Tiếng Việt](../../vi/how-to/per-task-routing.md)

Veles non è vincolato a un solo modello. Ogni **task** interno può usare un
`provider:model` diverso — un modello economico per la compressione del contesto,
uno potente per l'agente principale, un modello di visione per le immagini. Questo
è il sistema di *routing d'ensemble*.

## Tipi di task

| Task | Usato per |
|---|---|
| `default` | Il ciclo dell'agente principale |
| `curator` | Consolidamento sessione → wiki |
| `compressor` | Compressione del contesto a finestra scorrevole |
| `insights` | Estrazione degli insight a fine esecuzione |
| `skills` | Esecuzione delle skill |
| `advisor` | L'auto-controllo `advisor_review` |
| `vision` | `image_describe` (quando è collegato un adapter di visione) |
| `embedding` | Similarità di `veles skill dedup` |

## Vedere il routing corrente

```bash
veles route show
```

Questo stampa il `provider:model` risolto per ogni task e un'etichetta `source`
che indica quale livello lo ha deciso.

## Fissare un task a un modello

```bash
veles route set compressor openrouter:anthropic/claude-haiku-4.5
veles route set advisor    openrouter:anthropic/claude-opus-4.8
veles route set vision     openai:gpt-4o
```

Questi scrivono `[routing.tasks]` in `<project>/.veles/config.toml`:

```toml
[routing.tasks]
compressor = "openrouter:anthropic/claude-haiku-4.5"
advisor    = "openrouter:anthropic/claude-opus-4.8"
vision     = "openai:gpt-4o"
```

## Reset

```bash
veles route reset compressor   # one task back to default
veles route reset              # all tasks back to default
```

## Suggerimenti in linguaggio naturale in AGENTS.md

Puoi esprimere il routing in prosa in `AGENTS.md` (es. "usa un modello economico
per la compressione"). Veles li analizza e li traduce in un `routing.nl.toml`
generato automaticamente:

```bash
veles route refresh            # re-parse AGENTS.md hints
veles route refresh --force    # even if AGENTS.md hasn't changed
```

Le voci esplicite di `[routing.tasks]` vincono sempre sui suggerimenti NL.

## Ordine di risoluzione

Per ogni task, vince il primo livello che produce una specifica:

1. `[routing.tasks][task]` del progetto
2. `[routing.tasks].default` del progetto
3. suggerimento NL del progetto (`routing.nl.toml`)
4. base `[provider]` del progetto
5. `[routing.tasks][task]` / `.default` dell'utente
6. `[user] default_provider` + `default_model` dell'utente

Se nessuno di questi risolve, **non esiste un ripiego hardcoded** — il task resta
non impostato e il suo chiamante degrada (salta la funzionalità) o segnala un
errore chiaro, invece di ricorrere silenziosamente a un modello cloud.

(`embedding` salta i catch-all — un modello di chat non è un modello di embedding —
quindi solo un esplicito `[routing.tasks].embedding` lo soddisfa.)

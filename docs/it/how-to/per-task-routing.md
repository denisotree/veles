# Come instradare i task verso modelli diversi

> 🌐 **Lingue:** [English](../../en/how-to/per-task-routing.md) · [Русский](../../ru/how-to/per-task-routing.md) · **Italiano**

Veles non è vincolato a un solo modello. Ogni **task** interno può usare un
`provider:model` diverso — un modello economico per la compressione del contesto,
uno potente per l'agente principale, un modello di vision per le immagini. Questo è
il sistema di *ensemble routing*.

## Tipi di task

| Task | Usato per |
|---|---|
| `default` | Il loop principale dell'agente |
| `curator` | Consolidamento sessione → wiki |
| `compressor` | Compressione del contesto a finestra scorrevole |
| `insights` | Estrazione di insight post-esecuzione |
| `skills` | Esecuzione delle skill |
| `advisor` | L'autocontrollo `advisor_review` |
| `vision` | `image_describe` (quando un adapter di vision è collegato) |
| `embedding` | Similarità di `veles skill dedup` |

## Visualizzare il routing corrente

```bash
veles route show
```

Questo stampa il `provider:model` risolto per ogni task e un'etichetta `source` che
indica quale livello l'ha deciso.

## Vincolare un task a un modello

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

## Ripristino

```bash
veles route reset compressor   # one task back to default
veles route reset              # all tasks back to default
```

## Suggerimenti in linguaggio naturale in AGENTS.md

Puoi esprimere il routing in prosa in `AGENTS.md` (ad es. "usa un modello economico
per la compressione"). Veles li analizza in un `routing.nl.toml` generato
automaticamente:

```bash
veles route refresh            # re-parse AGENTS.md hints
veles route refresh --force    # even if AGENTS.md hasn't changed
```

Le voci esplicite di `[routing.tasks]` prevalgono sempre sui suggerimenti in NL.

## Ordine di risoluzione

Per ogni task vince il primo livello che produce una specifica:

1. `[routing.tasks][task]` del progetto
2. `[routing.tasks].default` del progetto
3. suggerimento NL del progetto (`routing.nl.toml`)
4. base `[provider]` del progetto
5. `[routing.tasks][task]` / `.default` dell'utente
6. `[user] default_provider` + `default_model` dell'utente
7. impostazione predefinita integrata per quel task

(`embedding` salta i fallback generici — un modello di chat non è un modello di embedding.)

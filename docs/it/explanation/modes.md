# Modalità di esecuzione

> 🌐 **Lingue:** [English](../../en/explanation/modes.md) · [简体中文](../../zh-CN/explanation/modes.md) · [繁體中文](../../zh-TW/explanation/modes.md) · [日本語](../../ja/explanation/modes.md) · [한국어](../../ko/explanation/modes.md) · [Español](../../es/explanation/modes.md) · [Français](../../fr/explanation/modes.md) · **Italiano** · [Português (BR)](../../pt-BR/explanation/modes.md) · [Português (PT)](../../pt-PT/explanation/modes.md) · [Русский](../../ru/explanation/modes.md) · [العربية](../../ar/explanation/modes.md) · [हिन्दी](../../hi/explanation/modes.md) · [বাংলা](../../bn/explanation/modes.md) · [Tiếng Việt](../../vi/explanation/modes.md)

Nella TUI, ogni prompt è gestito da una **modalità di esecuzione** — una strategia
che decide quanta autonomia e quali strumenti riceve il turno. Cicla tra le modalità
con `Shift+Tab`; l'ordine è `auto → planning → writing → goal`.

## Le quattro modalità

### `writing` — chat diretta
La modalità diretta: il tuo prompt va all'agente con l'intero set di strumenti
disponibile, e questo risponde. Usala per il lavoro ordinario in cui vuoi che
l'agente agisca.

### `planning` — ricerca in sola lettura + un piano
Le mutazioni sono bloccate (niente `write_file`, niente `run_shell`). L'agente usa
strumenti di lettura/ricerca per raccogliere contesto, poi produce un artefatto di
piano strutturato. Usala per ragionare prima di toccare qualcosa — oppure passa
`--plan` a `veles run` per lo stesso effetto sulla CLI.

### `auto` — instradamento intelligente (default)
Una rapida classificazione decide se il tuo prompt è una richiesta diretta o
richiede pianificazione, poi instrada di conseguenza verso `writing` o `planning`. È
il fallback più intelligente quando non hai espresso un'intenzione, ed è per questo
che è la prima tappa di default del ciclo.

### `goal` — obiettivo a lungo orizzonte
Pilota una macchina a stati finiti per un obiettivo a più passi: ti intervista per
chiarire, conferma un piano, esegue i passi (con controlli dell'advisor) e verifica
la condizione di completamento — il tutto sotto budget espliciti. L'equivalente CLI
è la famiglia di comandi
[`veles goal`](../how-to/long-running-tasks.md#goals--objectives-with-budgets-and-checkpoints).

## Perché esistono le modalità

Richieste diverse vogliono quantità diverse di cautela. Una domanda veloce non
dovrebbe richiedere cerimonie; una modifica rischiosa beneficia prima di un passaggio
di pianificazione in sola lettura; un grande obiettivo ha bisogno di budget e
checkpoint. Le modalità rendono questa scelta esplicita e commutabile per turno,
invece di incorporare un unico comportamento nell'intera sessione.

Quando cambi modalità a metà sessione, all'agente vengono comunicate le nuove regole,
così il suo comportamento cambia immediatamente.

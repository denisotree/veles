# Orchestrazione multi-agente

> 🌐 **Lingue:** [English](../../en/explanation/multi-agent-orchestration.md) · [简体中文](../../zh-CN/explanation/multi-agent-orchestration.md) · [繁體中文](../../zh-TW/explanation/multi-agent-orchestration.md) · [日本語](../../ja/explanation/multi-agent-orchestration.md) · [한국어](../../ko/explanation/multi-agent-orchestration.md) · [Español](../../es/explanation/multi-agent-orchestration.md) · [Français](../../fr/explanation/multi-agent-orchestration.md) · **Italiano** · [Português (BR)](../../pt-BR/explanation/multi-agent-orchestration.md) · [Português (PT)](../../pt-PT/explanation/multi-agent-orchestration.md) · [Русский](../../ru/explanation/multi-agent-orchestration.md) · [العربية](../../ar/explanation/multi-agent-orchestration.md) · [हिन्दी](../../hi/explanation/multi-agent-orchestration.md) · [বাংলা](../../bn/explanation/multi-agent-orchestration.md) · [Tiếng Việt](../../vi/explanation/multi-agent-orchestration.md)

Per il lavoro complesso, Veles può suddividere un compito tra un **manager** e
sub-agenti **worker** specializzati invece di fare tutto in un unico contesto.
Questa pagina spiega il modello; per attivarlo, vedi
[modalità manager](../how-to/long-running-tasks.md#manager-mode--decompose-any-prompt).

## La forma

```
            manager  (scompone il compito, non scrive mai la risposta finale)
           /    |    \
    explorer  writer  advisor   (worker specializzati, eseguiti in parallelo)
```

- Il **manager** pianifica la scomposizione e coordina — ma **non** scrive da sé il
  deliverable finale.
- I **worker** hanno system prompt specifici per ruolo: `explorer` raccoglie,
  `writer` produce la risposta, `advisor` revisiona. L'insieme è estendibile.
- Alla fine, il manager scrive un breve report in memoria.

## Niente gioco del telefono

Una regola chiave: gli artefatti intermedi raggiungono il sintetizzatore
**verbatim**, non come parafrasi del manager. I risultati di un explorer vengono
consegnati direttamente al writer, così il dettaglio non si perde attraverso una
catena di riassunti. È questo che fa sì che la scomposizione aggiunga qualità invece
di diluirla.

## Perché "il manager non scrive mai"

Se il coordinatore scrivesse anche la risposta, sarebbe tentato di scavalcare i
worker e di perdere il beneficio della specializzazione. Tenere la sintesi in un
`writer` dedicato (alimentato da input verbatim) fa rispettare la divisione del
lavoro. Veles rende tutto questo una garanzia a runtime.

## Quando aiuta — e quando no

La scomposizione conviene per compiti ampi o sfaccettati (verifica questo codebase,
ricerca questa domanda da più angolazioni). Per una richiesta veloce a contesto
singolo aggiunge solo overhead — ed è per questo che la modalità manager è
**abilitazione esplicita**, disattivata di default (`veles run --manager` oppure
`VELES_MANAGER_MODE=1`).

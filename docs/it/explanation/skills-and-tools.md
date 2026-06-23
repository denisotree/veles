# Skill e strumenti come capacità che si accumula

> 🌐 **Lingue:** [English](../../en/explanation/skills-and-tools.md) · [简体中文](../../zh-CN/explanation/skills-and-tools.md) · [繁體中文](../../zh-TW/explanation/skills-and-tools.md) · [日本語](../../ja/explanation/skills-and-tools.md) · [한국어](../../ko/explanation/skills-and-tools.md) · [Español](../../es/explanation/skills-and-tools.md) · [Français](../../fr/explanation/skills-and-tools.md) · **Italiano** · [Português (BR)](../../pt-BR/explanation/skills-and-tools.md) · [Português (PT)](../../pt-PT/explanation/skills-and-tools.md) · [Русский](../../ru/explanation/skills-and-tools.md) · [العربية](../../ar/explanation/skills-and-tools.md) · [हिन्दी](../../hi/explanation/skills-and-tools.md) · [বাংলা](../../bn/explanation/skills-and-tools.md) · [Tiếng Việt](../../vi/explanation/skills-and-tools.md)

Veles parte con un insieme minimo di strumenti e skill e lo **fa crescere** mentre
lavora. Questa pagina spiega la differenza tra i due e come si accumulano. Per i
comandi, vedi [gestire skill e strumenti](../how-to/manage-skills-and-tools.md).

## Strumenti vs skill

- Uno **strumento** è una singola azione eseguibile — leggere un file, eseguire un
  comando shell, recuperare un URL, cercare sul web, scrivere una pagina wiki. Gli
  strumenti sono ciò che il modello chiama.
- Una **skill** è un *processo* formalizzato — un `SKILL.md` con un corpo di prompt e
  un elenco di strumenti consentiti che gira come sub-agente focalizzato. Le skill
  compongono gli strumenti in un flusso di lavoro ripetibile (per esempio le skill
  `ingest`/`query`/`lint` della LLM-Wiki).

## Avvio minimale, espansione su richiesta

Veles si avvia con quanto basta per essere utile, più un posto noto da cui
prelevarne di più. Installare extra (una skill, uno strumento, un modulo) chiede
l'approvazione di default; puoi concedere un'autonomia permanente. Questo mantiene
snello un progetto nuovo lasciando crescere la capacità dove serve.

## Come si accumula la capacità

1. **Veles scrive i propri strumenti.** Quando nota un compito ricorrente, può
   redigere uno strumento Python pulito, tipizzato e riutilizzabile in
   `<project>/.veles/tools/` (con un passaggio di code-review dell'advisor). Lo
   strumento entra nel registro con la telemetria.
2. **I processi ricorrenti diventano skill.** Un rilevatore di pattern individua le
   sequenze di strumenti ricorrenti e propone di formalizzarle come skill; le skill
   possono `extends:` un'altra skill per ereditarne il corpo e gli strumenti.
3. **La telemetria guida il ranking.** Ogni strumento/skill porta con sé conteggi di
   uso/successo/errore. Questi alimentano il dedup (`veles skill dedup`) e i
   suggerimenti di promozione.

## Due ambiti, con promozione

Sia gli strumenti che le skill esistono a due livelli:

- **Locale al progetto** (`<project>/.veles/`) — visibile solo qui.
- **Globale dell'utente** (`~/.veles/`) — disponibile in ogni progetto.

Una capacità che si dimostra valida in un progetto può essere **promossa** all'ambito
utente così che tutti i progetti ne beneficino (`veles skill promote`,
`veles tool promote`), oppure **retrocessa**. È così che Veles trasporta tra i
progetti i flussi di lavoro conquistati a fatica.

## Perché un registro, non solo file

Conservare skill/strumenti come semplici file li mantiene ispezionabili e
modificabili; conservare la loro *telemetria* in `memory.db` permette a Veles di
ragionare su quali funzionano davvero. È la combinazione a trasformare "una cartella
di script" in una capacità che si accumula e si auto-cura.

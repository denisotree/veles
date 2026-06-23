# Come fare il backup e condividere un progetto

> 🌐 **Lingue:** [English](../../en/how-to/backup-and-share.md) · [简体中文](../../zh-CN/how-to/backup-and-share.md) · [繁體中文](../../zh-TW/how-to/backup-and-share.md) · [日本語](../../ja/how-to/backup-and-share.md) · [한국어](../../ko/how-to/backup-and-share.md) · [Español](../../es/how-to/backup-and-share.md) · [Français](../../fr/how-to/backup-and-share.md) · **Italiano** · [Português (BR)](../../pt-BR/how-to/backup-and-share.md) · [Português (PT)](../../pt-PT/how-to/backup-and-share.md) · [Русский](../../ru/how-to/backup-and-share.md) · [العربية](../../ar/how-to/backup-and-share.md) · [हिन्दी](../../hi/how-to/backup-and-share.md) · [বাংলা](../../bn/how-to/backup-and-share.md) · [Tiếng Việt](../../vi/how-to/backup-and-share.md)

I progetti Veles sono portabili. Esporta un progetto in un unico bundle `.tar.gz` per
backup o migrazione, oppure un template sanificato da condividere senza divulgare i tuoi dati.

## Backup completo

Impacchetta l'intero progetto (`.veles/` + `AGENTS.md`), esclusi gli elementi effimeri di runtime (lock,
stato del budget):

```bash
veles export full ./my-project-backup.tar.gz
```

Ripristinalo ovunque:

```bash
veles import ./my-project-backup.tar.gz                # into cwd
veles import ./my-project-backup.tar.gz --into ./restored
veles import ./my-project-backup.tar.gz --force        # overwrite an existing .veles/
```

Un bundle completo include il tuo `memory.db` (sessioni, insight), quindi trattalo come
dati privati.

## Template condivisibile

Impacchetta solo l'impalcatura riutilizzabile — schema, skill, moduli e pagine wiki
non legate alle sessioni. **Rimuove** `memory.db`, `sources/`, `sessions/`, le concessioni di trust e
oscura i dati personali (PII) nel testo:

```bash
veles export template ./my-template.tar.gz
```

Passa il template a un collega; lui esegue `veles import` e ottiene la tua struttura
e le tue skill senza la tua cronologia delle conversazioni o le tue fonti grezze.

## Quale usare

| Obiettivo | Comando |
|---|---|
| Backup / spostamento integrale di un progetto | `veles export full` |
| Condividere struttura + skill, non i dati | `veles export template` |

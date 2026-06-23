# Fiducia e sandbox

> 🌐 **Lingue:** [English](../../en/explanation/trust-and-sandbox.md) · [简体中文](../../zh-CN/explanation/trust-and-sandbox.md) · [繁體中文](../../zh-TW/explanation/trust-and-sandbox.md) · [日本語](../../ja/explanation/trust-and-sandbox.md) · [한국어](../../ko/explanation/trust-and-sandbox.md) · [Español](../../es/explanation/trust-and-sandbox.md) · [Français](../../fr/explanation/trust-and-sandbox.md) · **Italiano** · [Português (BR)](../../pt-BR/explanation/trust-and-sandbox.md) · [Português (PT)](../../pt-PT/explanation/trust-and-sandbox.md) · [Русский](../../ru/explanation/trust-and-sandbox.md) · [العربية](../../ar/explanation/trust-and-sandbox.md) · [हिन्दी](../../hi/explanation/trust-and-sandbox.md) · [বাংলা](../../bn/explanation/trust-and-sandbox.md) · [Tiếng Việt](../../vi/explanation/trust-and-sandbox.md)

Veles esegue un agente autonomo sulla tua macchina, quindi vincola ciò che quell'agente
può fare. Due meccanismi lavorano insieme: una **scala di fiducia** per le azioni
sensibili e una **sandbox** per il filesystem. Per i comandi, vedi
[sicurezza e permessi](../how-to/security-and-permissions.md).

## La scala di fiducia

Non tutti gli strumenti sono uguali. Leggere un file è innocuo; eseguire un comando
shell o scrivere su disco no. Gli strumenti sensibili (`run_shell`, `write_file`,
`fetch_url`, …) si fermano e chiedono prima di eseguire, offrendo quattro scelte:

- **Una volta** — consenti questa singola chiamata.
- **Sempre per questo progetto** — persisti una concessione con ambito di progetto.
- **Sempre ovunque** — persisti una concessione con ambito utente.
- **Rifiuta** — negala.

Le concessioni vengono memorizzate così che non ti venga chiesto di nuovo. Questo ti
dà un controllo graduale: fidati di uno strumento una volta, in un progetto o
globalmente — la tua scelta, fatta la prima volta che conta.

### Azioni a conferma sempre richiesta

Alcune operazioni sono abbastanza rischiose da far sì che Veles le confermi **anche
con una concessione**: eliminare file, recuperare URL, installare una nuova
skill/strumento/modulo, collegare un canale e scrivere fuori dal progetto. Sono
rivolte verso l'esterno o difficili da annullare, quindi una concessione permanente
non dovrebbe coprirle silenziosamente.

### Sicurezza non interattiva

In un daemon, un batch o un altro contesto senza TTY non c'è un umano a cui chiedere,
quindi Veles **rifiuta** le azioni sensibili di default — uno stdin vagante non può
intrufolare un'approvazione. Per girare incustodito di proposito, apri una finestra di
[autopilot](../how-to/security-and-permissions.md#autopilot--a-time-boxed-bypass);
ogni azione di autopilot viene registrata per la revisione.

## La sandbox del filesystem

Una guardia dei percorsi delimita dove gli strumenti possono leggere e scrivere:

- **Lettura** — all'interno del progetto attivo (e dei suoi sotto-progetti) più
  `~/.veles/`.
- **Scrittura** — solo le zone scrivibili del layout (per esempio `wiki/`); `.veles/`
  è sempre scrivibile per lo stato macchina.

I symlink che evadono dalla sandbox vengono rifiutati, e la traversata con `..` viene
respinta prima della risoluzione. I recuperi di URL mantengono una deny-list SSRF.
Configurazioni avanzate possono sovrascrivere le radici con `VELES_SANDBOX_ROOTS`, o
rimuovere il blocco delle reti private con `VELES_FETCH_ALLOW_PRIVATE=1` — entrambe ad
attivazione esplicita.

## Perché questo design

L'obiettivo è **autonomia utile senza brutte sorprese**: l'agente può svolgere lavoro
reale senza un prompt a ogni lettura, ma tutto ciò che potrebbe danneggiare la tua
macchina, spendere denaro o lasciare la scatola è regolato — una volta, e poi
ricordato secondo il tuo gusto.

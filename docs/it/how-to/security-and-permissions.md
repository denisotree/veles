# Come gestire la sicurezza: fiducia, autopilot, segreti

> 🌐 **Lingue:** [English](../../en/how-to/security-and-permissions.md) · [Русский](../../ru/how-to/security-and-permissions.md) · **Italiano**

Veles protegge le azioni pericolose dietro una **scala di fiducia**, isola
l'accesso ai file in una sandbox e conserva i segreti nel keychain del sistema
operativo. Per la motivazione, vedi [fiducia e sandbox](../explanation/trust-and-sandbox.md).

## La scala di fiducia

Gli strumenti sensibili (`run_shell`, `write_file`, `fetch_url`, …) chiedono
conferma prima dell'esecuzione. Tu scegli: consentire **una volta**, **sempre per
questo progetto**, **sempre ovunque**, oppure **rifiutare**. Le autorizzazioni
persistono, così non ti viene richiesto di nuovo.

Gestisci le autorizzazioni senza attendere una richiesta:

```bash
veles trust list                          # current grants (user + project)
veles trust set run_shell --scope project # pre-grant for this project
veles trust set write_file --scope user   # pre-grant everywhere
veles trust revoke run_shell              # remove a grant
veles trust clear --scope all             # wipe everything
```

Alcune azioni sono **sempre confermate** anche con un'autorizzazione — eliminare
file, recuperare URL, installare una nuova skill/strumento/modulo, collegare un
canale e scrivere al di fuori del progetto.

## Autopilot — un bypass a tempo limitato

Per un'esecuzione non presidiata (un batch notturno), apri una finestra in cui le
richieste di fiducia vengono auto-consentite:

```bash
veles autopilot enable --until +2h
veles autopilot enable --until 2026-12-31T23:00:00Z
veles autopilot status
veles autopilot disable
```

Ogni azione in autopilot viene registrata per una revisione successiva. I contesti
non interattivi (daemon, batch) rifiutano per impostazione predefinita a meno che
l'autopilot non sia attivo.

## Segreti

Le chiavi API e i token dei bot risiedono nel keychain del sistema operativo, mai
nei file di configurazione:

```bash
veles secret set OPENROUTER_API_KEY       # prompts (or pipe via stdin)
veles secret list                         # which secrets are configured
veles secret get OPENROUTER_API_KEY --reveal
veles secret delete OPENROUTER_API_KEY
```

La ricerca ricade sulla [variabile d'ambiente](../reference/environment-variables.md)
corrispondente a meno che tu non passi `--no-env-fallback`.

## La sandbox

Gli strumenti possono leggere all'interno del progetto attivo e di `~/.veles/`, e
scrivere solo nelle zone scrivibili del layout (`wiki/`, `.veles/` per impostazione
predefinita). Sovrascrivi le radici per configurazioni avanzate con
`VELES_SANDBOX_ROOTS` (separate da `:`). I recuperi di URL mantengono una deny-list
anti-SSRF; `VELES_FETCH_ALLOW_PRIVATE=1` rimuove il blocco della rete privata.

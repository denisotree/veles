# Comment gérer la sécurité : confiance, pilote automatique, secrets

> 🌐 **Langues :** [English](../../en/how-to/security-and-permissions.md) · [简体中文](../../zh-CN/how-to/security-and-permissions.md) · [繁體中文](../../zh-TW/how-to/security-and-permissions.md) · [日本語](../../ja/how-to/security-and-permissions.md) · [한국어](../../ko/how-to/security-and-permissions.md) · [Español](../../es/how-to/security-and-permissions.md) · **Français** · [Italiano](../../it/how-to/security-and-permissions.md) · [Português (BR)](../../pt-BR/how-to/security-and-permissions.md) · [Português (PT)](../../pt-PT/how-to/security-and-permissions.md) · [Русский](../../ru/how-to/security-and-permissions.md) · [العربية](../../ar/how-to/security-and-permissions.md) · [हिन्दी](../../hi/how-to/security-and-permissions.md) · [বাংলা](../../bn/how-to/security-and-permissions.md) · [Tiếng Việt](../../vi/how-to/security-and-permissions.md)

Veles protège les actions dangereuses derrière une **échelle de confiance**, met
l'accès aux fichiers en bac à sable et conserve les secrets dans le trousseau du
système d'exploitation. Pour la justification, voir
[confiance et bac à sable](../explanation/trust-and-sandbox.md).

## L'échelle de confiance

Les outils sensibles (`run_shell`, `write_file`, `fetch_url`, …) demandent une
confirmation avant de s'exécuter. Vous choisissez : autoriser **une fois**,
**toujours pour ce projet**, **toujours partout**, ou **refuser**. Les
autorisations persistent, donc on ne vous redemande pas.

Gérez les autorisations sans attendre une invite :

```bash
veles trust list                          # current grants (user + project)
veles trust set run_shell --scope project # pre-grant for this project
veles trust set write_file --scope user   # pre-grant everywhere
veles trust revoke run_shell              # remove a grant
veles trust clear --scope all             # wipe everything
```

Certaines actions sont **toujours confirmées** même avec une autorisation —
supprimer des fichiers, récupérer des URL, installer une nouvelle
compétence/outil/module, connecter un canal et écrire en dehors du projet.

## Pilote automatique — un contournement limité dans le temps

Pour une exécution sans surveillance (un lot pendant la nuit), ouvrez une fenêtre
où les invites de confiance s'autorisent automatiquement :

```bash
veles autopilot enable --until +2h
veles autopilot enable --until 2026-12-31T23:00:00Z
veles autopilot status
veles autopilot disable
```

Chaque action en pilote automatique est journalisée pour un examen ultérieur. Les
contextes non interactifs (démon, traitement par lots) refusent par défaut, sauf
si le pilote automatique est actif.

## Secrets

Les clés d'API et les jetons de bot vivent dans le trousseau du système
d'exploitation, jamais dans les fichiers de configuration :

```bash
veles secret set OPENROUTER_API_KEY       # prompts (or pipe via stdin)
veles secret list                         # which secrets are configured
veles secret get OPENROUTER_API_KEY --reveal
veles secret delete OPENROUTER_API_KEY
```

La recherche se rabat sur la [variable d'environnement](../reference/environment-variables.md)
correspondante, sauf si vous passez `--no-env-fallback`.

## Le bac à sable

Les outils peuvent lire à l'intérieur du projet actif et de `~/.veles/`, et
écrire uniquement dans les zones inscriptibles du layout (`wiki/`, `.veles/` par
défaut). Remplacez les racines pour les configurations avancées avec
`VELES_SANDBOX_ROOTS` (séparées par `:`). Les récupérations d'URL conservent une
liste de blocage SSRF ; `VELES_FETCH_ALLOW_PRIVATE=1` lève le blocage du réseau
privé.

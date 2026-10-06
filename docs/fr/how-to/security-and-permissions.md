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
contextes non interactifs (daemon, traitement par lots) refusent par défaut, sauf
si le pilote automatique est actif.

## Secrets

Les clés d'API et les jetons de bot vivent dans le trousseau du système
d'exploitation, jamais dans les fichiers de configuration :

```bash
veles secret set OPENROUTER_API_KEY       # prompts (or pipe via stdin)
veles secret list                         # which secrets are configured
veles secret get OPENROUTER_API_KEY --reveal
veles secret delete OPENROUTER_API_KEY
veles secret set OPENROUTER_API_KEY --project myproj   # a key for one project only
```

La recherche se rabat sur la [variable d'environnement](../reference/environment-variables.md)
correspondante, sauf si vous passez `--no-env-fallback`.

## Le bac à sable

Les outils peuvent lire à l'intérieur du projet actif, de `~/.veles/skills/` et de
`~/.veles/locales/`, et écrire uniquement dans le projet — ou uniquement dans les
zones inscriptibles de la mise en page, quand celle-ci en déclare. Remplacez les
racines pour les configurations avancées avec `VELES_SANDBOX_ROOTS` (séparées par
`:`). Les récupérations d'URL conservent une liste de blocage SSRF ;
`VELES_FETCH_ALLOW_PRIVATE=1` lève le blocage du réseau privé.

Dans le `.veles/` du projet, les outils de fichiers de l'agent ne peuvent écrire que
dans `skills/`, `tools/`, `tmp/`, `plans/`, `memory/` et `artifacts/`. Tout le reste —
`trust.json`, `config.toml`, `project.toml`, `modules/`, `wiki.toml`, `memory.db` — ne
change que par les commandes `veles` et les outils propres à Veles. Les outils de
fichiers refusent aussi tout autre répertoire `.veles/` du projet (celui d'un
sous-projet, ou un que l'agent planterait dans `wiki/`), à n'importe quelle
profondeur. Ainsi, via ses outils de fichiers, l'agent ne peut ni s'accorder la
confiance ni ajouter du code que Veles exécuterait (un outil qu'il écrit dans
`.veles/tools/` ne se charge qu'après votre approbation de son fichier). Les autres
graphies du même fichier (casse, `..`, lien symbolique) sont refusées aussi.

Les fichiers qui s'exécutent sans commande explicite ou qui pilotent une CLI d'agent —
tout ce qui se trouve sous `.git/`, `.githooks/`, `.claude/`, `.gemini/`, `.agents/`,
`.codex/`, `.vscode/`, `.devcontainer/`, `.husky/`, ainsi que `.envrc`, `.mcp.json`,
`.pre-commit-config.yaml`, `lefthook.yml`, à n'importe quelle profondeur, plus le
répertoire `core.hooksPath` du dépôt et la cible d'un `.git` qui est un lien
symbolique — les outils de fichiers de l'agent ne les écrivent qu'après votre
confirmation de cette écriture. Les autorisations de confiance et l'autopilot ne la
couvrent pas ; le daemon demande dans le canal, et une exécution par lots sans
personne à qui demander refuse.

Les fournisseurs `claude-cli`, `codex` et `antigravity-cli` s'exécutent comme un modèle avec les
seuls outils de Veles : leurs propres outils shell, d'édition de fichiers et web, les
réglages et hooks `.claude/` du projet, et les autres serveurs MCP ne s'appliquent
pas, et chaque outil Veles qu'ils appellent passe par l'échelle de confiance
ci-dessus (personne ne peut répondre à une invite là-bas, donc tout ce qui n'est pas
déjà accordé est refusé). Leur configuration MCP vit dans
`.veles/tmp/delegate-<pid>/`, une par processus en cours, que les outils de fichiers de
l'agent ne peuvent pas écrire. `agy` s'exécute dans un espace de travail temporaire hors
du projet, sous `~/.veles/tmp/`, si bien que les hooks et serveurs MCP de `.agents/` du
projet ne l'atteignent jamais. Il s'exécute avec `--dangerously-skip-permissions` quand il
dispose des outils de Veles — sinon agy refuse les appels MCP en headless — et un hook de
cet espace de travail refuse tous ses propres outils ; un hook qui échoue refuse aussi.
Les outils de fichiers de Veles ne peuvent pas écrire hors du projet, donc agy ne peut
pas réécrire ce hook via eux. `codex` s'exécute aussi hors du projet, avec votre
configuration codex ignorée, un bac à sable en lecture seule et ses propres outils
désactivés par des indicateurs de fonctionnalité dont Veles vérifie les noms avant chaque
première exécution — un codex qui en a renommé un dont il dépend est refusé, pas exécuté
ouvert. Son serveur MCP passe dans ses arguments (pas de fichier de configuration), seuls
les outils de ce serveur sont approuvés, et l'environnement que reçoit ce serveur est
transmis par nom — jamais `VELES_TRUST_AUTO_ALLOW`.

Limites connues :

- `run_shell` est un shell : une fois que vous l'accordez (ou sous autopilot), il peut
  écrire n'importe lequel des fichiers ci-dessus sans la confirmation par fichier — ainsi
  que les magasins d'approbation dans `~/.veles/`. `veles … approve` exige un terminal ou
  le hash relu (`--sha256`) et refuse une commande lancée par le shell de l'agent, mais
  un shell accordé peut retirer cette marque ou écrire ces fichiers directement.
- Une approbation MCP fige la ligne de commande du serveur, pas les fichiers qu'il
  exécute depuis le projet (un script nommé dans `args`) — relisez-les aussi.
- Avec un fournisseur CLI, les exécutions qui pré-autorisent des outils uniquement
  pour elles-mêmes (tâches d'arrière-plan du daemon, `veles research`) ne le
  transmettent pas à la CLI déléguée : la pré-autorisation vit dans le processus Veles, et
  le serveur MCP que la CLI démarre en est un autre, donc ses outils Veles ont besoin
  d'une autorisation permanente via `veles trust set` ou d'une fenêtre d'autopilot. Le
  mode de planification de l'exécution parente ne leur parvient pas non plus.
- `antigravity-cli` suppose qu'agy respecte le `.agents/hooks.json` de son espace de
  travail ; une version d'agy qui cesserait de lire les hooks de l'espace de travail
  laisserait ses propres outils ouverts sous `--dangerously-skip-permissions`.

Les chemins contenant des caractères de contrôle (séquences d'échappement de
terminal, surcharges bidi) sont refusés, et les confirmations, l'invite de confiance
et l'aperçu du diff affichent ces caractères échappés — un appel d'outil ne peut pas
falsifier le texte que vous approuvez.

Les serveurs MCP d'une configuration ne démarrent qu'après votre approbation — voir
[serveurs MCP externes](external-mcp-servers.md#approuver-inspecter-et-tester).

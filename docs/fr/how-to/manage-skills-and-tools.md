# Comment gérer les compétences, les outils et les modules

> 🌐 **Langues :** [English](../../en/how-to/manage-skills-and-tools.md) · [简体中文](../../zh-CN/how-to/manage-skills-and-tools.md) · [繁體中文](../../zh-TW/how-to/manage-skills-and-tools.md) · [日本語](../../ja/how-to/manage-skills-and-tools.md) · [한국어](../../ko/how-to/manage-skills-and-tools.md) · [Español](../../es/how-to/manage-skills-and-tools.md) · **Français** · [Italiano](../../it/how-to/manage-skills-and-tools.md) · [Português (BR)](../../pt-BR/how-to/manage-skills-and-tools.md) · [Português (PT)](../../pt-PT/how-to/manage-skills-and-tools.md) · [Русский](../../ru/how-to/manage-skills-and-tools.md) · [العربية](../../ar/how-to/manage-skills-and-tools.md) · [हिन्दी](../../hi/how-to/manage-skills-and-tools.md) · [বাংলা](../../bn/how-to/manage-skills-and-tools.md) · [Tiếng Việt](../../vi/how-to/manage-skills-and-tools.md)

Veles accumule des capacités au fil du temps. Les **compétences** (skills) sont des
workflows réutilisables, les **outils** (tools) sont des actions exécutables, les
**modules** sont des greffons optionnels. Chacun existe à deux portées : locale au
projet (`<project>/.veles/`) et globale à l'utilisateur (`~/.veles/`). Pour les
concepts, voir [compétences et outils](../explanation/skills-and-tools.md).

## Compétences

Une compétence est un `SKILL.md` (frontmatter + corps de prompt) que l'agent peut
invoquer comme un outil.

```bash
veles skill list                          # installed skills + telemetry
veles skill show <name>                   # print its SKILL.md
veles skill add https://github.com/org/skill.git
veles skill add ./local-skill --scope user   # install user-global
veles skill remove <name>
```

### Promouvoir / rétrograder entre les portées

Une compétence qui s'avère utile dans un projet peut être déplacée vers la portée
utilisateur pour que tous les projets la voient (ou l'inverse) :

```bash
veles skill promote <name>     # project → ~/.veles/skills/
veles skill demote  <name>     # user → this project
```

### Trouver les doublons et les candidats à la promotion

```bash
veles skill dedup                         # near-duplicate skills (embedding/TF-IDF)
veles skill suggest-promote --save        # skills that meet the auto-promote bar
```

## Outils

Les outils sont catalogués dans le `memory.db` du projet avec une télémétrie
d'utilisation. Veles peut écrire ses propres outils au fil de son travail ; vous
les gérez avec :

```bash
veles tool list                # tools in this project
veles tool show <name>         # manifest + telemetry
veles tool promote <name>      # move to ~/.veles/tools/ (cross-project)
```

Les outils sensibles (`run_shell`, `write_file`, `fetch_url`, …) sont protégés par
l'[échelle de confiance](security-and-permissions.md).

## Modules

Un module est du code Python (`module.toml` + un point d'entrée) qui s'exécute dans
Veles — il ajoute des capacités optionnelles (fournisseurs de mémoire, embeddings,
vision, STT) sans alourdir le cœur. Installer un module nécessite une confirmation par
défaut, et il ne se charge à chaque exécution que tant que ses fichiers correspondent
à ce que vous avez approuvé (voir [garder les installations
fiables](../../en/how-to/extension-registries.md#keep-installs-honest)).

```bash
veles module list                              # les deux périmètres, avec une colonne `scope`
veles module add https://github.com/org/module.git
veles module add ./local-module --user          # installe dans ~/.veles/modules/, pour tous les projets
veles module show <name> [--user]             # manifeste + sha256 des fichiers
veles module remove <name> [--user]
veles module approve <name> [--user]          # saisir `yes` dans un terminal
veles module approve <name> --sha256 <hash>   # sans terminal : le hash relu
```

Les modules vivent à deux portées, comme les compétences et les outils : locaux au
projet (`<project>/.veles/modules/`) et globaux à l'utilisateur (`~/.veles/modules/`,
chargés dans chaque projet). Un module utilisateur passe par la même porte
d'approbation qu'un module de projet, et la porte s'exécute avant la comparaison des
noms. Si un module de projet et un module utilisateur portent le même nom, un module de
projet approuvé se charge et Veles avertit que le module utilisateur est masqué ; un
module de projet non approuvé est ignoré (l'avertissement nomme son répertoire) et le
module utilisateur se charge. Deux modules approuvés de la même portée portant le même
nom — le premier (trié par répertoire) se charge, les autres avertissent et sont
ignorés. `veles module {show,approve,remove}` prennent le nom du manifeste (celui que
montre `list`) et refusent un nom que plus d'un répertoire de la portée déclare, en les
listant ; `veles module add` refuse d'installer un module dont un autre répertoire de
la portée déclare déjà le nom.

### Écrire un module qui ajoute un fournisseur de mémoire

Le point d'entrée `register(api)` d'un module peut appeler
`api.add_memory_provider(name, factory)` pour brancher une source de mémoire externe
sur le rappel. `name` doit correspondre à une section `[memory.external.<name>]` de
`~/.veles/config.toml` ; `factory` reçoit cette section (un `dict`) et doit renvoyer un
objet implémentant le protocole `MemoryProvider` de Veles
(`veles.core.memory.provider`), ou `None` pour ignorer le fournisseur :

```toml
# module.toml
[module]
name = "my-provider"
description = "Recalls memories from my external store."
entrypoint = "my_provider.py:register"
version = "0.1.0"
```

```python
# my_provider.py
from veles.core.memory.provider import RecallHit


class MyProvider:
    name = "my-provider"

    def recall(self, query: str, *, limit: int) -> list[RecallHit]:
        ...  # query the external store, return RecallHit objects


def _build(cfg: dict) -> MyProvider | None:
    api_key = cfg.get("api_key")
    return MyProvider() if api_key else None


def register(api) -> None:
    api.add_memory_provider("my-provider", _build)
```

```toml
# ~/.veles/config.toml
[memory.external.my-provider]
api_key = "..."
```

Un fournisseur qui implémente aussi `ingest(title, body, *, insight_id) -> bool` (le
protocole `IngestingMemoryProvider`) reçoit également les écritures de Veles, pas
seulement les lectures. Si deux modules enregistrent le même nom de fournisseur, le
chargement du second échoue — il est ignoré avec un avertissement, rien n'est
enregistré à moitié. Une section configurée dans `config.toml` dont le module n'est pas
installé affiche un seul avertissement avec la commande d'installation ; le rappel
continue de fonctionner sans lui.

Le registre fournit Honcho, Mem0 et Supermemory comme modules de fournisseur prêts à
l'emploi — installez-les avec `veles registry install --user
{honcho,mem0,supermemory}`, puis lancez la commande `uv tool install veles-ai --with
'<package>'` qu'affiche l'installation (chacun déclare un SDK — `mem0ai>=2.0`,
`honcho-ai>=2.5`, `supermemory>=3.62` — que Veles n'installe jamais pour vous), et
renseignez la section `[memory.external.<name>]` correspondante :

- **mem0** : `api_key`, `user_id`, `agent_id` facultatif (rappelle aussi les souvenirs
  de cet agent) et `host`. La télémétrie du SDK est désactivée par défaut ; chaque
  rappel fait une requête `GET /v1/ping/` supplémentaire.
- **supermemory** : `api_key`, `user_id` facultatif (envoyé comme `container_tag` de la
  recherche) et `base_url`.
- **honcho** : `api_key`, `workspace_id`, `peer_id` facultatif (recherche uniquement
  dans les messages de ce peer) et `base_url`. Chaque rappel fait un get-or-create du
  workspace — il crée `workspace_id` s'il n'existe pas déjà.

## Découvrir davantage

Recherchez dans les registres connectés :

```bash
veles registry search [query] [--kind module|skill|layout|mcp]
```

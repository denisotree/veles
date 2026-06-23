# Connecter des serveurs MCP externes

> 🌐 **Langues :** [English](../../en/how-to/external-mcp-servers.md) · [简体中文](../../zh-CN/how-to/external-mcp-servers.md) · [繁體中文](../../zh-TW/how-to/external-mcp-servers.md) · [日本語](../../ja/how-to/external-mcp-servers.md) · [한국어](../../ko/how-to/external-mcp-servers.md) · [Español](../../es/how-to/external-mcp-servers.md) · **Français** · [Italiano](../../it/how-to/external-mcp-servers.md) · [Português (BR)](../../pt-BR/how-to/external-mcp-servers.md) · [Português (PT)](../../pt-PT/how-to/external-mcp-servers.md) · [Русский](../../ru/how-to/external-mcp-servers.md) · [العربية](../../ar/how-to/external-mcp-servers.md) · [हिन्दी](../../hi/how-to/external-mcp-servers.md) · [বাংলা](../../bn/how-to/external-mcp-servers.md) · [Tiếng Việt](../../vi/how-to/external-mcp-servers.md)

Veles est un **client** [MCP](https://modelcontextprotocol.io/) : il peut se connecter
à des serveurs MCP externes et exposer leurs outils à l'agent comme s'ils étaient
intégrés (GitHub, documentation de bibliothèques, recherche web, vos propres services, …).

## Configurer un serveur

Ajoutez un bloc `[mcp.servers.<name>]` à `<project>/.veles/config.toml` (ou au fichier
global utilisateur `~/.veles/config.toml`). Le `<name>` doit correspondre à
`[A-Za-z0-9][A-Za-z0-9_-]{0,31}` — il devient une partie du nom de chaque outil. Trois
transports sont pris en charge : `stdio` (par défaut), `http`, `sse`.

| Clé | Transport | Par défaut | Rôle |
|---|---|---|---|
| `transport` | — | `"stdio"` | `stdio` \| `http` \| `sse` |
| `command` | stdio (requis) | — | l'exécutable à lancer — **uniquement le programme, pas ses arguments** |
| `args` | stdio | `[]` | liste d'arguments, un token par élément |
| `env` | stdio | `{}` | variables d'environnement supplémentaires pour le sous-processus (fusionnées par-dessus l'environnement hérité) |
| `url` | http/sse (requis) | — | le point d'accès du serveur |
| `timeout_s` | — | `120` | budget pour un seul appel d'outil |
| `connect_timeout_s` | — | `30` | budget pour la connexion initiale |
| `enabled` | — | `true` | mettez `false` pour conserver l'entrée sans s'y connecter |

Les valeurs de chaîne dans `command`, `args`, `env` et `url` interpolent `${VAR}`
depuis l'environnement (une variable non définie devient une chaîne vide accompagnée
d'un avertissement) — gardez les secrets hors du fichier.

> **`command` vs `args`.** Veles exécute le programme directement (sans shell) :
> l'exécutable et ses arguments sont donc des champs **distincts**. Écrivez
> `command = "npx"`, `args = ["-y", "pkg"]` — et **non** `command = "npx -y pkg"`.

### stdio (sous-processus local)

```toml
[mcp.servers.github]
transport = "stdio"
command = "npx"
args = ["-y", "@modelcontextprotocol/server-github"]
env = { GITHUB_TOKEN = "${GITHUB_TOKEN}" }
```

Un serveur que vous exécutez vous-même fonctionne de la même façon — pointez
`command`/`args` vers lui :

```toml
[mcp.servers.mytools]
transport = "stdio"
command = "python"
args = ["-m", "my_mcp_server"]
```

### Un serveur nécessitant une clé d'API (context7)

[Context7](https://context7.com) fournit une documentation de bibliothèques à jour.
Passez la clé en argument afin que `${VAR}` la garde hors du fichier :

```toml
[mcp.servers.context7]
transport = "stdio"
command = "npx"
args = ["-y", "@upstash/context7-mcp", "--api-key", "${CONTEXT7_API_KEY}"]
```

```bash
export CONTEXT7_API_KEY=...   # puis démarrez veles
```

### http / sse (distant)

```toml
[mcp.servers.search]
transport = "http"            # HTTP en flux ; utilisez "sse" pour un point d'accès SSE
url = "https://mcp.example.com/mcp"
```

> **Pas d'en-têtes personnalisés (pour l'instant).** Les transports `http`/`sse`
> n'envoient que l'`url` — Veles ne peut pas attacher d'en-tête `Authorization`. Pour
> un serveur distant nécessitant une clé, préférez sa variante `stdio` (p. ex. `npx`)
> avec la clé dans `args`/`env`, ou un point d'accès qui accepte la clé dans l'URL.

## Masquer certains outils

Définissez `[mcp] disabled_tools` — une table associant chaque serveur aux noms des
outils à ignorer :

```toml
[mcp]
disabled_tools = { github = ["delete_repository"], search = ["raw_query"] }
```

## Inspecter et tester

```bash
veles mcp list              # chaque serveur configuré : transport, statut, nombre d'outils
veles mcp test github       # se connecte à un serveur et liste ses outils
```

`veles mcp list` se termine toujours avec le code 0 — c'est un inspecteur, pas un
contrôle de santé. `veles mcp test` se termine avec le code 1 quand la connexion échoue
et 2 pour un nom de serveur inconnu.

## Comment les outils apparaissent

Une fois configurés, les serveurs sont montés **automatiquement** au prochain
`veles run` / démarrage du TUI / du daemon — il n'y a pas d'indicateur « activer MCP »
distinct, la présence de la configuration fait office d'interrupteur. Chaque outil
entre dans le registre normal sous la forme `mcp_<server>_<tool>` et est appelable par
l'agent comme n'importe quel outil intégré. Les schémas sont assainis (limites de
nom/longueur, suppression des caractères de contrôle) afin qu'un serveur non fiable ne
puisse pas s'injecter dans le prompt. Les indices d'outils sont mappés sur l'échelle de
confiance : les outils destructeurs demandent toujours confirmation, les outils en
lecture seule ne sont pas soumis à invite, et tout le reste suit le flux de
[confiance](security-and-permissions.md) habituel — accordez une approbation permanente
avec `veles trust set` si vous ne voulez pas être sollicité à chaque fois.

## Gestion des échecs

Un serveur qui échoue à se connecter — `command` manquant, `url` incorrect ou toute
entrée invalide — est consigné comme avertissement et ignoré. Il ne bloque jamais le
démarrage ni l'agent. Relancez `veles mcp list` pour voir le statut et l'erreur.

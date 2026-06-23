# Comment exécuter Veles en démon

> 🌐 **Langues :** [English](../../en/how-to/run-as-daemon.md) · [Русский](../../ru/how-to/run-as-daemon.md)

Le démon est un serveur HTTP+WS optionnel et persistant qui expose l'agent sous
forme d'API — c'est la fondation des [canaux](connect-telegram.md) (Telegram, …),
des [tâches](long-running-tasks.md) planifiées et de l'usage distant/sans interface.

## Démarrer et arrêter

```bash
veles daemon start              # detaches by default; binds 127.0.0.1:8765
veles daemon status             # is it running?
veles daemon stop               # SIGTERM via the pid file
```

`start` se détache et vous rend la main sur le shell. Pour un processus au
premier plan (systemd `Type=simple`, Docker, débogage), passez `--foreground`.
Remplacez l'adresse d'écoute :

```bash
veles daemon start --host 0.0.0.0 --port 9000
```

Le modèle et le fournisseur du démon proviennent de la configuration du projet et
sont **fixés pour toute sa durée de vie** — définissez-les avant de démarrer :

```toml
# <project>/.veles/config.toml
[provider]
default = "ollama:qwen3:4b-instruct"
```

## Jetons d'authentification

Les clients de l'API s'authentifient avec un jeton bearer :

```bash
veles daemon token add tui-client     # mint a token
veles daemon token list               # list (masked)
veles daemon token remove tui-client
```

## Le sélecteur de démons (TUI)

Lancez `veles daemon` sans sous-commande pour ouvrir le panneau de contrôle — un
arbre des démons de votre projet et des canaux de chaque démon :

```
Project: my-project
  default   running  pid=…  up 1.2h  qwen3:4b-instruct
    chan: telegram
  api       stopped
Other projects
  other-proj  running
```

Touches : `Enter` ouvre le journal d'un démon ; `s`/`t`/`r` démarrer/arrêter/
redémarrer ; `d` supprimer ; `c`/`x` ajouter/retirer un canal ; `q` quitter.

## Plusieurs démons par projet (sessions nommées)

Un projet peut faire tourner plusieurs démons avec des modèles/ports différents
en même temps. Déclarez une session nommée, puis démarrez-la :

```bash
veles daemon session create api --port 8801 --provider anthropic --model claude-opus-4.8
veles daemon start --name api
veles daemon session list
```

Chaque session nommée a son propre bloc de configuration `[daemon.<name>]` et ses
propres canaux (`[daemon.<name>.channels.*]`).

## Lister les démons à travers les projets

```bash
veles daemon list
veles daemon restart <project-or-slug>
veles daemon delete  <project-or-slug>
```

## Et ensuite

- [Connecter un canal Telegram](connect-telegram.md)
- [Planifier des tâches](long-running-tasks.md)

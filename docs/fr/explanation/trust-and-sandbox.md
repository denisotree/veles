# Confiance et bac à sable

> 🌐 **Langues :** [English](../../en/explanation/trust-and-sandbox.md) · [简体中文](../../zh-CN/explanation/trust-and-sandbox.md) · [繁體中文](../../zh-TW/explanation/trust-and-sandbox.md) · [日本語](../../ja/explanation/trust-and-sandbox.md) · [한국어](../../ko/explanation/trust-and-sandbox.md) · [Español](../../es/explanation/trust-and-sandbox.md) · **Français** · [Italiano](../../it/explanation/trust-and-sandbox.md) · [Português (BR)](../../pt-BR/explanation/trust-and-sandbox.md) · [Português (PT)](../../pt-PT/explanation/trust-and-sandbox.md) · [Русский](../../ru/explanation/trust-and-sandbox.md) · [العربية](../../ar/explanation/trust-and-sandbox.md) · [हिन्दी](../../hi/explanation/trust-and-sandbox.md) · [বাংলা](../../bn/explanation/trust-and-sandbox.md) · [Tiếng Việt](../../vi/explanation/trust-and-sandbox.md)

Veles exécute un agent autonome sur votre machine ; il contraint donc ce que cet agent peut
faire. Deux mécanismes œuvrent de concert : une **échelle de confiance** pour les actions
sensibles et un **bac à sable** pour le système de fichiers. Pour les commandes, voir
[sécurité et permissions](../how-to/security-and-permissions.md).

## L'échelle de confiance

Tous les outils ne se valent pas. Lire un fichier est inoffensif ; lancer une commande shell
ou écrire sur le disque ne l'est pas. Les outils sensibles (`run_shell`, `write_file`,
`fetch_url`, …) s'arrêtent et demandent avant de s'exécuter, en proposant quatre choix :

- **Une fois** — autoriser cet appel unique.
- **Toujours pour ce projet** — persister une autorisation à portée projet.
- **Toujours partout** — persister une autorisation à portée utilisateur.
- **Refuser** — la rejeter.

Les autorisations sont conservées afin qu'on ne vous redemande plus. Cela vous donne un
contrôle gradué : faire confiance à un outil une fois, dans un projet, ou globalement — à
votre choix, fait la première fois que cela compte.

### Actions toujours confirmées

Certaines opérations sont assez risquées pour que Veles les confirme **même avec une
autorisation** : supprimer des fichiers, récupérer des URL, installer une nouvelle
compétence/outil/module, connecter un canal et écrire en dehors du projet. Ce sont des
actions tournées vers l'extérieur ou difficiles à annuler, donc une autorisation permanente
ne devrait pas les couvrir silencieusement.

### Sécurité non interactive

Dans un daemon, un traitement par lot ou tout autre contexte sans TTY, il n'y a pas d'humain à
interroger, donc Veles **refuse** les actions sensibles par défaut — une entrée stdin
parasite ne peut pas glisser une approbation en douce. Pour fonctionner sans surveillance de manière
délibérée, ouvrez une fenêtre d'[autopilote](../how-to/security-and-permissions.md#autopilot--a-time-boxed-bypass) ;
chaque action de l'autopilote est journalisée pour revue.

## Le bac à sable du système de fichiers

Un garde-chemins borne où les outils peuvent lire et écrire :

- **Lecture** — à l'intérieur du projet actif (et de ses sous-projets) plus `~/.veles/`.
- **Écriture** — uniquement les zones inscriptibles de la mise en page (par ex. `wiki/`) ;
  `.veles/` est toujours inscriptible pour l'état machine.

Les liens symboliques qui s'échappent du bac à sable sont rejetés, et la traversée par `..`
est refusée avant résolution. Les récupérations d'URL maintiennent une liste de blocage SSRF.
Les configurations avancées peuvent surcharger les racines avec `VELES_SANDBOX_ROOTS`, ou
lever le blocage du réseau privé avec `VELES_FETCH_ALLOW_PRIVATE=1` — les deux en opt-in.

## Pourquoi cette conception

Le but est une **autonomie utile sans mauvaises surprises** : l'agent peut accomplir un vrai
travail sans une invite à chaque lecture, mais tout ce qui pourrait endommager votre machine,
dépenser de l'argent ou sortir de son périmètre est verrouillé — une fois, puis mémorisé selon vos
préférences.

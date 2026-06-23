# Connecter un canal Telegram

> 🌐 **Langues :** [English](../../en/how-to/connect-telegram.md) · [简体中文](../../zh-CN/how-to/connect-telegram.md) · [繁體中文](../../zh-TW/how-to/connect-telegram.md) · [日本語](../../ja/how-to/connect-telegram.md) · [한국어](../../ko/how-to/connect-telegram.md) · [Español](../../es/how-to/connect-telegram.md) · **Français** · [Italiano](../../it/how-to/connect-telegram.md) · [Português (BR)](../../pt-BR/how-to/connect-telegram.md) · [Português (PT)](../../pt-PT/how-to/connect-telegram.md) · [Русский](../../ru/how-to/connect-telegram.md) · [العربية](../../ar/how-to/connect-telegram.md) · [हिन्दी](../../hi/how-to/connect-telegram.md) · [বাংলা](../../bn/how-to/connect-telegram.md) · [Tiếng Việt](../../vi/how-to/connect-telegram.md)

Discutez avec un projet Veles depuis Telegram. Un canal est une passerelle qui
transmet les messages à un [daemon](run-as-daemon.md) et renvoie les réponses en flux
continu. Chaque conversation dispose de sa propre session.

## Prérequis

- Un daemon en cours d'exécution (voir [exécuter en tant que daemon](run-as-daemon.md)).
- Un token de bot Telegram fourni par [@BotFather](https://t.me/BotFather).

## Option A — attacher via l'assistant (recommandé)

Depuis le projet, lancez l'assistant de canal ; il écrit la configuration et stocke le
token dans le trousseau du système d'exploitation :

```bash
veles channel add --channel telegram
```

Ou attachez-vous à une session de daemon nommée précise :

```bash
veles channel add --channel telegram --session api
```

Vous pouvez également le faire depuis le [TUI de sélection de daemon](run-as-daemon.md#the-daemon-picker-tui) :
appuyez sur `c` sur un daemon et suivez les invites.

Cela produit un bloc de configuration :

```toml
[channels.telegram]            # ou [daemon.api.channels.telegram]
enabled = true
whitelist = ["@alice", "123456789"]
```

La **whitelist** restreint les personnes auxquelles le bot répond (`@username`
Telegram ou identifiant utilisateur numérique). Laissez-la vide pour répondre à tout le
monde — déconseillé, car chaque message consomme des tokens du modèle.

Redémarrez le daemon pour appliquer :

```bash
veles daemon restart
```

## Option B — exécuter une passerelle autonome

Si vous préférez un processus séparé (au lieu du canal intégré au daemon), lancez :

```bash
export TELEGRAM_BOT_TOKEN=123456:ABC...
veles channel run --channel telegram \
  --daemon-url http://127.0.0.1:8765 \
  --daemon-token "$(veles daemon token add tg)"
```

## Gérer les sessions de conversation

```bash
veles channel list                       # plateformes enregistrées + nombre de sessions
veles channel list-sessions              # correspondances chat_id → session_id
veles channel reset-session <chat_id>    # le prochain message de cette conversation repart de zéro
veles channel remove telegram            # supprime la liaison du canal
```

## Limitation multimodale

L'envoi d'une **photo ou d'un message vocal** renvoie actuellement un avis « non
configuré ». Veles définit les protocoles `VisionAdapter` / d'adaptateur STT ainsi
qu'un registre (`modules/vision.py`, `modules/stt.py`), mais **aucun adaptateur
concret n'est livré et aucun n'est enregistré au démarrage du daemon** : les images et
l'audio ne sont donc pas encore analysés. La conversation texte fonctionne pleinement.
Voir la [référence des fournisseurs](../reference/providers.md#multimodal-status-vision--speech-to-text).

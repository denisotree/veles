# Telegram チャネルを接続する方法

> 🌐 **言語:** **English** · [Русский](../../ru/how-to/connect-telegram.md)

Telegram から Veles プロジェクトと対話します。チャネルとは、メッセージを
[デーモン](run-as-daemon.md) に転送し、返信をストリーミングで返すゲートウェイです。各チャットは
それぞれ独自の会話セッションを持ちます。

## 前提条件

- 稼働中のデーモン（[デーモンとして実行する](run-as-daemon.md) を参照）。
- [@BotFather](https://t.me/BotFather) から取得した Telegram ボットトークン。

## 選択肢 A — ウィザードで接続する（推奨）

プロジェクトからチャネルウィザードを実行します。設定が書き込まれ、トークンは
OS のキーチェーンに保存されます:

```bash
veles channel add --channel telegram
```

または、特定の名前付きデーモンセッションに接続します:

```bash
veles channel add --channel telegram --session api
```

これは [デーモンピッカー TUI](run-as-daemon.md#the-daemon-picker-tui) からも実行できます:
デーモンの上で `c` を押し、プロンプトに従ってください。

これにより次の設定ブロックが生成されます:

```toml
[channels.telegram]            # or [daemon.api.channels.telegram]
enabled = true
whitelist = ["@alice", "123456789"]
```

**whitelist** はボットが応答する相手を制限します（Telegram の `@username` または数値の
ユーザー ID）。空のままにすると全員に応答します — メッセージごとにモデルのトークンを
消費するため、推奨されません。

適用するにはデーモンを再起動します:

```bash
veles daemon restart
```

## 選択肢 B — スタンドアロンのゲートウェイを実行する

（デーモン内蔵チャネルではなく）別プロセスを使いたい場合は、次を実行します:

```bash
export TELEGRAM_BOT_TOKEN=123456:ABC...
veles channel run --channel telegram \
  --daemon-url http://127.0.0.1:8765 \
  --daemon-token "$(veles daemon token add tg)"
```

## チャットセッションを管理する

```bash
veles channel list                       # 登録済みプラットフォーム + セッション数
veles channel list-sessions              # chat_id → session_id のマッピング
veles channel reset-session <chat_id>    # そのチャットからの次のメッセージは新規セッションで開始
veles channel remove telegram            # チャネルのバインディングを解除
```

## マルチモーダルの制限

**写真や音声メッセージ** を送信すると、現時点では「未設定（not configured）」の通知が返されます。
Veles は `VisionAdapter` / STT アダプターのプロトコルとレジストリ
（`modules/vision.py`、`modules/stt.py`）を定義していますが、**具体的なアダプターは同梱されておらず、
デーモン起動時に登録されるものもありません**。そのため画像や音声はまだ解析されません。テキストの
チャットは完全に機能します。[プロバイダーリファレンス](../reference/providers.md#multimodal-status-vision--speech-to-text) を参照してください。

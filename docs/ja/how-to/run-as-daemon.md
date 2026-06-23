# Veles をデーモンとして実行する方法

> 🌐 **Languages:** **English** · [Русский](../../ru/how-to/run-as-daemon.md)

デーモンは、エージェントを API として公開するオプションの常駐型 HTTP+WS サーバーです。[チャンネル](connect-telegram.md)（Telegram など）、スケジュールされた[ジョブ](long-running-tasks.md)、リモート/ヘッドレス利用の基盤となります。

## 起動と停止

```bash
veles daemon start              # detaches by default; binds 127.0.0.1:8765
veles daemon status             # is it running?
veles daemon stop               # SIGTERM via the pid file
```

`start` はデタッチしてシェルを返します。フォアグラウンドプロセスとして動かしたい場合（systemd の `Type=simple`、Docker、デバッグなど）は `--foreground` を渡します。バインド先を上書きするには次のようにします:

```bash
veles daemon start --host 0.0.0.0 --port 9000
```

デーモンのモデルとプロバイダーはプロジェクト設定から取得され、**そのライフタイムの間は固定**されます。起動前に設定してください:

```toml
# <project>/.veles/config.toml
[provider]
default = "ollama"            # provider name
model = "qwen3:4b-instruct"   # model id
```

## 認証トークン

API クライアントはベアラートークンで認証します:

```bash
veles daemon token add tui-client     # mint a token
veles daemon token list               # list (masked)
veles daemon token remove tui-client
```

## デーモンピッカー（TUI）

サブコマンドなしで `veles daemon` を実行すると、コントロールパネルが開きます。プロジェクトのデーモンと各デーモンのチャンネルからなるツリーです:

```
Project: my-project
  default   running  pid=…  up 1.2h  qwen3:4b-instruct
    chan: telegram
  api       stopped
Other projects
  other-proj  running
```

キー操作: `Enter` でデーモンのログを開く、`s`/`t`/`r` で起動/停止/再起動、`d` で削除、`c`/`x` でチャンネルの追加/削除、`q` で終了。

## プロジェクトごとに複数のデーモン（名前付きセッション）

1 つのプロジェクトで、異なるモデル/ポートを持つ複数のデーモンを同時に実行できます。名前付きセッションを宣言してから起動します:

```bash
veles daemon session create api --port 8801 --provider anthropic --model claude-opus-4.8
veles daemon start --name api
veles daemon session list
```

各名前付きセッションは独自の `[daemon.<name>]` 設定ブロックと、独自のチャンネル（`[daemon.<name>.channels.*]`）を持ちます。

## プロジェクトをまたいでデーモンを一覧する

```bash
veles daemon list
veles daemon restart <project-or-slug>
veles daemon delete  <project-or-slug>
```

## 次に

- [Telegram チャンネルを接続する](connect-telegram.md)
- [ジョブをスケジュールする](long-running-tasks.md)

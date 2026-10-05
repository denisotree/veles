# プロバイダー

> 🌐 **言語:** [English](../../en/reference/providers.md) · [简体中文](../../zh-CN/reference/providers.md) · [繁體中文](../../zh-TW/reference/providers.md) · **日本語** · [한국어](../../ko/reference/providers.md) · [Español](../../es/reference/providers.md) · [Français](../../fr/reference/providers.md) · [Italiano](../../it/reference/providers.md) · [Português (BR)](../../pt-BR/reference/providers.md) · [Português (PT)](../../pt-PT/reference/providers.md) · [Русский](../../ru/reference/providers.md) · [العربية](../../ar/reference/providers.md) · [हिन्दी](../../hi/reference/providers.md) · [বাংলা](../../bn/reference/providers.md) · [Tiếng Việt](../../vi/reference/providers.md)

Veles はプロバイダー非依存です。任意のエージェントコマンドに `--provider <id>` を渡すか、設定でデフォルトを指定します。モデル ID は各プロバイダー独自の命名を使用します。

## プロバイダーカタログ

Veles が知っているプロバイダーはすべて、3 つのソースから構築された 1 つのカタログのエントリーです。

1. **ビルトイン** — 下の表。Veles に同梱されています。
2. **自分のもの** — `~/.veles/providers.toml`: エントリーを追加すると、ホスト型の OpenAI 互換 API や自分で動かすサーバーを使えます（[独自のプロバイダーを追加する](../how-to/configure-providers.md#独自のプロバイダーを追加する)を参照）。ビルトインと同じ id のエントリーは、そのプロバイダーの設定（たとえば `base_url`）を上書きします。
3. **モジュール** — レジストリのモジュールが提供するプロバイダー（`antigravity-cli`）。`[engine] provider`、ルート、または `--provider` で指定すると、宣言済みのチャンネルと同じように、次回の実行時に接続済みのレジストリからインストールされます。

`--provider`、`veles models`、セットアップウィザード、ルーティング、`veles doctor` はすべてこのカタログを読むため、どのソースのプロバイダーもビルトインと同じ場所で使えます。未知の id は、存在するものを列挙した 1 行のエラーになります。`veles doctor` は `~/.veles/providers.toml` と、ルートが指定するすべてのプロバイダーも検査します。

| プロバイダー | 種別 | API キー | 備考 |
|---|---|---|---|
| `openrouter` | クラウドゲートウェイ | `OPENROUTER_API_KEY` | **デフォルト。** 数百のモデルを中継。モデル ID は `anthropic/claude-sonnet-4.6` のような形式 |
| `anthropic` | クラウド直接 | `ANTHROPIC_API_KEY` | Claude Messages API、プロンプトキャッシング |
| `openai` | クラウド直接 | `OPENAI_API_KEY` | GPT chat completions |
| `gemini` | クラウド直接 | `GEMINI_API_KEY` / `GOOGLE_API_KEY` | Google Gemini |
| `claude-cli` | CLI 委譲 | —（CLI セッション） | ローカルの `claude` CLI に JSON ストリームモードで委譲 |
| `ollama` | ローカル | なし | `OLLAMA_BASE_URL`（デフォルト `http://localhost:11434/v1`） |
| `llamacpp` | ローカル | なし | `LLAMACPP_BASE_URL`（デフォルト `http://localhost:8080/v1`） |
| `openai-compat` | ローカル/カスタム | 任意の `OPENAI_COMPAT_API_KEY` | `OPENAI_COMPAT_BASE_URL`（必須、デフォルトなし） |

`gemini-cli` は 1.2.6 で削除されました — Google は個人アカウント向けに Gemini CLI を提供しなくなったためです。API キーを使う `gemini`、または `antigravity-cli` モジュールを使ってください。

デフォルトのプロバイダー: `openrouter`。**ハードコードされたデフォルトモデルはありません** — セットアップウィザード、`[engine] model`、または `--model` で指定してください（指定しないとエージェントは「no model configured」と報告します）。タスクごとのルートは、`[routing.tasks]` で上書きしない限り `[engine]` をベースとして継承します。[タスク別ルーティング](../how-to/per-task-routing.md)を参照してください。

## ローカルプロバイダー

`ollama`、`llamacpp`、`openai-compat` は API キーを必要としません。インストール済みモデルは `veles models <provider>` で一覧表示できます（ローカルプロバイダーでは常にライブ取得）。

**ツール呼び出しは検出されます**。バックエンドが通知する内容に基づきます。ollama はモデルごとの機能を報告し、llama.cpp サーバーはチャットテンプレートの機能を報告します。`VELES_LOCAL_TOOLS=1` でツール呼び出しを強制的に有効に、`=0` で無効にします。未設定なら検出に任せます。

```bash
veles run --provider ollama --model qwen3:4b-instruct "..."
```

エンドポイントは `*_BASE_URL` 環境変数で上書きします（[環境変数](environment-variables.md)を参照）。

## CLI 委譲（`claude-cli`、`antigravity-cli`）

Claude または Google のサブスクリプションを持っている場合、Veles はその CLI をヘッドレスで実行し、コーディネーターとして振る舞うことができます。別途 API キーは不要です。`claude-cli` はビルトインです。`antigravity-cli`（`agy` CLI）はレジストリのモジュールで、指定すると自動的にインストールされます。

委譲先はモデルにすぎません。Veles のツールは MCP ブリッジ経由で届き、すべての呼び出しが Veles のトラストラダーを通ります。ブリッジの設定は実行中プロセスのディレクトリ `.veles/tmp/delegate-<pid>/` にあり、プロセスの終了時に削除されます。`agy` はプロジェクトではなく、そこにある作業用の一時ワークスペースで実行され、自身のシェルとファイルツールを拒否するゲートの内側に置かれます。

## マルチモーダルの状況（ビジョン / 音声認識）

Veles は `VisionAdapter` と STT アダプターのプロトコル（`modules/vision.py`、`modules/stt.py`）、およびプロセスグローバルなレジストリを定義していますが、**具体的なアダプターは同梱されておらず、デーモン起動時に登録されるものもありません**。そのため、チャンネルに送られた写真や音声メッセージは現状、分析される代わりに「未設定（not configured）」という通知を返します。`vision` ルーティングタスクは、アダプターが配線されたときのために存在します。[Telegram を接続する](../how-to/connect-telegram.md#multimodal-limitation)を参照してください。

## モデルの選択

```bash
veles models openrouter            # cached 24h
veles models openrouter --refresh  # bypass cache
veles models ollama                # always live
```

ジョブごとに異なるモデルを使う場合（圧縮には安価なもの、計画には強力なもの）、[タスク別ルーティング](../how-to/per-task-routing.md)を参照してください。

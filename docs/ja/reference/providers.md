# プロバイダー

> 🌐 **言語:** [English](../../en/reference/providers.md) · [简体中文](../../zh-CN/reference/providers.md) · [繁體中文](../../zh-TW/reference/providers.md) · **日本語** · [한국어](../../ko/reference/providers.md) · [Español](../../es/reference/providers.md) · [Français](../../fr/reference/providers.md) · [Italiano](../../it/reference/providers.md) · [Português (BR)](../../pt-BR/reference/providers.md) · [Português (PT)](../../pt-PT/reference/providers.md) · [Русский](../../ru/reference/providers.md) · [العربية](../../ar/reference/providers.md) · [हिन्दी](../../hi/reference/providers.md) · [বাংলা](../../bn/reference/providers.md) · [Tiếng Việt](../../vi/reference/providers.md)

Veles はプロバイダー非依存です。任意のエージェントコマンドに `--provider <name>` を渡すか、設定でデフォルトを指定します。モデル ID は各プロバイダー独自の命名を使用します。

| プロバイダー | 種別 | API キー | 備考 |
|---|---|---|---|
| `openrouter` | クラウドゲートウェイ | `OPENROUTER_API_KEY` | **デフォルト。** 数百のモデルを中継。モデル ID は `anthropic/claude-sonnet-4.6` のような形式 |
| `anthropic` | クラウド直接 | `ANTHROPIC_API_KEY` | Claude Messages API、プロンプトキャッシング |
| `openai` | クラウド直接 | `OPENAI_API_KEY` | GPT chat completions |
| `gemini` | クラウド直接 | `GEMINI_API_KEY` / `GOOGLE_API_KEY` | Google Gemini |
| `claude-cli` | サブプロセス | —（CLI セッション） | ローカルの `claude` CLI に JSON ストリームモードで委譲 |
| `gemini-cli` | サブプロセス | —（CLI セッション） | ローカルの `gemini` CLI に委譲 |
| `ollama` | ローカル | なし | `OLLAMA_BASE_URL`（デフォルト `http://localhost:11434/v1`） |
| `llamacpp` | ローカル | なし | `LLAMACPP_BASE_URL`（デフォルト `http://localhost:8080/v1`） |
| `openai-compat` | ローカル/カスタム | なし | `OPENAI_COMPAT_BASE_URL`（必須、デフォルトなし） |

デフォルトのプロバイダー: `openrouter`。**ハードコードされたデフォルトモデルはありません** — セットアップウィザード、`[provider] model`、または `--model` で指定してください（指定しないとエージェントは「no model configured」と報告します）。タスクごとのルートは、`[routing.tasks]` で上書きしない限り `[provider]` をベースとして継承します。[タスク別ルーティング](../how-to/per-task-routing.md)を参照してください。

## ローカルプロバイダー

`ollama`、`llamacpp`、`openai-compat` は API キーを必要としません。インストール済みモデルは `veles models <provider>` で一覧表示できます（ローカルプロバイダーでは常にライブ取得）。

ローカルプロバイダーでは**ツール呼び出しはデフォルトで無効**です。多くのローカルモデルは不正なツール呼び出しを生成するためです。ツール対応のモデルを選んだら有効にしてください:

```bash
export VELES_LOCAL_TOOLS=1
veles run --provider ollama --model qwen3:4b-instruct "..."
```

エンドポイントは `*_BASE_URL` 環境変数で上書きします（[環境変数](environment-variables.md)を参照）。

## CLI 委譲（`claude-cli`、`gemini-cli`）

Claude または Gemini の CLI サブスクリプションを持っている場合、Veles はそのバイナリを JSON ストリーミングモードで実行し、コーディネーターとして振る舞うことができます。別途 API キーを用意せずにループをローカルファーストに保てます。Veles のツールがサブプロセスに到達するのは、MCP ブリッジが設定されている場合のみです。

## マルチモーダルの状況（ビジョン / 音声認識）

Veles は `VisionAdapter` と STT アダプターのプロトコル（`modules/vision.py`、`modules/stt.py`）、およびプロセスグローバルなレジストリを定義していますが、**具体的なアダプターは同梱されておらず、デーモン起動時に登録されるものもありません**。そのため、チャンネルに送られた写真や音声メッセージは現状、分析される代わりに「未設定（not configured）」という通知を返します。`vision` ルーティングタスクは、アダプターが配線されたときのために存在します。[Telegram を接続する](../how-to/connect-telegram.md#multimodal-limitation)を参照してください。

## モデルの選択

```bash
veles models openrouter            # cached 24h
veles models openrouter --refresh  # bypass cache
veles models ollama                # always live
```

ジョブごとに異なるモデルを使う場合（圧縮には安価なもの、計画には強力なもの）、[タスク別ルーティング](../how-to/per-task-routing.md)を参照してください。

# 環境変数

> 🌐 **言語:** [English](../../en/reference/environment-variables.md) · [简体中文](../../zh-CN/reference/environment-variables.md) · [繁體中文](../../zh-TW/reference/environment-variables.md) · **日本語** · [한국어](../../ko/reference/environment-variables.md) · [Español](../../es/reference/environment-variables.md) · [Français](../../fr/reference/environment-variables.md) · [Italiano](../../it/reference/environment-variables.md) · [Português (BR)](../../pt-BR/reference/environment-variables.md) · [Português (PT)](../../pt-PT/reference/environment-variables.md) · [Русский](../../ru/reference/environment-variables.md) · [العربية](../../ar/reference/environment-variables.md) · [हिन्दी](../../hi/reference/environment-variables.md) · [বাংলা](../../bn/reference/environment-variables.md) · [Tiếng Việt](../../vi/reference/environment-variables.md)

Veles は実行時にこれらを読み取ります。API キーとトークンは OS キーチェーン（`veles secret set …`）に保存するのが最適です。環境変数はフォールバックおよび上書き用です。

## プロバイダーの API キー

API キーの参照カスケード: OS キーチェーン（プロジェクトスコープ）→ OS キーチェーン（デフォルトスコープ）→ 環境変数。

| 変数 | プロバイダー | 備考 |
|---|---|---|
| `OPENROUTER_API_KEY` | openrouter | デフォルトのプロバイダー |
| `ANTHROPIC_API_KEY` | anthropic | Anthropic API への直接接続 |
| `OPENAI_API_KEY` | openai | OpenAI API への直接接続 |
| `GEMINI_API_KEY` | gemini | Google Gemini の主キー |
| `GOOGLE_API_KEY` | gemini | Google Gemini のフォールバック |

`claude-cli` と `gemini-cli` は各自のバイナリを通じて認証します。環境変数は不要です。

## ローカルプロバイダー

| 変数 | デフォルト | 目的 |
|---|---|---|
| `OLLAMA_BASE_URL` | `http://localhost:11434/v1` | Ollama のエンドポイント |
| `OLLAMA_HOST` | `OLLAMA_BASE_URL` に従う | 埋め込み用の Ollama ホスト |
| `LLAMACPP_BASE_URL` | `http://localhost:8080/v1` | llama.cpp サーバーのエンドポイント |
| `OPENAI_COMPAT_BASE_URL` | — (required) | `openai-compat` プロバイダーのエンドポイント |
| `VELES_LOCAL_TOOLS` | off | ローカルプロバイダーでツール呼び出しを有効にする（`1`/`true`） |
| `VELES_OLLAMA_EMBED_MODEL` | プロバイダーのデフォルト | Ollama の埋め込みモデルを上書きする |

## チャンネルとデーモン

| 変数 | デフォルト | 目的 |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | — | `veles channel run --channel telegram` 用の Telegram ボットトークン |
| `VELES_DAEMON_URL` | `http://127.0.0.1:8765` | チャンネルゲートウェイが使うデーモンのベース URL |
| `VELES_DAEMON_TOKEN` | — | デーモン認証用のベアラートークン |

## パスとロケール

| 変数 | デフォルト | 目的 |
|---|---|---|
| `VELES_USER_HOME` | `~` | `~/.veles/`（状態、キャッシュ、キーチェーンインデックス）を保持するホームを上書きする |
| `VELES_REGISTRY_PATH` | `~/.veles/…` | マルチプロジェクトレジストリのパスを上書きする |
| `VELES_LOCALE` | `[user] language` or `en` | 1 回の実行に対してアクティブな UI ロケールを上書きする |
| `VELES_LOG_LEVEL` | `INFO` | デーモン/ログの詳細度（`DEBUG`/`INFO`/`WARNING`/`ERROR`） |

## 挙動とフィーチャーフラグ

| 変数 | デフォルト | 目的 |
|---|---|---|
| `VELES_NO_WIZARD` | off | 初回ウィザードをスキップする（TTY も必要） |
| `VELES_MANAGER_MODE` | off | `veles run` でマルチエージェントマネージャーを強制する（`1` で有効 / `0` でキルスイッチ） |
| `VELES_VERIFY_MODE` | off | `veles run` で検証 → エスカレーションのパスを強制する（`1` で有効 / `0` でキルスイッチ） |
| `VELES_FENCED_TOOLS` | off | ツールをフェンス化/サンドボックス化された実行経路で実行する |
| `VELES_TRUST_AUTO_ALLOW` | off | 信頼ラダーをバイパスする（CI / オートパイロット / 事前承認済みサブエージェント） |
| `VELES_SANDBOX_ROOTS` | project + `~/.veles` | 読み取り/書き込みサンドボックスのルートを `:` 区切りで上書きする |
| `VELES_FETCH_ALLOW_PRIVATE` | off | ツールが RFC-1918 / プライベートアドレスを取得するのを許可する |
| `VELES_MEMORY_RERANK` | on | メモリ想起のベクトルリランキング（`0`/`false` で無効化） |
| `VELES_WEB_SEARCH_BACKEND` | auto | `research` と `web_search` 用の Web 検索バックエンド |

## レジストリ

| 変数 | 目的 |
|---|---|
| `VELES_SKILLS_REGISTRY_URL` | `veles browse skills` のソース |
| `VELES_MODULES_REGISTRY_URL` | `veles browse modules` のソース |

## 内部 / テスト用

| 変数 | 目的 |
|---|---|
| `VELES_BUNDLE_VERSION` | 内部用。設定する必要はないはずです |
| `VELES_REPL_SIMPLE` | `1` に設定すると、フルスクリーンの `prompt_toolkit` アプリの代わりに、プレーンな行ベースの REPL ループを強制する（機能が限られたターミナル向けのフォールバック） |

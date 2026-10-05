# プロバイダーを設定する方法

> 🌐 **言語:** [English](../../en/how-to/configure-providers.md) · [简体中文](../../zh-CN/how-to/configure-providers.md) · [繁體中文](../../zh-TW/how-to/configure-providers.md) · **日本語** · [한국어](../../ko/how-to/configure-providers.md) · [Español](../../es/how-to/configure-providers.md) · [Français](../../fr/how-to/configure-providers.md) · [Italiano](../../it/how-to/configure-providers.md) · [Português (BR)](../../pt-BR/how-to/configure-providers.md) · [Português (PT)](../../pt-PT/how-to/configure-providers.md) · [Русский](../../ru/how-to/configure-providers.md) · [العربية](../../ar/how-to/configure-providers.md) · [हिन्दी](../../hi/how-to/configure-providers.md) · [বাংলা](../../bn/how-to/configure-providers.md) · [Tiếng Việt](../../vi/how-to/configure-providers.md)

Veles を OpenRouter、Anthropic、OpenAI、Gemini、ローカルモデル、または CLI サブスクリプションのあいだで切り替えます。プロバイダーの全一覧は[プロバイダーリファレンス](../reference/providers.md)を参照してください。

## コマンドごとにプロバイダーを選ぶ

```bash
veles run --provider anthropic --model claude-sonnet-4.6 "..."
veles run --provider openai     --model gpt-4o            "..."
veles run --provider gemini     --model gemini-2.5-pro    "..."
```

## プロジェクトのデフォルトを設定する

`<project>/.veles/config.toml` にベースを記述します:

```toml
[engine]
provider = "openrouter"                 # provider name
model = "anthropic/claude-sonnet-4.6"  # model id
```

あるいは `~/.veles/config.toml` にユーザーグローバルなデフォルトを記述します:

```toml
[user]
default_provider = "openrouter"
default_model = "anthropic/claude-sonnet-4.6"
```

## API キーを設定する

クラウドプロバイダーにはキーが必要です。OS のキーチェーンに一度だけ保存します:

```bash
veles secret set OPENROUTER_API_KEY
veles secret set ANTHROPIC_API_KEY
```

…または[環境変数](../reference/environment-variables.md)をエクスポートします:

```bash
export OPENROUTER_API_KEY=sk-or-v1-...
```

探索順序: キーチェーン（プロジェクトスコープ）→ キーチェーン（デフォルト）→ 環境変数。キーが設定ファイルに書き込まれることは**決してありません**。

## 完全にローカルなモデルを使う（キー不要）

[Ollama](https://ollama.com) をインストールし、モデルを pull して、Veles を向けます:

```bash
ollama pull qwen3:4b-instruct
veles models ollama                     # confirm it's listed
veles run --provider ollama --model qwen3:4b-instruct "Hello"
```

ツール呼び出しは、サーバーが通知する内容から**検出**されます。`VELES_LOCAL_TOOLS=1` で強制的に有効にできます（`=0` で無効）。

サーバーがデフォルトのポートにない場合は、エンドポイントを上書きします:

```bash
export OLLAMA_BASE_URL=http://localhost:11434/v1
export LLAMACPP_BASE_URL=http://localhost:8080/v1
export OPENAI_COMPAT_BASE_URL=http://my-host:8000/v1   # required for openai-compat
```

## 独自のプロバイダーを追加する

ホスト型の OpenAI 互換 API でも、自分で動かすサーバーでも、`~/.veles/providers.toml` にエントリーを 1 つ書けばプロバイダーになります — コードは不要です。id はテーブル名です:

```toml
[providers.groq]
kind = "openai-api"                          # a hosted API; needs a key
label = "Groq"                               # shown in the wizards (optional)
base_url = "https://api.groq.com/openai/v1"
key_env = ["GROQ_API_KEY"]

[providers.lmstudio]
kind = "local"                               # a server you run; a key is optional
base_url = "http://localhost:1234/v1"
```

あとはビルトインと同じように使います:

```bash
veles secret set GROQ_API_KEY      # into the keychain, where the groq entry reads it
veles models groq
veles run --provider groq --model llama-3.3-70b-versatile "..."
```

| キー | 意味 |
|---|---|
| `kind` | `openai-api`（ホスト型 API）または `local`（自分で動かすサーバー） |
| `base_url` | OpenAI 互換のエンドポイント。`/v1`（またはそのプロバイダー相当のパス）で終わる |
| `base_url_env` | 設定されていれば `base_url` を上書きする環境変数 |
| `key_env` | キーを読み取る環境変数名。キーチェーンが先に試されます |
| `label`、`tagline` | ウィザードでの表示のされ方 |
| `tools` | `auto`（デフォルト）、`on`、`off` — モデルにツール呼び出しを渡すかどうか |

ビルトインと同じ id のエントリー（`[providers.ollama]`）は、そのプロバイダーの設定（たとえば `base_url`）を変更しますが、kind は変更しません。壊れたファイルは一度だけ報告され、Veles はビルトインのプロバイダーで動作を続けます。`veles doctor` がファイルの問題点を一覧表示します。

よく使われる API の出発点です — **Veles チームによる検証は行っていません**。現在のエンドポイントはプロバイダーのドキュメントで確認してください:

| id | `base_url` | `key_env` |
|---|---|---|
| `groq` | `https://api.groq.com/openai/v1` | `GROQ_API_KEY` |
| `deepseek` | `https://api.deepseek.com/v1` | `DEEPSEEK_API_KEY` |
| `mistral` | `https://api.mistral.ai/v1` | `MISTRAL_API_KEY` |
| `together` | `https://api.together.xyz/v1` | `TOGETHER_API_KEY` |
| `xai` | `https://api.x.ai/v1` | `XAI_API_KEY` |
| `fireworks` | `https://api.fireworks.ai/inference/v1` | `FIREWORKS_API_KEY` |
| `deepinfra` | `https://api.deepinfra.com/v1/openai` | `DEEPINFRA_API_KEY` |
| `nebius` | `https://api.studio.nebius.com/v1` | `NEBIUS_API_KEY` |
| `cerebras` | `https://api.cerebras.ai/v1` | `CEREBRAS_API_KEY` |
| `zai` | `https://api.z.ai/api/paas/v4` | `ZAI_API_KEY` |
| `moonshot` | `https://api.moonshot.ai/v1` | `MOONSHOT_API_KEY` |
| `lmstudio` (`local`) | `http://localhost:1234/v1` | — |
| `vllm` (`local`) | `http://localhost:8000/v1` | — |

## Claude / Google サブスクリプションに委譲する

`claude` CLI が認証済みであれば、Veles はそれを駆動できます:

```bash
veles run --provider claude-cli "..."
```

Google のサブスクリプションの場合は、Antigravity CLI（`agy`）を一度インストールしてログインし、そのプロバイダーを指定します — `antigravity-cli` モジュールは、その実行時に接続済みのレジストリから自動的にインストールされます:

```bash
veles run --provider antigravity-cli --model gemini-3.8-flash-high "..."
veles models antigravity-cli
```

API キーは不要です — 認証は CLI が処理します。

## 利用可能なモデルを一覧表示する

```bash
veles models openrouter            # cloud: cached 24h
veles models openrouter --refresh  # force re-fetch
veles models ollama                # local: always live
```

## 次に

- [タスクごとに異なるモデルへルーティングする](per-task-routing.md) — 圧縮には安価なモデル、プランニングには強力なモデルを。

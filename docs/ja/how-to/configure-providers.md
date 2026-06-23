# プロバイダーを設定する方法

> 🌐 **言語:** **English** · [Русский](../../ru/how-to/configure-providers.md)

Veles を OpenRouter、Anthropic、OpenAI、Gemini、ローカルモデル、または CLI
サブスクリプションのあいだで切り替えます。プロバイダーの全一覧は [プロバイダーリファレンス](../reference/providers.md) を参照してください。

## コマンドごとにプロバイダーを選ぶ

```bash
veles run --provider anthropic --model claude-sonnet-4.6 "..."
veles run --provider openai     --model gpt-4o            "..."
veles run --provider gemini     --model gemini-2.5-pro    "..."
```

## プロジェクトのデフォルトを設定する

`<project>/.veles/config.toml` にベースを記述します:

```toml
[provider]
default = "openrouter:anthropic/claude-sonnet-4.6"
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

…または [環境変数](../reference/environment-variables.md) をエクスポートします:

```bash
export OPENROUTER_API_KEY=sk-or-v1-...
```

探索順序: キーチェーン（プロジェクトスコープ）→ キーチェーン（デフォルト）→ 環境変数。キーが
設定ファイルに書き込まれることは **決してありません**。

## 完全にローカルなモデルを使う（キー不要）

[Ollama](https://ollama.com) をインストールし、モデルを pull して、Veles を向けます:

```bash
ollama pull qwen3:4b-instruct
veles models ollama                     # 一覧に表示されることを確認
veles run --provider ollama --model qwen3:4b-instruct "Hello"
```

ローカルプロバイダーでは、ツール呼び出しは **デフォルトでオフ** です。ツール対応の
モデルを選んだら有効にしてください:

```bash
export VELES_LOCAL_TOOLS=1
```

サーバーがデフォルトのポートにない場合は、エンドポイントを上書きします:

```bash
export OLLAMA_BASE_URL=http://localhost:11434/v1
export LLAMACPP_BASE_URL=http://localhost:8080/v1
export OPENAI_COMPAT_BASE_URL=http://my-host:8000/v1   # required for openai-compat
```

## Claude / Gemini CLI サブスクリプションに委譲する

`claude` または `gemini` CLI が認証済みであれば、Veles はそれを駆動できます:

```bash
veles run --provider claude-cli "..."
veles run --provider gemini-cli "..."
```

API キーは不要です — 認証は CLI が処理します。

## 利用可能なモデルを一覧表示する

```bash
veles models openrouter            # クラウド: 24時間キャッシュ
veles models openrouter --refresh  # 強制的に再取得
veles models ollama                # ローカル: 常にライブ
```

## 次に

- [タスクごとに異なるモデルへルーティングする](per-task-routing.md) — 圧縮には安価なモデル、
  プランニングには強力なモデルを。

# はじめに

> 🌐 **言語:** [English](../../en/tutorials/getting-started.md) · [简体中文](../../zh-CN/tutorials/getting-started.md) · [繁體中文](../../zh-TW/tutorials/getting-started.md) · **日本語** · [한국어](../../ko/tutorials/getting-started.md) · [Español](../../es/tutorials/getting-started.md) · [Français](../../fr/tutorials/getting-started.md) · [Italiano](../../it/tutorials/getting-started.md) · [Português (BR)](../../pt-BR/tutorials/getting-started.md) · [Português (PT)](../../pt-PT/tutorials/getting-started.md) · [Русский](../../ru/tutorials/getting-started.md) · [العربية](../../ar/tutorials/getting-started.md) · [हिन्दी](../../hi/tutorials/getting-started.md) · [বাংলা](../../bn/tutorials/getting-started.md) · [Tiếng Việt](../../vi/tutorials/getting-started.md)

このチュートリアルでは、Veles をインストールし、API キーを与え、最初のプロジェクトを作成して、最初のプロンプトを実行します。所要時間は約 10 分です。最後には、対話できる動作する Veles プロジェクトが手に入ります。

## 前提条件

- **Python 3.13+**（Veles は `>=3.13` を必要とします）。
- LLM API キー。ここでは **OpenRouter**（デフォルトのプロバイダー）を使用します。キー不要の完全ローカルなものを含め、[その他のプロバイダー](../reference/providers.md)のいずれでも動作します。

## 1. インストール

Veles は [uv](https://docs.astral.sh/uv/) を使ってグローバルな `veles` コマンドとしてインストールします:

```bash
# install uv if you don't have it
curl -LsSf https://astral.sh/uv/install.sh | sh

# install veles (published as `veles-ai`; the command is `veles`)
uv tool install veles-ai
# …or from a source checkout: uv tool install .

# verify
veles --help
```

後で更新するには: `uv tool upgrade veles-ai`。

## 2. Veles に API キーを与える

[openrouter.ai](https://openrouter.ai) からキーを取得してエクスポートします:

```bash
export OPENROUTER_API_KEY=sk-or-v1-...
```

シェルごとに再エクスポートしなくて済むよう、OS のキーチェーンに保存することもできます:

```bash
veles secret set OPENROUTER_API_KEY
```

（キー不要の完全ローカルなセットアップがお好みですか？ [Ollama](https://ollama.com) をインストールし、`ollama pull qwen3:4b-instruct` を実行して、以下で `--provider ollama` を使ってください。）

## 3. 最初のプロジェクトを作成する

Veles プロジェクトとは、`.veles/` 状態フォルダを持つ単なるディレクトリです。作成しましょう:

```bash
mkdir my-notes && cd my-notes
veles init my-notes
```

これにより、`AGENTS.md`（プロジェクトコンテキスト）、`sources/` と `wiki/`（デフォルトの [LLM-Wiki レイアウト](../explanation/layout-packs-and-llm-wiki.md)）、そして `.veles/`（マシン状態）が作成されます。[プロジェクトレイアウト](../reference/project-layout.md)を参照してください。

## 4. 最初のプロンプトを実行する

```bash
veles run "Read AGENTS.md and describe this project in three sentences."
```

Veles はプロジェクトコンテキストを読み込み、モデルを呼び出し、回答を表示します。このターンはプロジェクトのメモリに保存されます。

`--stream` を追加するとトークンが届くたびに表示され、`--verbose` でターンごとの進捗が表示されます:

```bash
veles run --stream "What files exist in this project right now?"
```

## 5. 対話型 REPL を開く

複数ターンの会話には、TUI を開きます:

```bash
veles tui
```

メッセージを入力して Enter を押します。便利なキー: 終了は `Ctrl+D`、[実行モード](../explanation/modes.md)の切り替えは `Shift+Tab`、スラッシュコマンドの一覧は `/help`。完全な一覧は [TUI リファレンス](../reference/tui.md)にあります。

## 6. Veles が何を記憶しているか確認する

すべての実行は保存されます。セッションを一覧表示して検索しましょう:

```bash
veles sessions list
veles sessions search "three sentences"
```

## 次に進む先

- **[ナレッジベースを構築する](building-a-knowledge-base.md)** — ソースを wiki に取り込み、それらについて質問します。
- **[プロバイダーを設定する](../how-to/configure-providers.md)** — Anthropic、OpenAI、Gemini、または完全ローカルのモデルに切り替えます。
- **[アーキテクチャ概要](../explanation/architecture.md)** — Veles が内部で何をしているかを理解します。

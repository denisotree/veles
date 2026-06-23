# アーキテクチャ概要

> 🌐 **言語:** [English](../../en/explanation/architecture.md) · [简体中文](../../zh-CN/explanation/architecture.md) · [繁體中文](../../zh-TW/explanation/architecture.md) · **日本語** · [한국어](../../ko/explanation/architecture.md) · [Español](../../es/explanation/architecture.md) · [Français](../../fr/explanation/architecture.md) · [Italiano](../../it/explanation/architecture.md) · [Português (BR)](../../pt-BR/explanation/architecture.md) · [Português (PT)](../../pt-PT/explanation/architecture.md) · [Русский](../../ru/explanation/architecture.md) · [العربية](../../ar/explanation/architecture.md) · [हिन्दी](../../hi/explanation/architecture.md) · [বাংলা](../../bn/explanation/architecture.md) · [Tiếng Việt](../../vi/explanation/architecture.md)

このページでは、Veles が *何であるか*、そして各部分がどのように組み合わさっているかを説明し、ドキュメントの残りの部分が理解しやすくなるようにします。正式なプロダクトビジョンについては、リポジトリのルートにある `VISION.md` を参照してください。

## 設計の意図

Veles は意図的に **ミニマルでクリーンに分解された** 設計になっています。単一責任のモジュール群で構成され、巨大なファイル（god-file）は存在しません。また **ローカルファースト** です。マシン上のディレクトリに対して実行し、そこに自身の構造化されたメモリを保持します。

## 5 つの柱（コア）

コアにあるものはすべて、次の 5 つの役割のいずれかを担います。

1. **プロジェクトメモリ** — セッションログ、学習したルール/インサイト、プロジェクトのファイルマップ、テレメトリ付きのスキル/ツールレジストリを保持する構造化された成果物（あなたのコンテンツとは分離されている）。[プロジェクトメモリと学習ループ](project-memory-and-learning-loop.md)を参照。
2. **学習ループ** — メモリを最新に保ち、経験を再利用可能なルールへと変える curator、インサイト抽出器、そして dreaming。
3. **マルチエージェントオーケストレーション** — タスクを分解し、専門化されたワーカーをスポーンするマネージャー。[マルチエージェントオーケストレーション](multi-agent-orchestration.md)を参照。
4. **プロバイダプロトコル** — 多数の LLM バックエンド（クラウド、ローカル、CLI 委譲）に対する単一のインターフェース。[プロバイダ](../reference/providers.md)を参照。
5. **最小限のツールとスキル** — 小さなブートストラップセットであり、Veles が自身のツールを書き、繰り返されるプロセスをスキルとして形式化するにつれて **蓄積されていく**。[スキルとツール](skills-and-tools.md)を参照。

## それ以外はすべてオプションのモジュール

ゲートウェイ/チャネル、デーモン、スケジューラ、TUI、ビジョン/STT — これらはすべて **プラガブル** であり、使用されたときにのみロードされます。Veles は最小限の構成で起動し、必要に応じて拡張するため、シンプルな `veles run` はシンプルなままです。

## 1 ターンの流れ

```
your prompt
   │
   ▼
context: AGENTS.md (small) + on-demand recall from project memory
   │
   ▼
agent loop  ──►  provider (routed per task)  ──►  tool calls
   │                                               │
   │            (trust ladder gates sensitive tools)
   ▼
response  ──►  saved to memory  ──►  learning triggers (insights, curator)
```

コンテキストファイル（`AGENTS.md`）は意図的に小さく保たれます。補助的な知識（wiki ページ、プロジェクトのファイルマップ、関連する過去のターン）は、最初にまとめて投入されるのではなく、**必要に応じて** 取り込まれます。

## 状態がどこに存在するか

- `<project>/.veles/` — このプロジェクトのメモリ、設定、ローカルのスキル/ツール。
- `~/.veles/` — ユーザーグローバルの設定、プロジェクト横断のスキル/ツール、キャッシュ、トラスト。
- `<project>/AGENTS.md`、`wiki/`、`sources/` — あなたのコンテンツ（LLM-Wiki レイアウト）。

[プロジェクトレイアウト](../reference/project-layout.md)を参照。

## 1 つのループで複数プロジェクト

1 つのエージェントループが多数のプロジェクトに対応します。各プロジェクトは独自のコンテキストとメモリを持つ専用ディレクトリを取得します。`AGENTS.md` は `CLAUDE.md`/`GEMINI.md` にシンボリックリンクされるため、そこで起動された外部 CLI も同じコンテキストを参照します。[複数プロジェクト](../how-to/multi-project-and-subprojects.md)を参照。

## 操作面（サーフェス）

- **CLI**（`veles run`、`veles add`、…）— ワンショットおよびスクリプト用途。
- **TUI**（`veles tui`）— [実行モード](modes.md)を備えたインタラクティブな REPL。
- **デーモン + チャネル** — ヘッドレス API、Telegram、スケジュールジョブ。

これら 3 つはすべて同じコアのエージェントループを駆動します。

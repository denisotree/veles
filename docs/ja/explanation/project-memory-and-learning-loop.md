# プロジェクトメモリと学習ループ

> 🌐 **言語:** [English](../../en/explanation/project-memory-and-learning-loop.md) · [简体中文](../../zh-CN/explanation/project-memory-and-learning-loop.md) · [繁體中文](../../zh-TW/explanation/project-memory-and-learning-loop.md) · **日本語** · [한국어](../../ko/explanation/project-memory-and-learning-loop.md) · [Español](../../es/explanation/project-memory-and-learning-loop.md) · [Français](../../fr/explanation/project-memory-and-learning-loop.md) · [Italiano](../../it/explanation/project-memory-and-learning-loop.md) · [Português (BR)](../../pt-BR/explanation/project-memory-and-learning-loop.md) · [Português (PT)](../../pt-PT/explanation/project-memory-and-learning-loop.md) · [Русский](../../ru/explanation/project-memory-and-learning-loop.md) · [العربية](../../ar/explanation/project-memory-and-learning-loop.md) · [हिन्दी](../../hi/explanation/project-memory-and-learning-loop.md) · [বাংলা](../../bn/explanation/project-memory-and-learning-loop.md) · [Tiếng Việt](../../vi/explanation/project-memory-and-learning-loop.md)

Veles を特徴づけるのは、プロジェクトごとに**記憶**し**学習**する点です。この
ページでは、そのメモリとは何か、そして学習ループがどのようにメモリを有用に保ち続けるのかを説明します。

## メモリは構造化されたアーティファクトである

プロジェクトメモリは `<project>/.veles/` に格納されます。`memory.db`（SQLite、信頼できる
唯一の情報源）に加え、人間が読める `.veles/memory/` ツリー（レンダリングされたインサイトビュー、
セッションダイジェスト、提案、システム運用ジャーナル）から構成されます。これは**あなたの
コンテンツとは分離されており**、どのレイアウト（wiki、notes、bare）でも同一に機能します。
チャット記録をそのまま吐き出したものではなく、構造化されたレイヤーの集合です:

- **セッションログ** — すべての会話。ターンごとに 1 行で、全文検索インデックス付き。
- **ルール** — エージェントが従うべき短い命令文（`format`、`do`、`don't`、
  `preference`）。安定したシステムプロンプトに注入されます。
- **インサイト** — セッションから抽出された教訓。SQL の行が正規データであり
  （リコール、エイジング、重複排除はこの行に対して動作します）、人間と
  エクスポート向けに markdown ビューが `.veles/memory/insights/` にレンダリングされます。
- **プロジェクトツリーマップ** — 意味的にタグ付けされキャッシュされたファイルマップ。これにより
  エージェントはツリー全体ではなく、関連する 3〜5 個のファイルを読みます。
- **スキル & ツールレジストリ** — ランキングと重複排除が使用するテレメトリ
  （使用回数 / 成功回数 / エラー回数）付き。

テーブル一覧については [プロジェクトレイアウト](../reference/project-layout.md#project-memory-velesmemorydb) を参照してください。

## リコール: 小さなコンテキストを必要に応じて引き出す

`AGENTS.md` は意図的に小さく保たれています。何かを尋ねると、Veles は関連するものだけを
引き込みます: 一致する過去のターン（全文検索 + オプションのベクトル再ランキング）、
適用可能なルールとインサイト、そしてプロジェクトツリーマップが最高スコアを付けたファイルです。
これにより、すべてを吐き出すのではなく、各モデル呼び出しを焦点を絞った安価なものに保ちます。

## 学習ループ

経験は、3 つのメカニズムを通じて永続的な知識になります:

### インサイト — 教訓を捉える
実行後、エクストラクターは記憶する価値のあるものを探します: 明示的な「remember
X」/「never Y」というフィードバック、そしてツールエラー → リカバリのパターン（失敗の後に
修正が続くもの）です。これらをインサイトとルールに抽出し、同じ間違いが繰り返されないようにします。

### キュレーター — セッションの統合
キュレーターは古いセッションを永続的なメモリに抽出します: SQL のインサイトとルールは
常に作成され、加えてプロジェクトのレイアウトが wiki エンジンを有効にしている場合は
`wiki/sessions/` ページも作成されます。アイドル時 / ターン後のタイマー、または `veles curate` で
オンデマンドに実行されます。

### ドリーミング — バックグラウンドメンテナンス
`veles dream`（およびアイドル時のデーモン）は、インサイトを抽出し、スキルと
インサイトを重複排除し、昇格を提案し、（wiki レイアウト下では）wiki を lint します。
これによりあなたをブロックすることなくメモリを新鮮に保ちます。より深い LLM パスには
`--include-consolidation` を追加してください。

## コンテキスト圧縮

長い会話は、スライディングウィンドウ圧縮機によってモデルのコンテキスト上限内に
保たれます: メモリ内の履歴がトークン閾値を超えると、中間部分が
（安価にルーティングされたモデルによって）要約され、`.veles/memory/sessions/` に保存された
要約へのポインタに置き換えられます。完全な履歴は常に `memory.db` に残ります。圧縮されるのは
メモリ内のウィンドウだけなので、ディスク上ではロスレスです。

## なぜこれが重要なのか

メモリが構造化されており、ループが継続的に実行されるため、Veles プロジェクトは
**使えば使うほど有用になります**。あなたの慣習を学び、繰り返しのエラーを避け、
実際に見てきたものに基づいて回答を裏付けます。

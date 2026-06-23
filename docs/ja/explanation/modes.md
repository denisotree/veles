# 実行モード

> 🌐 **言語:** [English](../../en/explanation/modes.md) · [简体中文](../../zh-CN/explanation/modes.md) · [繁體中文](../../zh-TW/explanation/modes.md) · **日本語** · [한국어](../../ko/explanation/modes.md) · [Español](../../es/explanation/modes.md) · [Français](../../fr/explanation/modes.md) · [Italiano](../../it/explanation/modes.md) · [Português (BR)](../../pt-BR/explanation/modes.md) · [Português (PT)](../../pt-PT/explanation/modes.md) · [Русский](../../ru/explanation/modes.md) · [العربية](../../ar/explanation/modes.md) · [हिन्दी](../../hi/explanation/modes.md) · [বাংলা](../../bn/explanation/modes.md) · [Tiếng Việt](../../vi/explanation/modes.md)

TUI では、各プロンプトは **実行モード** によって処理されます。これは、そのターンにどれだけの自律性とどのツールを与えるかを決める戦略です。モードは `Shift+Tab` で切り替えます。順序は `auto → planning → writing → goal` です。

## 4 つのモード

### `writing` — ダイレクトチャット
最も素直なモードです。プロンプトはフルのツールセットが利用可能な状態でエージェントに渡され、エージェントが応答します。エージェントに実際に行動してほしい通常の作業に使います。

### `planning` — 読み取り専用の調査 + プラン
変更操作はブロックされます（`write_file` なし、`run_shell` なし）。エージェントは読み取り/検索ツールを使ってコンテキストを集め、その後、構造化されたプラン成果物を生成します。何かに触れる前に考えるために使います。あるいは、CLI で同じ効果を得るには `veles run` に `--plan` を渡します。

### `auto` — スマートルーティング（デフォルト）
素早い分類により、プロンプトがダイレクトなリクエストなのか、それともプランニングを要するのかを判断し、それに応じて `writing` または `planning` にディスパッチします。意図を明示していないときの最も賢いフォールバックであり、これがサイクルのデフォルトの最初の地点となっている理由です。

### `goal` — 長期的な目標
複数ステップの目標のための有限状態機械を駆動します。明確化のためにあなたにインタビューし、プランを確認し、ステップを実行し（advisor のチェック付き）、完了条件を検証します — すべて明示的な予算の下で行われます。CLI での同等物は [`veles goal`](../how-to/long-running-tasks.md#goals--objectives-with-budgets-and-checkpoints) コマンド群です。

## なぜモードが存在するのか

リクエストによって、必要な慎重さの度合いは異なります。ちょっとした質問に大げさな手続きは不要ですし、リスクのある変更はまず読み取り専用のプランニングパスを経ると有益で、大きな目標には予算とチェックポイントが必要です。モードはその選択を明示的にし、セッション全体に 1 つの振る舞いを焼き付ける代わりに、ターンごとに切り替えられるようにします。

セッションの途中で切り替えると、エージェントには新しいルールが伝えられるため、その振る舞いは即座に変わります。

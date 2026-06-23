# マルチエージェントオーケストレーション

> 🌐 **言語:** [English](../../en/explanation/multi-agent-orchestration.md) · [简体中文](../../zh-CN/explanation/multi-agent-orchestration.md) · [繁體中文](../../zh-TW/explanation/multi-agent-orchestration.md) · **日本語** · [한국어](../../ko/explanation/multi-agent-orchestration.md) · [Español](../../es/explanation/multi-agent-orchestration.md) · [Français](../../fr/explanation/multi-agent-orchestration.md) · [Italiano](../../it/explanation/multi-agent-orchestration.md) · [Português (BR)](../../pt-BR/explanation/multi-agent-orchestration.md) · [Português (PT)](../../pt-PT/explanation/multi-agent-orchestration.md) · [Русский](../../ru/explanation/multi-agent-orchestration.md) · [العربية](../../ar/explanation/multi-agent-orchestration.md) · [हिन्दी](../../hi/explanation/multi-agent-orchestration.md) · [বাংলা](../../bn/explanation/multi-agent-orchestration.md) · [Tiếng Việt](../../vi/explanation/multi-agent-orchestration.md)

複雑な作業に対して、Veles はすべてを 1 つのコンテキストで行う代わりに、タスクを **マネージャー** と専門化された **ワーカー** サブエージェントに分割できます。このページではそのモデルを説明します。有効化するには、[マネージャーモード](../how-to/long-running-tasks.md#manager-mode--decompose-any-prompt)を参照してください。

## その形

```
            manager  (decomposes the task, never writes the final answer)
           /    |    \
    explorer  writer  advisor   (specialised workers, run in parallel)
```

- **マネージャー** は分解を計画し、調整します — しかし最終的な成果物を自身で **書くことはありません**。
- **ワーカー** はロール固有のシステムプロンプトを持ちます: `explorer` は収集し、`writer` は答えを生成し、`advisor` はレビューします。このセットは拡張可能です。
- 最後に、マネージャーは短いレポートをメモリに書き込みます。

## 伝言ゲームはなし

重要なルール: 中間成果物は、マネージャーによる言い換えではなく、**そのまま（verbatim）** 統合者に届きます。explorer の調査結果は writer に直接手渡されるため、要約の連鎖を通じて細部が失われることはありません。これこそが、分解が品質を希釈するのではなく付加するものにしている要因です。

## なぜ「マネージャーは決して書かない」のか

もし調整役が答えも書いていたら、ワーカーを近道で済ませてしまい、専門化の利点を失う誘惑に駆られるでしょう。統合を専用の `writer`（そのまま渡された入力を与えられる）に留めることで、分業が強制されます。Veles はこれをランタイムでの保証としています。

## いつ役立ち — いつ役立たないか

分解は、広範または多面的なタスク（このコードベースを監査する、この問いを複数の角度から調査する）で効果を発揮します。素早く、単一コンテキストのリクエストには、ただオーバーヘッドを増やすだけです — これがマネージャーモードが **明示的なオプトイン** であり、デフォルトでオフ（`veles run --manager` または `VELES_MANAGER_MODE=1`）になっている理由です。

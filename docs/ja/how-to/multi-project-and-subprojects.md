# 複数プロジェクトとサブプロジェクトの扱い方

> 🌐 **言語:** [English](../../en/how-to/multi-project-and-subprojects.md) · [Русский](../../ru/how-to/multi-project-and-subprojects.md) · **日本語**

Veles は 1 つのエージェントループで多数のプロジェクトを実行します。各プロジェクトは独自のメモリ、
スキル、ツールを持ちます。**サブプロジェクト** は親の下にネストされたプロジェクトで、大きな
モノレポやナレッジベースをスコープ付きのメモリへ分解するのに役立ちます。

## プロジェクト

Veles は（`git` のように）カレントディレクトリから `.veles/` ディレクトリまで上方向に辿って
アクティブなプロジェクトを発見します。レジストリの管理は次のとおりです。

```bash
veles project list                  # registered projects, most-recent first
veles project add /path/to/project  # register an existing project
veles project add /path --slug web  # with a custom slug
veles project remove <slug>         # unregister (files untouched)
```

`switch` はパスを出力するので、プロジェクトに `cd` で移動できます。

```bash
cd "$(veles project switch web)"
```

`cd` せずに別の場所にあるプロジェクトに対してコマンドを実行します。

```bash
veles run --project-root /path/to/project "..."
```

## サブプロジェクト

サブプロジェクトとは、親の内部にある子の Veles プロジェクトです。作成は次のとおりです。

```bash
veles subproject init frontend --description "the web client"
veles subproject list
cd "$(veles subproject switch frontend)"
veles subproject remove frontend    # unregister (files untouched)
```

### Veles に分割を提案させる

プロジェクトの wiki が大きくなると、Veles はテーマ別のクラスタを検出し、それらをサブプロジェクト
として提案できます。

```bash
veles subproject suggest            # print candidates
veles subproject suggest --save     # save each to .veles/memory/proposals/ for recall
```

## どちらを使うべきか

- **別々のプロジェクト** — 互いに無関係なナレッジベース／コードベース。
- **サブプロジェクト** — 1 つの大きなものの構成部分で、スコープ付きメモリの恩恵を受けつつ
  親のコンテキストを共有するもの。

マルチプロジェクトのコンテキストが 1 つのモノリシックなダンプとしてではなく、必要に応じて
読み込まれる仕組みについては [アーキテクチャ](../explanation/architecture.md) を参照してください。

# ナレッジベースを構築する

> 🌐 **言語:** [English](../../en/tutorials/building-a-knowledge-base.md) · [简体中文](../../zh-CN/tutorials/building-a-knowledge-base.md) · [繁體中文](../../zh-TW/tutorials/building-a-knowledge-base.md) · **日本語** · [한국어](../../ko/tutorials/building-a-knowledge-base.md) · [Español](../../es/tutorials/building-a-knowledge-base.md) · [Français](../../fr/tutorials/building-a-knowledge-base.md) · [Italiano](../../it/tutorials/building-a-knowledge-base.md) · [Português (BR)](../../pt-BR/tutorials/building-a-knowledge-base.md) · [Português (PT)](../../pt-PT/tutorials/building-a-knowledge-base.md) · [Русский](../../ru/tutorials/building-a-knowledge-base.md) · [العربية](../../ar/tutorials/building-a-knowledge-base.md) · [हिन्दी](../../hi/tutorials/building-a-knowledge-base.md) · [বাংলা](../../bn/tutorials/building-a-knowledge-base.md) · [Tiếng Việt](../../vi/tutorials/building-a-knowledge-base.md)

このチュートリアルでは、Veles プロジェクトを生きたナレッジベースに変えていきます。いくつかのソースを取り込み、Veles に wiki ページを書かせ、質問し、学んだことを統合します。これがデフォルトの **LLM-Wiki** ワークフローです。所要時間は約 15 分です。

先に [はじめに](getting-started.md) を完了しておいてください。

## 考え方

Veles プロジェクトには2つのコンテンツゾーンがあります:

- `sources/` — あなたが与える生の不変な素材（エージェントには読み取り専用）。
- `wiki/` — エージェント自身が生成する、LLM 生成のナレッジ（エージェントがコンテンツを書き込む唯一のゾーン）。

あなたがソースを与えると、Veles はそれらをリンクされた wiki ページに蒸留します。あなたは自然言語で wiki に問い合わせます。その理由については [レイアウトパックと LLM-Wiki](../explanation/layout-packs-and-llm-wiki.md) を参照してください。

## 1. ソースを取り込む

`veles add` はファイルや URL を読み込み、それを要約した wiki ページを書き込みます:

```bash
veles add https://en.wikipedia.org/wiki/Knowledge_management
veles add ./notes/meeting-2026-06-01.md
```

各 `add` は `wiki/` 配下にページを生成し、それを wiki グラフにリンクします。

## 2. wiki が育つのを見る

何が書き込まれたかを見てみましょう:

```bash
ls wiki/concepts wiki/entities wiki/sources
```

ページは互いに相互参照します。オンデマンドの `wiki/INDEX.md` カタログは、エージェントが必要なときに読み込むマップを保持します（モノリシックなコンテキストの一括投入ではありません）。

## 3. 質問する

では、ナレッジベースに自然言語で問い合わせてみましょう:

```bash
veles run "Using the wiki, summarise the main approaches to knowledge management
and cite the pages you used."
```

Veles は wiki を検索し、関連するページを読み、回答します。学習データだけに頼るのではなく、あなたが取り込んだ内容に基づいて回答します。

対話的なやり取りには、TUI（`veles tui`）で同じことを行ってください。

## 4. セッションを統合する

作業を進めるにつれて会話が蓄積されていきます。キュレーターを実行して、それらを永続的な wiki ページにまとめ、教訓を抽出しましょう:

```bash
veles curate
```

これは `wiki/sessions/` ページを書き込み、プロジェクトのインサイトとルールを更新します。Veles は時間の経過とともにこれを自動的にも行います。[プロジェクトメモリと学習ループ](../explanation/project-memory-and-learning-loop.md) を参照してください。

## 5. wiki を健全に保つ

時間が経つとページは古くなったり孤立したりします。`lint` 操作はそれらを見つけ出します:

```bash
veles run "lint"
```

（`ingest`、`query`、`lint` は LLM-Wiki レイアウトに同梱されるスキルです。`veles run "<operation>"` で呼び出すか、エージェントに呼び出させます。）

## 構築したもの

自己組織化するナレッジベース。ソースが入り、リンクされた wiki ページが出てきて、自然言語でクエリ可能であり、Veles が統合するにつれて整理されていきます。ここから先は:

- **[スキル、ツール、モジュールを管理する](../how-to/manage-skills-and-tools.md)** — Veles に再利用可能なワークフローを教える。
- **[デーモンとして実行する](../how-to/run-as-daemon.md)** + **[Telegram を接続する](../how-to/connect-telegram.md)** — スマートフォンからナレッジベースと対話する。
- **[複数のプロジェクトとサブプロジェクト](../how-to/multi-project-and-subprojects.md)** — 多数のナレッジベースにスケールする。

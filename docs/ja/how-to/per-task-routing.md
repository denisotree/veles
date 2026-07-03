# タスクごとに異なるモデルへルーティングする方法

> 🌐 **言語:** [English](../../en/how-to/per-task-routing.md) · [简体中文](../../zh-CN/how-to/per-task-routing.md) · [繁體中文](../../zh-TW/how-to/per-task-routing.md) · **日本語** · [한국어](../../ko/how-to/per-task-routing.md) · [Español](../../es/how-to/per-task-routing.md) · [Français](../../fr/how-to/per-task-routing.md) · [Italiano](../../it/how-to/per-task-routing.md) · [Português (BR)](../../pt-BR/how-to/per-task-routing.md) · [Português (PT)](../../pt-PT/how-to/per-task-routing.md) · [Русский](../../ru/how-to/per-task-routing.md) · [العربية](../../ar/how-to/per-task-routing.md) · [हिन्दी](../../hi/how-to/per-task-routing.md) · [বাংলা](../../bn/how-to/per-task-routing.md) · [Tiếng Việt](../../vi/how-to/per-task-routing.md)

Veles は 1 つのモデルに固定されているわけではありません。内部の各**タスク**は異なる `provider:model` を使えます。コンテキスト圧縮には安価なモデル、メインエージェントには強力なモデル、画像にはビジョンモデル、といった具合です。これが*アンサンブルルーティング*システムです。

## タスクの種類

| タスク | 用途 |
|---|---|
| `default` | メインのエージェントループ |
| `curator` | セッション → wiki 統合 |
| `compressor` | スライディングウィンドウのコンテキスト圧縮 |
| `insights` | 実行後のインサイト抽出 |
| `skills` | スキルの実行 |
| `advisor` | `advisor_review` のセルフチェック |
| `vision` | `image_describe`（ビジョンアダプターが配線されている場合） |
| `embedding` | `veles skill dedup` の類似度計算 |

## 現在のルーティングを確認する

```bash
veles route show
```

これは各タスクについて解決された `provider:model` と、どのレイヤーがそれを決定したかを示す `source` ラベルを出力します。

## タスクをモデルに固定する

```bash
veles route set compressor openrouter:anthropic/claude-haiku-4.5
veles route set advisor    openrouter:anthropic/claude-opus-4.8
veles route set vision     openai:gpt-4o
```

これらは `<project>/.veles/config.toml` に `[routing.tasks]` を書き込みます:

```toml
[routing.tasks]
compressor = "openrouter:anthropic/claude-haiku-4.5"
advisor    = "openrouter:anthropic/claude-opus-4.8"
vision     = "openai:gpt-4o"
```

## リセット

```bash
veles route reset compressor   # one task back to default
veles route reset              # all tasks back to default
```

## AGENTS.md での自然言語ヒント

`AGENTS.md` の中で散文としてルーティングを表現できます（例: 「圧縮には安価なモデルを使う」）。Veles はこれらを解析して、自動生成される `routing.nl.toml` に変換します:

```bash
veles route refresh            # re-parse AGENTS.md hints
veles route refresh --force    # even if AGENTS.md hasn't changed
```

明示的な `[routing.tasks]` のエントリは、常に自然言語ヒントよりも優先されます。

## 解決の順序

各タスクについて、最初にスペックを返したレイヤーが採用されます:

1. プロジェクトの `[routing.tasks][task]`
2. プロジェクトの `[routing.tasks].default`
3. プロジェクトの自然言語ヒント（`routing.nl.toml`）
4. プロジェクトの `[engine]` ベース
5. ユーザーの `[routing.tasks][task]` / `.default`
6. ユーザーの `[user] default_provider` + `default_model`

これらのいずれも解決しない場合、**ハードコードされたフォールバックはありません** — そのタスクは未設定のままとなり、呼び出し側は機能を縮退させる（その機能をスキップする）か、明確にエラーを返します。ひそかにクラウドモデルへ手を伸ばすことはありません。

（`embedding` はキャッチオールをスキップします。チャットモデルは埋め込みモデルではないためです。したがって、明示的な `[routing.tasks].embedding` のみがこれに応えます。）

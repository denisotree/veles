# TUI のキーバインドとスラッシュコマンド

> 🌐 **言語:** [English](../../en/reference/tui.md) · [简体中文](../../zh-CN/reference/tui.md) · [繁體中文](../../zh-TW/reference/tui.md) · **日本語** · [한국어](../../ko/reference/tui.md) · [Español](../../es/reference/tui.md) · [Français](../../fr/reference/tui.md) · [Italiano](../../it/reference/tui.md) · [Português (BR)](../../pt-BR/reference/tui.md) · [Português (PT)](../../pt-PT/reference/tui.md) · [Русский](../../ru/reference/tui.md) · [العربية](../../ar/reference/tui.md) · [हिन्दी](../../hi/reference/tui.md) · [বাংলা](../../bn/reference/tui.md) · [Tiếng Việt](../../vi/reference/tui.md)

`veles tui`（または単に `veles`）はインタラクティブな REPL を開きます。これはスクロールバック付きのチャットで、複数行のコンポーザー、ステータスバー、折りたたみ可能なインスペクターを備えています。

## キーバインド

| キー | 動作 |
|---|---|
| `Ctrl+D` | 終了 |
| `Ctrl+C` | 最後のアシスタント応答をコピー。1.5 秒以内に2回押すと終了 |
| `Ctrl+V` | クリップボードから貼り付け |
| `Ctrl+Shift+C` / `⌘C` | 現在の選択範囲をコピー（OSC52）。macOS の Terminal.app では、ネイティブのドラッグ選択 + ⌘C が直接機能します |
| `Ctrl+I` | インスペクターの表示切り替え（推論、ツールアクティビティ、トークン/エラーログ） |
| `Ctrl+R` | セッションピッカーを開く（過去のセッションを再開） |
| `Ctrl+T` | テーマピッカーを開く |
| `Shift+Tab` | 実行モードを循環: `auto → planning → writing → goal` |
| `Tab` | スラッシュコマンドの補完を循環 |
| `Up` / `Down` | 履歴（およびキューに入ったプロンプトの取り出し） |

実行モードについては [実行モード](../explanation/modes.md) で説明しています。

## スラッシュコマンド

コンポーザーで `/` を入力すると、`Tab` で補完されます。登録されているコマンドは次のとおりです:

| コマンド | 目的 |
|---|---|
| `/help` | 利用可能なコマンドを一覧表示 |
| `/quit`, `/q`, `/exit` | REPL を終了 |
| `/clear` | チャットログをクリア |
| `/model` | モデルピッカーを開く |
| `/mode` | 実行モードを切り替え（auto/planning/writing/goal） |
| `/session` | セッションピッカーを開く（再開） |
| `/save` | 現在のセッションを保存 / 名前を付ける |
| `/history` | セッション履歴を表示 |
| `/tokens` | トークン使用量（入力 / 出力 / ターンごと / セッションごと） |
| `/context` | 現在のコンテキストサイズと上限の比較 |
| `/status` | スナップショット: モデル、プロバイダー、モード、セッション、ビジー状態、キュー |
| `/insights` | プロジェクトの学習済みインサイトを表示 |
| `/rules` | プロジェクトのルールダイジェストを表示 |
| `/schema` | `AGENTS.md` を検証 / 修正 |
| `/wiki` | アクティブなレイアウトに対する wiki 操作 |
| `/daemon` | デーモン制御パネルを開く（プロジェクト → デーモン → チャンネル） |

> スラッシュコマンドのセットは、TUI を直接起動しても別の画面から呼び出しても同じです。チャンネル（例: Telegram）は、それぞれ独立した別のコマンドセットを公開します。

## テーマ

組み込みテーマ: `everforest`（デフォルト）、`dracula`、`gruvbox`、`tokyo-night`、`catppuccin`。`Ctrl+T`、`veles tui --theme <name>`、または `~/.veles/config.toml` の `[user] tui_theme` で選択します。

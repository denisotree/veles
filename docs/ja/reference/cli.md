# CLI リファレンス

> 🌐 **言語:** [English](../../en/reference/cli.md) · **日本語** · [Русский](../../ru/reference/cli.md)

Veles のすべてのコマンド、サブコマンド、フラグの一覧です。正式かつ常に最新のシグネチャは
`veles <command> --help` で確認してください。このページは
`src/veles/cli/_parsers/` の引数パーサーを反映しています。

```
veles [--no-wizard] <command> [subcommand] [options]
```

- `--no-wizard` — `~/.veles/config.toml` が存在しない場合でも初回セットアップ
  ウィザードをスキップします（TTY であること、および `VELES_NO_WIZARD=1` でも制御されます）。
- 引数なしで `veles` を実行すると、対話型の [TUI](tui.md) が起動します。

ほとんどのエージェントコマンドは、ページ下部に記載した
[共通エージェントループフラグ](#shared-agent-loop-flags) と
[プロバイダ名](#provider-names) を受け付けます。

---

## プロジェクトのライフサイクル

### `veles init [name]`
カレントディレクトリに新しい Veles プロジェクトを作成します（`.veles/` 状態ディレクトリ
＋ `AGENTS.md` ＋ 選択したレイアウトパックのコンテンツスキャフォールド）。

| Flag | Default | Purpose |
|---|---|---|
| `name` (positional) | cwd basename | プロジェクト名 |
| `--layout <name>` | `llm-wiki` | コンテンツスキャフォールド用のレイアウトパック（`llm-wiki`、`notes`、`bare`、または `~/.veles/layouts/` のカスタムパック） |
| `--force` | off | すでに存在していても `.veles/` を再作成する |

### `veles schema {validate,edit,fix}`
`AGENTS.md`（プロジェクトのコンテキストファイル）を検証または編集します。

- `validate` — 必須の H2 セクションが揃っているか確認します。
- `edit` — `$EDITOR`（デフォルト `vi`）で `AGENTS.md` を開き、終了時に検証します。
- `fix` — LLM ウィザードを使って不足しているセクションを対話的に追加します。

### `veles self-doc [refresh|show]`
プロジェクトの自己ドキュメント（`wiki/self-doc/overview.md`）を生成して表示します。
引数なしの `veles self-doc` は現在のページを表示し、`refresh` は再生成します。

### `veles doctor`
ユーザーグローバルの状態とアクティブなプロジェクトに対してヘルスチェックを実行します。
アクティブなプロジェクトの有無にかかわらず動作します。

| Flag | Default | Purpose |
|---|---|---|
| `--json` | off | JSON レポートを出力する |
| `--strict` | off | 警告が 1 つでもあれば非ゼロで終了する（CI でのゲーティング用） |

### `veles export {full,template} <path>`
プロジェクトを `.tar.gz` バンドルにまとめます。[バックアップと共有](../how-to/backup-and-share.md) を参照してください。

- `full <path>` — プロジェクト全体（`.veles/` ＋ `AGENTS.md`）から実行時の一時データを除いたもの。
- `template <path>` — サニタイズしたサブセット（スキーマ＋スキル＋モジュール＋セッション以外の
  wiki ページ）。`memory.db`、`sources/`、`sessions/`、`trust` の付与、PII を含むテキストは除去・編集されます。

### `veles import <path>`
`veles export` で作成したバンドルを復元します。

| Flag | Default | Purpose |
|---|---|---|
| `path` (positional) | — | バンドルのパス（`.tar.gz`） |
| `--into <dir>` | cwd | 展開先ディレクトリ |
| `--force` | off | 展開先に既存の `.veles/` があれば上書きする |

---

## エージェントの実行

### `veles run "<prompt>"`
1 つのプロンプトを、メモリ永続化とキュレーター／学習トリガー付きでエンドツーエンドに実行します。
すべての [共通エージェントループフラグ](#shared-agent-loop-flags) に加えて、以下を受け付けます。

| Flag | Default | Purpose |
|---|---|---|
| `--resume <session_id>` | new session | 既存のセッションを継続する |
| `--manager` | off | マルチエージェントマネージャー経由でタスクを分解する（`VELES_MANAGER_MODE=1` でも可） |
| `--plan` | off | プランニングモード: 読み取り／検索／下書きは許可、変更操作はブロック |
| `--no-agents-md` | off | システムプロンプトに `AGENTS.md` を注入しない |
| `--no-index` | off | `wiki/INDEX.md` を注入しない |
| `--no-compress` | off | スライディングウィンドウのコンテキスト圧縮を無効にする |
| `--no-curator` | off | この実行ではキュレータートリガーを無効にする |
| `--no-insights` | off | 実行後のインサイト抽出を無効にする |
| `--no-proposer` | off | サブプロジェクトプロポーザーの自動トリガーを無効にする |
| `--no-route-refresh` | off | `AGENTS.md` からの自然言語ルーティング更新を無効にする |
| `--no-suggest-promote` | off | 自動プロモーションサジェスターを無効にする |
| `--compressor-model <id>` | routed | 圧縮モデルを上書きする |
| `--compress-threshold-tokens <n>` | `50000` | 圧縮を発動させる履歴サイズ |

### `veles tui`
対話型 REPL を開きます。[TUI リファレンス](tui.md) を参照してください。共通エージェントループフラグ、
`--resume`、上記の `--no-*` 注入／圧縮フラグ、および以下を受け付けます。

| Flag | Default | Purpose |
|---|---|---|
| `--theme <name>` | config or `everforest` | カラーテーマ（everforest、dracula、gruvbox、tokyo-night、catppuccin） |

### `veles add <source>`
ソース（ローカルファイルまたは `http(s)://` URL）を読み込み、wiki ページに合成します。
共通エージェントループフラグを受け付けます。

### `veles curate`
キュレーターを 1 回実行します。未処理のセッションを `wiki/sessions/` ページにコンパクト化します。

| Flag | Default | Purpose |
|---|---|---|
| `--limit <n>` | a small default | この実行で処理するセッションの最大数 |

加えて共通エージェントループフラグを受け付けます。

### `veles research "<question>"`
ディープリサーチ: サブクエスチョンに分解 → Web を並列に探索 → 引用付きレポートを合成します。

| Flag | Default | Purpose |
|---|---|---|
| `--max-subquestions <n>` | `4` | 並列のリサーチ観点の数 |

加えて共通エージェントループフラグを受け付けます。

### `veles dream`
バックグラウンドのメモリ統合サイクルを 1 回実行します（インサイト → スキルの重複排除 →
プロモーション提案 → wiki リント、オプションで LLM 統合）。

| Flag | Default | Purpose |
|---|---|---|
| `--include-consolidation` | off | コストの高い LLM 統合を実行する（API キーが必要） |
| `--dry-run` | off | すべてのステップを実行するが `wiki/state` への書き込みはスキップする |
| `--skip-insights` / `--skip-dedup` / `--skip-promote` / `--skip-lint` | off | 個別のステップをスキップする |
| `--consolidation-model <id>` | `anthropic/claude-haiku-4.5` | 統合モデルを上書きする |
| `--provider <name>` | `openrouter` | 統合サブエージェント用のプロバイダ |
| `--project-root <path>` | discover | プロジェクトの上書き指定 |

---

## ナレッジ: スキル、ツール、モジュール

### `veles skill {list,show,add,remove,promote,demote,dedup,suggest-promote}`

| Subcommand | Purpose |
|---|---|
| `list` | アクティブなプロジェクトのスキルを一覧表示する（テレメトリ付き） |
| `show <name>` | スキルの `SKILL.md` を表示する |
| `add <source> [--name N] [--scope project\|user] [-y]` | git URL またはローカルパスからインストールする |
| `remove <name> [--scope project\|user] [-y]` | インストール済みのスキルを削除する |
| `promote <name> [--keep-telemetry]` | プロジェクトスキルをユーザースコープ（`~/.veles/skills/`）にコピーする |
| `demote <name> [-y]` | ユーザースキルをアクティブなプロジェクトにコピーする |
| `dedup [--mode auto\|embedding\|tfidf] [--embedding-threshold f] [--tfidf-threshold f]` | ほぼ重複しているスキルを検出する |
| `suggest-promote [--save] [--min-uses n] [--min-success-rate f]` | 自動プロモーション基準を満たすスキルを一覧表示する |

### `veles tool {list,show,promote}`

| Subcommand | Purpose |
|---|---|
| `list` | このプロジェクトの `memory.db` にカタログ化されたツールを一覧表示する |
| `show <name>` | ツールのマニフェスト＋テレメトリを表示する |
| `promote <name> [-y]` | プロジェクトツールを `~/.veles/tools/`（プロジェクト横断）へ移動する |

### `veles module {list,show,add,remove}`

| Subcommand | Purpose |
|---|---|
| `list` | インストール済みのモジュールを一覧表示する |
| `show <name>` | モジュールのマニフェストを表示する |
| `add <source> [--name N] [-y]` | git URL またはローカルパスからモジュールをインストールする |
| `remove <name> [-y]` | インストール済みのモジュールを削除する |

### `veles browse {modules,skills} [query]`
キュレーション済みのレジストリを閲覧します。

| Flag | Default | Purpose |
|---|---|---|
| `query` (positional) | `""` | 部分文字列フィルタ |
| `--source <url>` | canonical | レジストリのソースを上書きする |
| `--json` | off | JSON を出力する |

---

## セッションとメモリ

### `veles sessions {list,show,delete,search}`

| Subcommand | Purpose |
|---|---|
| `list [--limit n]` | 最近のセッションを一覧表示する（デフォルト 20 件） |
| `show <session_id>` | セッションの全ターン履歴を表示する |
| `delete <session_id>` | セッションとそのターンを削除する |
| `search "<query>" [--limit n] [--role user\|assistant\|both\|all] [--since 7d]` | ターン内容に対する全文（FTS5）検索 |

---

## マルチプロジェクト

### `veles project {list,add,remove,switch}`

| Subcommand | Purpose |
|---|---|
| `list` | 登録済みのプロジェクトを、最近のものから順に一覧表示する |
| `add <path> [--slug S]` | 既存のプロジェクトディレクトリを登録する |
| `remove <slug>` | プロジェクトの登録を解除する（ファイルはそのまま） |
| `switch <slug>` | プロジェクトの絶対パスを表示する（`cd $(veles project switch <slug>)` のように使う） |

### `veles subproject {init,list,switch,remove,suggest}`

| Subcommand | Purpose |
|---|---|
| `init <subdir> [--name N] [--description D]` | サブプロジェクトを作成して登録する |
| `list` | アクティブなプロジェクトのサブプロジェクトを一覧表示する |
| `switch <slug>` | サブプロジェクトの絶対パスを表示する |
| `remove <slug>` | サブプロジェクトの登録を解除する |
| `suggest [--save] [--min-pages n] [--min-similarity f]` | テーマ的なクラスタを検出してサブプロジェクトを提案する |

---

## ルーティングとモデル

### `veles route {show,set,reset,refresh}`
タスクごとのアンサンブルルーティング — どの `provider:model` が各タスクタイプ
（`default`、`curator`、`compressor`、`insights`、`skills`、`advisor`、`vision`、
`embedding`）を処理するか。[タスク別ルーティング](../how-to/per-task-routing.md) を参照してください。

| Subcommand | Purpose |
|---|---|
| `show` | アクティブなプロジェクトについて解決済みのルーティングテーブルを表示する |
| `set <task> <provider:model>` | タスクを指定の仕様に固定する |
| `reset [task]` | 1 つのタスク（または全タスク）をデフォルトにリセットする |
| `refresh [--force]` | `AGENTS.md` から自然言語のルーティングヒントを再解析する |

### `veles models <provider>`
プロバイダのモデルを一覧表示します。クラウドプロバイダ（openrouter/openai/gemini）は
24 時間キャッシュされ、ローカルプロバイダは常にライブです。

| Flag | Default | Purpose |
|---|---|---|
| `provider` (positional) | — | [プロバイダ名](#provider-names) のいずれか |
| `--refresh` | off | ディスクキャッシュをバイパスする（クラウドのみ） |
| `--json` | off | `{provider, source, models}` を JSON として出力する |

---

## 長時間タスク

### `veles goal {list,show,start,checkpoint,pause,resume,done,cancel}`
予算とチェックポイントを伴う長期的な目標です。

| Subcommand | Purpose |
|---|---|
| `list [--status active\|paused\|completed\|blocked\|cancelled]` | 目標を一覧表示する |
| `show <id> [--json]` | 1 つの目標を表示する |
| `start "<objective>" [--scope S] [--done-when D] [--max-steps n] [--max-cost-usd f] [--max-wall-time-s n] [--forbid A]… [--approve A]…` | 目標を作成する |
| `checkpoint <id> "<note>" [--evidence U] [--cost-usd f] [--no-advance]` | 進捗を追記する |
| `pause <id>` / `resume <id>` | 一時停止／再開 |
| `done <id> [--evidence E]` / `cancel <id> [--reason R]` | 完了／キャンセル |

### `veles job {add,list,show,pause,resume,trigger,remove,history,tick}`
スケジュールされたエージェントジョブです。

| Subcommand | Purpose |
|---|---|
| `add --name N --schedule S --prompt P [--repeat n] [--context-from JOB_ID] [--deliver-to TARGET]` | ジョブを作成する（schedule = cron、`<N><s\|m\|h\|d>`、または ISO タイムスタンプ） |
| `list [--json]` / `show <id>` | ジョブを確認する |
| `pause <id>` / `resume <id>` / `trigger <id>` / `remove <id>` | ライフサイクル操作 |
| `history <id> [--limit n]` | 最近の実行 |
| `tick` | 実行期限が来たすべてのジョブを同期的に 1 回実行する（デーモン不要、エージェントループフラグを受け付ける） |

---

## セキュリティとアクセス制御

### `veles trust {list,set,revoke,clear}`
機微なツール（`run_shell`、`write_file`、`fetch_url` など）に対する永続的な付与です。
[セキュリティ](../how-to/security-and-permissions.md) を参照してください。

| Subcommand | Purpose |
|---|---|
| `list` | 付与を表示する（ユーザー＋プロジェクトスコープ） |
| `set <tool> [--scope project\|user]` | ツールを許可する |
| `revoke <tool> [--scope project\|user\|both]` | 付与を取り消す |
| `clear [--scope project\|user\|all]` | スコープ内の付与をすべて消去する |

### `veles autopilot {enable,disable,status}`
信頼ラダーのプロンプトが自動で許可される、時間制限付きのウィンドウです。

| Subcommand | Purpose |
|---|---|
| `enable --until <DUR>` | ウィンドウを開く（`+30m`、`+2h`、`+1d`、または ISO `2026-05-12T18:00:00Z`） |
| `disable` | ウィンドウを今すぐ閉じる |
| `status` | オートパイロットが有効かどうかを報告する |

### `veles secret {set,get,list,delete}`
OS キーチェーンに保存されるシークレット（API キー、ボットトークン）です。

| Subcommand | Purpose |
|---|---|
| `set <name> [value]` | 保存する（value を省略すると対話／標準入力） |
| `get <name> [--reveal] [--no-env-fallback]` | 参照する（デフォルトでは env にフォールバック） |
| `list` | どの正規シークレットが設定されているかを表示する |
| `delete <name>` | シークレットを削除する |

---

## デーモンとチャンネル

### `veles daemon [start|stop|status|list|restart|delete|session|token]`
HTTP+WS デーモンの実行／制御を行います。引数なしの `veles daemon` は
**デーモンピッカー** TUI（プロジェクト → デーモン → チャンネル）を開きます。
[デーモンとして実行する](../how-to/run-as-daemon.md) を参照してください。

| Subcommand | Purpose |
|---|---|
| `start [--host H] [--port P] [--foreground] [--name N]` | デーモンを起動する（デフォルトでデタッチ） |
| `stop [--name N]` / `status [--name N]` | 停止／確認 |
| `list` | 全プロジェクトのデーモンを一覧表示する |
| `restart [target] [--name N]` | 同じホスト／ポートで停止して再起動する |
| `delete <target> [-y]` | 停止してレジストリから削除する |
| `session create <name> [--host H] --port P [--model M] [--provider P] [--mode M]` | 名前付きデーモンセッションを宣言する |
| `session list [--all]` / `session delete <name>` | 名前付きセッションを管理する |
| `token add <name>` / `token list` / `token remove <name>` | ベアラートークンの CRUD |

`start` は共通エージェントループフラグも受け付けます。デーモンでは `--model` /
`--provider` がプロジェクト設定をデフォルトとし、デーモンの稼働中は固定されます。

### `veles channel {list,run,list-sessions,reset-session,add,remove}`
デーモンと通信する外部チャットゲートウェイ（Telegram など）です。
[Telegram に接続する](../how-to/connect-telegram.md) を参照してください。

| Subcommand | Purpose |
|---|---|
| `list` | 登録済みのチャンネルプラットフォームとセッション数を一覧表示する |
| `run --channel telegram [--bot-token T] [--daemon-url U] [--daemon-token T]` | ゲートウェイをフォアグラウンドで起動する |
| `list-sessions [--channel C]` | `chat_id → session_id` のマッピングを表示する |
| `reset-session <chat_id> [--channel C]` | マッピングを破棄する（次のメッセージから新規開始） |
| `add [--channel C] [--session S]` | チャンネルをデーモンに接続する（ウィザード、認証情報 → キーチェーン） |
| `remove <channel> [--session S]` | チャンネルのバインディングを削除する |

---

## MCP（外部ツールサーバー）

### `veles mcp {list,test}`
`[mcp.servers.*]` で設定された外部 MCP サーバーを確認します。
[外部 MCP サーバー](../how-to/external-mcp-servers.md) を参照してください。

| Subcommand | Purpose |
|---|---|
| `list [--connect-timeout f]` | 設定済みのサーバー、接続状態、ツール数を表示する |
| `test <server>` | 1 つのサーバーに接続してそのツールを一覧表示する |

---

## 共通エージェントループフラグ

`run`、`add`、`tui`、`curate`、`research`、`job tick`、`daemon start` が受け付けます。

| Flag | Default | Purpose |
|---|---|---|
| `--model <id>` | `anthropic/claude-sonnet-4.6` (tui: persisted) | モデル ID |
| `--provider <name>` | `openrouter` | プロバイダ（下記参照） |
| `--max-tokens-total <n>` | `100000` | 累積トークン予算。`0` で無効化 |
| `--max-iterations <n>` | `30` | 1 ターンあたりのツール呼び出しの最大反復回数 |
| `--stream` | off | レスポンスをトークン単位でストリーミングする |
| `--verbose` / `-v` | off | ターンごとの進捗を stderr に出力する |
| `--project-root <path>` | discover from cwd | 別の場所にあるプロジェクトを対象に操作する |

## プロバイダ名

`openrouter`（デフォルト） · `anthropic` · `openai` · `gemini` · `claude-cli` ·
`gemini-cli` · `ollama` · `llamacpp` · `openai-compat`

ローカルプロバイダ（`ollama`、`llamacpp`、`openai-compat`）は API キー不要です。
[プロバイダリファレンス](providers.md) と [プロバイダの設定](../how-to/configure-providers.md) を参照してください。

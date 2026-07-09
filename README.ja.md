# Veles

[![CI](https://github.com/denisotree/veles/actions/workflows/ci.yml/badge.svg)](https://github.com/denisotree/veles/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/veles-ai.svg)](https://pypi.org/project/veles-ai/)
[![License: Apache-2.0](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)
[![Python 3.13+](https://img.shields.io/badge/python-3.13%2B-blue.svg)](pyproject.toml)

<p align="center">
  <a href="README.md">English</a> ·
  <a href="README.zh-CN.md">简体中文</a> ·
  <a href="README.zh-TW.md">繁體中文</a> ·
  <b>日本語</b> ·
  <a href="README.ko.md">한국어</a> ·
  <a href="README.es.md">Español</a> ·
  <a href="README.fr.md">Français</a> ·
  <a href="README.it.md">Italiano</a> ·
  <a href="README.pt-BR.md">Português (BR)</a> ·
  <a href="README.pt-PT.md">Português (PT)</a> ·
  <a href="README.ru.md">Русский</a> ·
  <a href="README.ar.md">العربية</a> ·
  <a href="README.hi.md">हिन्दी</a> ·
  <a href="README.bn.md">বাংলা</a> ·
  <a href="README.vi.md">Tiếng Việt</a>
</p>

**セッションを重ねるごとに賢くなる、ミニマルな CLI エージェントフレームワーク。**

<p align="center">
  <img src="docs/assets/tui-hero.gif" alt="Veles REPL — 質問を投げると、プロジェクト自身のメモリに基づいた回答が返ってくる" width="800">
</p>

毎回ゼロから始まるチャットツールとは違い、Veles は**構造化されたプロジェクトメモリ**を保持します。インサイト、ルール、キュレーションされた知識がセッションを越えて蓄積され、使い込むほどエージェントが役に立つようになります。*コンテンツ*の整理方法は差し替え可能です。デフォルトは Karpathy 流の LLM ウィキ、フラットなノート、あるいはコードリポジトリ向けに構造をまったく持たせない形式も選べます。クリーンな設計を貫いています。神クラスのファイルなし、ベンダーロックインなし、クラウド同期なし。

```bash
uv tool install veles-ai          # installs the `veles` command
veles init && veles run "Summarize the project architecture."
veles        # interactive REPL (bare `veles` with no subcommand)
```

---

## なぜ Veles なのか?

**複利的に効くメモリ** — すべてのセッションは Curator によってプロジェクトごとのメモリ(インサイト、振る舞いのルール、セッションダイジェスト。`.veles/` 内)へと蒸留されます。エージェントは関連する事実や過去の判断を自動的に思い出すため、同じ文脈を何度も説明し直す必要がなくなります。メモリは*どの*コンテンツレイアウトの下でも機能します。

**差し替え可能なコンテンツレイアウト** — `veles init` はデフォルトで Karpathy 流の LLM ウィキを生成します。`--layout notes` ならフラットなノートディレクトリ、`--layout bare` なら構造をいっさい持たせません(コードリポジトリに最適)。カスタムレイアウトパックは `~/.veles/layouts/` に置く単一の TOML ファイルです。

**プロバイダー非依存のルーティング** — OpenRouter、Anthropic、OpenAI、Gemini、Ollama、llamacpp、あるいはあなたの `claude` / `gemini` CLI サブスクリプション。タスクの種類ごと(プランニング、圧縮、インサイト)に異なるモデルへルーティングできます。

**蓄積するスキル** — 再利用可能なプロンプトブロックがエージェントのツールになります。スキルをプロジェクトからユーザーグローバルへ昇格させれば、どこでも使えるようになります。組み込みの重複除去機能が、ニアデュプリケートなスキルがドリフトする前に検出します。

**ローカルファースト + サンドボックス** — テレメトリなし、クラウド同期なし。エージェントが見られるのはアクティブなプロジェクトディレクトリだけです。トラストラダー(信頼の段階)が機微なツール呼び出しのたびに確認を求めます。CI 向けには事前付与も可能です。

**モノリシックではなく、モジュラー** — 最小限のコア(メモリ、エージェントループ、プロバイダープロトコル、ツールレジストリ)。それ以外のすべて — TUI、デーモン、Telegram ゲートウェイ、ディープリサーチ、ジョブスケジューラー — はオプションのロード可能なモジュールです。

---

## クイックスタート

**要件:** Python 3.13+、macOS / Linux(Windows はベストエフォート)。まず [uv](https://docs.astral.sh/uv/) をインストールしてください。

```bash
# 1. Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# 2. Install veles (the package is published as `veles-ai`; the command is `veles`)
uv tool install veles-ai
# …or from source:
#   git clone https://github.com/denisotree/veles.git && cd veles && uv tool install .

# 3. Set an API key — OpenRouter is recommended (access to all models, one key)
export OPENROUTER_API_KEY=sk-or-v1-...

# 4. Create a project
mkdir my-project && cd my-project
veles init

# 5. Talk to the agent
veles run "Read AGENTS.md and describe this project."
```

代わりにインタラクティブな REPL を開く(素の `veles` でも同じことができます):

```bash
veles
```

初回起動時には、セットアップウィザードが、言語、LLM プロバイダー、API キー、デフォルトモデル、カラーテーマ、そして現在のディレクトリにプロジェクトを初期化するかどうかを順番に案内します。

---

## プロバイダー

| プロバイダー | 環境変数 | 備考 |
|---|---|---|
| **OpenRouter** *(推奨)* | `OPENROUTER_API_KEY` | Claude、GPT、Gemini、Llama — 1 つのキーで数百のモデル |
| Anthropic | `ANTHROPIC_API_KEY` | 直接 API |
| OpenAI | `OPENAI_API_KEY` | 直接 API |
| Gemini | `GEMINI_API_KEY` または `GOOGLE_API_KEY` | 直接 API |
| `claude` CLI | — | あなたの Claude サブスクリプションを利用。API キー不要 |
| `gemini` CLI | — | あなたの Gemini サブスクリプションを利用。API キー不要 |
| Ollama | — | ローカルモデル、`http://localhost:11434/v1` |
| llamacpp | — | ローカルモデル、`http://localhost:8080/v1` |
| openai-compat | `OPENAI_COMPAT_BASE_URL` | あらゆる OpenAI 互換エンドポイント |

実行ごとにオーバーライド:

```bash
veles run --provider anthropic --model anthropic/claude-opus-4-8 "..."
veles run --provider ollama --model llama3.2 "..."
```

API キーを環境変数の代わりに OS のキーチェーンに保存する:

```bash
veles secret set OPENROUTER_API_KEY    # prompts for value, stores in keychain
```

---

## 基本ワークフロー

### コンテンツレイアウトを選ぶ

```bash
veles init                  # default: Karpathy-style LLM wiki (sources/ + wiki/)
veles init --layout notes   # a single flat notes/ directory
veles init --layout bare    # no content scaffold — code repos, free-form work
```

エージェント自身のメモリ(インサイト、ルール、セッションダイジェスト。`.veles/` 内)は、どのレイアウトの下でも同じように機能します。カスタムパックは `~/.veles/layouts/<name>/` に置く 1 つの `layout.toml` です。

### ナレッジベースを構築する(llm-wiki レイアウト)

```bash
veles add paper.pdf                   # read a source → write a wiki page
veles add https://example.com/post    # web pages, PDFs, plain text

veles run "What do we know about the authentication design?"
veles curate                          # explicit session → memory consolidation
```

<p align="center">
  <img src="docs/assets/kb-ingest.gif" alt="Veles ナレッジベース — ソースをウィキページに取り込み、質問するとそれを引用した回答が返ってくる" width="800">
</p>

Curator はセッション後に自動で実行されます。インサイト抽出は「always prefer X(常に X を優先する)」や「never do Y(決して Y をしない)」といったフレーズを捉え、永続的なプロジェクトインサイトとして書き込みます。

### ディープリサーチ

```bash
veles research "What are the trade-offs between SQLite and PostgreSQL for this use case?"
```

質問を並列のサブクエスチョンに分解し、それぞれを探索したうえで、構造化されたレポートに統合します。

### 長時間実行のゴール

```bash
veles goal start "Migrate auth module to the new provider" --max-cost-usd 2.00
veles goal list
veles goal checkpoint <id> "Completed step 1: identified all call sites"
```

### スケジュールジョブ

```bash
veles job add --name "weekly-review" --schedule "0 9 * * 1" --prompt "Generate a weekly progress summary"
veles job list
```

---

## モデルルーティング(アンサンブル)

タスクの種類ごとに異なるモデルへルーティングします。一度設定すれば、あとは気にする必要はありません。

**CLI 経由:**
```bash
veles route show                                          # current routing table
veles route set compressor anthropic/claude-haiku-4-5    # typed override
veles route reset compressor                             # back to default
```

**`AGENTS.md` 内の自然言語経由:**
```markdown
## Routing
Use Opus for planning and architecture decisions.
Haiku is fine for compression and insight extraction.
```

```bash
veles route refresh    # parse the NL hints; typed overrides always win
```

---

## スキルとモジュール

**スキル**は再利用可能なプロンプトブロック(`SKILL.md`)で、自動的にエージェントのツールになります。

```bash
veles skill add https://github.com/org/skill-repo    # install from git
veles skill add ./local-skill-dir                    # or from local path
veles skill list                                     # list with telemetry
veles skill promote my-skill                         # copy to ~/.veles/skills (global)
veles skill dedup                                    # find near-duplicates
veles skill suggest-promote --save                   # propose promotions based on usage
```

**モジュール**は Python プラグインで、エージェントのライフサイクル(`pre_turn`、`post_turn`、`pre_tool_call`、`post_tool_call`)にフックしたり、ツールのディスパッチを拒否(veto)したりできます。

```bash
veles module add https://github.com/org/module-repo
veles module list
```

---

## インタラクティブセッション(REPL)

```bash
veles                        # new session (bare `veles` launches the interactive REPL)
veles --resume <id>      # continue a session
```

<p align="center">
  <img src="docs/assets/tui-tour.gif" alt="Veles REPL — スラッシュインスペクター(/status、/context)、モード切り替え、コマンドパレット" width="800">
</p>

スラッシュコマンドがすべてをライブで表示します — `/status`、`/tokens`、`/context`、`/mode`、`/help` — そして `Shift+Tab` でモード(auto / planning / writing / goal)を順に切り替えられます。

| キー | 動作 |
|---|---|
| `Enter` | メッセージを送信 |
| `Shift+Enter` | コンポーザー内で改行 |
| `Ctrl+I` | ツールアクティビティインスペクターの切り替え |
| `Ctrl+R` | セッションピッカーのオーバーレイ |
| `Ctrl+G` | 現在の下書きを `$EDITOR` で開く |
| `Tab` | スラッシュコマンドの自動補完 |
| `Ctrl+D` | 終了 |

スラッシュコマンド: `/help` · `/model` · `/mode` · `/status` · `/tokens` · `/context` · `/wiki` · `/save <slug>` · `/history` · `/insights` · `/rules` · `/daemon` など。

---

## デーモン + Telegram

Veles を HTTP/WebSocket API を備えた永続的なデーモンとして実行します。まっさらなプロジェクトディレクトリで `veles daemon start` を実行すると、セットアップを案内してくれます — プロジェクトの初期化、デーモンの有効化、そして**チャンネルの接続**です。まずチャンネルの*種類*を選び(現時点で対応しているプラットフォームは Telegram のみですが、ピッカーは新しいチャンネルが登録される継ぎ目です)、次にそのチャンネルのフィールド(ボットトークン、ホワイトリスト)を入力します。先に TUI を開く必要はありません。

<p align="center">
  <img src="docs/assets/daemon-setup.gif" alt="veles daemon start — デーモンを起動し Telegram チャンネルを接続するウィザード(まずチャンネルの種類、次にトークンとホワイトリスト)" width="800">
</p>

```bash
veles daemon start                        # wizard (fresh dir) → starts on 127.0.0.1:8765
veles daemon status                       # is it running?
veles daemon list                         # daemons across all projects
```

素の `veles daemon` はライブのコントロールパネルを開きます — プロジェクト → デーモン → チャンネルのツリーです。すべてのプロジェクトを横断して、デーモンの起動・停止・再起動・削除や、チャンネルの追加・削除(同じく「まずチャンネルの種類から」というフロー。キーは `c`)を、すべてキーボードから行えます:

<p align="center">
  <img src="docs/assets/daemon-panel.gif" alt="veles daemon — コントロールパネル TUI: プロジェクト → デーモン → チャンネルのツリーで、起動/停止/再起動/削除とインラインのチャンネル管理" width="800">
</p>

同じチャンネルウィザードは、すでに稼働中のプロジェクトに対してスタンドアロン(`veles channel add`)でも利用できます。

API エンドポイント: プロンプトを送信する `POST /v1/runs`、レスポンスをストリーミングする `WS /v1/runs/{id}/events`、セッションを一覧する `GET /v1/sessions`。`GET /v1/health` を除くすべてで `Authorization: Bearer <token>` が必要です(トークンは `veles daemon token add <name>` で発行します)。

Telegram ユーザーごとに永続的なセッションが割り当てられます。マッピングの管理には `veles channel list-sessions` / `reset-session` を使ってください。

---

## マルチプロジェクト

```bash
veles project list                       # registered projects
veles project switch <slug>              # print the absolute path
cd $(veles project switch <slug>)        # jump to a project

veles subproject init frontend           # create a child project
veles subproject suggest --save          # agent-detected topic clusters → proposals
```

---

## トラストと安全性

機微なツール呼び出し(シェル実行、ファイル書き込み、URL の取得)はそのたびに確認を求めます:

```
Tool 'run_shell' wants to execute. Allow?
  [1] Once  [2] Always for this project  [3] Always everywhere  [4] Refuse
```

CI や長時間の自律実行のために事前付与する:

```bash
veles trust set run_shell --scope project   # pre-grant for this project
veles autopilot enable --until +2h          # temporary trust bypass (audit-logged)
veles autopilot disable
```

エージェントが見られるのはアクティブなプロジェクトディレクトリだけです — 他のプロジェクト、シンボリックリンクによる脱出、`..` によるトラバーサルはブロックされます。

---

## エクスポート / インポート

```bash
veles export full ./backup.tar.gz        # full backup: memory, sessions, telemetry
veles export template ./template.tar.gz  # sanitised template (no sources/sessions/PII)
veles import ./backup.tar.gz --into ./new-dir
```

---

## CLI リファレンス

| コマンド | 目的 |
|---|---|
| `veles init [name]` | 新しいプロジェクトを作成 |
| `veles run "<prompt>"` | シングルターンのエージェント実行 |
| `veles` | インタラクティブな REPL |
| `veles add <file\|url>` | ソースを取り込み → トピック別のウィキページ群へ |
| `veles organize` | アクティブなレイアウトに沿ってプロジェクトの内容を再編成（提案してから適用）|
| `veles research "<question>"` | 多角的なディープリサーチ |
| `veles curate` | セッションをウィキへ統合 |
| `veles sessions {list,show,delete,search}` | セッション管理 |
| `veles skill {list,show,add,remove,promote,demote,dedup,suggest-promote}` | スキル管理 |
| `veles tool {list,show,promote,approve}` | ツール管理（`approve` は自作ツールを承認）|
| `veles module {list,add,remove}` | プラグイン管理 |
| `veles browse {modules,skills}` | 厳選されたモジュール／スキルのレジストリを検索 |
| `veles route {show,set,reset,refresh}` | モデルルーティング |
| `veles schema {validate,edit}` | AGENTS.md の検証／編集 |
| `veles self-doc` | プロジェクトの自己ドキュメントを生成 |
| `veles layout {sync}` | レイアウトパックのメンテナンス |
| `veles goal {list,show,start,checkpoint,pause,resume,done,cancel}` | 長期ホライズンのゴール |
| `veles job {list,add,show,pause,resume,trigger,remove,history}` | スケジュールジョブ |
| `veles dream` | バックグラウンドのメモリ統合サイクル |
| `veles project {list,add,remove,switch}` | マルチプロジェクトのレジストリ |
| `veles subproject {init,list,switch,remove,suggest}` | 子プロジェクト |
| `veles trust {list,set,revoke,clear}` | トラストの付与 |
| `veles autopilot {enable,disable,status}` | 一時的なトラストバイパス |
| `veles secret {set,get,list,delete}` | OS キーチェーンのシークレット |
| `veles daemon {start,stop,status,list,restart,delete,session,token}` | HTTP/WS デーモン |
| `veles channel {list,run,list-sessions,reset-session,add,remove}` | 外部チャンネルゲートウェイ |
| `veles mcp {list,test}` | 外部 MCP サーバー |
| `veles models <provider>` | プロバイダーのモデルを一覧 |
| `veles doctor` | ヘルスチェック |
| `veles export / import` | プロジェクトのバックアップと移行 |

すべてのコマンドに `--help` があります。

---

## ドキュメント

完全なドキュメント — Diátaxis に沿って整理(チュートリアル · ハウツーガイド · リファレンス · 解説):

- **日本語:** [`docs/ja/index.md`](docs/ja/index.md)

他の言語: 各ドキュメントページ上部の 🌐 言語切り替えをご利用ください。

---

## コントリビューション

コントリビューションは大歓迎です — Veles は**拡張されることを前提に作られています**。コアは小さく保たれており(エージェントループ + プロジェクトメモリ + プロバイダープロトコル)、それ以外のほぼすべては差し替え可能な拡張ポイントです。そのため、機能を追加してもコアに手を入れることはめったにありません:

- **プロバイダーアダプター**(`src/veles/adapters/`)— 新しいモデルバックエンドを接続。
- **スキル** — `extends:` 継承を持つ再利用可能なプロンプトブロックとツール。プロジェクトからユーザーグローバルへ昇格可能。
- **ツール** — エージェントが書いて再利用する型付き Python。`<project>/.veles/tools/` 配下。
- **レイアウトパック** — `~/.veles/layouts/<name>/` に置く 1 つの `layout.toml` がコンテンツレイアウト全体を定義。
- **モジュールフック** — `pre_turn` / `post_turn` フックによる可観測性、ロギング、ポリシー(`src/veles/core/modules.py`)。
- **チャンネルと MCP サーバー** — 新しいゲートウェイと外部ツールソース。
- **ロケール** — `src/veles/locales/` 内の翻訳。

```bash
git clone https://github.com/denisotree/veles.git && cd veles
uv sync                              # runtime + dev dependencies
uv run pytest                        # the full suite (3200+ tests, no network)
uv run ruff check src tests && uv run mypy
```

コードベースは意図的に分解されています — 単一責任、神クラスのファイルなし。PR を出す前に、規約については [`CONTRIBUTING.md`](CONTRIBUTING.md) を、そして [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md) を読んでください。最初のコントリビューションに適しているのは、プロバイダーアダプター、ワークフロースキル、モジュールフック、ロケールファイルです。

---

## ライセンス

特許許諾付きの Apache 2.0 — [`LICENSE`](LICENSE) と [`NOTICE`](NOTICE) を参照してください。

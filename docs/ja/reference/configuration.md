# 設定リファレンス

> 🌐 **言語:** [English](../../en/reference/configuration.md) · [简体中文](../../zh-CN/reference/configuration.md) · [繁體中文](../../zh-TW/reference/configuration.md) · **日本語** · [한국어](../../ko/reference/configuration.md) · [Español](../../es/reference/configuration.md) · [Français](../../fr/reference/configuration.md) · [Italiano](../../it/reference/configuration.md) · [Português (BR)](../../pt-BR/reference/configuration.md) · [Português (PT)](../../pt-PT/reference/configuration.md) · [Русский](../../ru/reference/configuration.md) · [العربية](../../ar/reference/configuration.md) · [हिन्दी](../../hi/reference/configuration.md) · [বাংলা](../../bn/reference/configuration.md) · [Tiếng Việt](../../vi/reference/configuration.md)

Veles は 2 つの TOML ファイルと一連の状態ディレクトリで設定されます。シークレット（API キー、ボットトークン）は**決して**これらのファイルに書き込まれません。OS キーチェーンまたは環境変数に保存されます（[環境変数](environment-variables.md)を参照）。

## 状態の保存場所

| パス | スコープ | 内容 |
|---|---|---|
| `~/.veles/` | ユーザーグローバル | `config.toml`、trust の付与、プロジェクト横断のスキル/ツール、モデルキャッシュ、ロケール、レジストリ |
| `<project>/.veles/` | プロジェクトローカル | `project.toml`、`config.toml`、`memory.db`、プロジェクトのスキル/ツール、プラン、実行時アーティファクト |
| `<project>/AGENTS.md` | プロジェクト | エージェントに注入されるコンテキストファイル（`CLAUDE.md` / `GEMINI.md` にシンボリックリンクされる） |
| `<project>/wiki/`, `sources/` | プロジェクト | ユーザーコンテンツ（デフォルトの LLM-Wiki レイアウト） |

`VELES_USER_HOME` は `~` をリダイレクトします（ユーザー状態は `<override>/.veles/` に置かれます）。ツリー全体については[プロジェクトレイアウト](project-layout.md)を参照してください。

---

## ユーザー設定 — `~/.veles/config.toml`

初回ウィザードによって書き込まれます。手動で編集しても安全です。

```toml
[user]
language = "en"                  # "en" | "ru" — UI string locale
default_provider = "openrouter"  # default provider for new projects
default_model = "anthropic/claude-sonnet-4.6"
first_project_name = "myorg"     # recorded by the wizard
tui_theme = "everforest"         # everforest | dracula | gruvbox | tokyo-night | catppuccin

[permissions]                    # optional per-tool policy
fetch_url  = "approval_required" # allow | approval_required | always_confirm
write_file = "always_confirm"

[routing.tasks]                  # optional user-scope routing (see below)
compressor = "openrouter:anthropic/claude-haiku-4.5"

[mcp.servers.my-server]          # optional user-scope MCP servers
transport = "stdio"
command = "python"               # executable only — arguments go in `args`
args = ["-m", "my_mcp_server"]
```

| キー | 型 | 目的 |
|---|---|---|
| `[user] language` | `"en"` \| `"ru"` | UI 文字列のロケール（`VELES_LOCALE` で上書き可能） |
| `[user] default_provider` | string | プロバイダーが指定されないときに使われるプロバイダー |
| `[user] default_model` | string | モデルが指定されないときに使われるモデル |
| `[user] tui_theme` | string | デフォルトの TUI カラーテーマ |
| `[permissions] <tool>` | policy | ツールごとのパーミッションポリシー（[trust とサンドボックス](../explanation/trust-and-sandbox.md)を参照） |

---

## プロジェクト設定 — `<project>/.veles/config.toml`

```toml
[engine]
provider = "openrouter"                               # provider name for the main agent + routing base
model = "anthropic/claude-sonnet-4.6"                # model id (omit to require --model or the user default_model)

[routing.tasks]                  # per-task overrides (highest priority below explicit flags)
default    = "openrouter:anthropic/claude-sonnet-4.6"
compressor = "openrouter:anthropic/claude-haiku-4.5"
insights   = "openrouter:anthropic/claude-haiku-4.5"
advisor    = "openrouter:anthropic/claude-opus-4.8"
vision     = "openai:gpt-4o"
embedding  = "openai:text-embedding-3-small"

[daemon]                         # the unnamed/"default" daemon
enabled = true
host = "127.0.0.1"
port = 8765
autostart = false

[daemon.api]                     # a named daemon session ("api")
provider = "anthropic"
model = "claude-opus-4.8"
host = "127.0.0.1"
port = 8801
mode = "auto"

[channels.telegram]              # global channels (served by the unnamed daemon)
enabled = true
whitelist = ["@alice", "123456789"]

[daemon.api.channels.telegram]   # channels bound to a named daemon session
enabled = true
whitelist = ["@bob"]

[mcp.servers.github]             # external MCP servers (project scope)
transport = "stdio"             # stdio | http | sse
command = "npx"                  # executable only — arguments go in `args`
args = ["-y", "@modelcontextprotocol/server-github"]
env = { GITHUB_TOKEN = "${GITHUB_TOKEN}" }   # ${VAR} interpolates from the environment
```

### セクション

| セクション | 目的 |
|---|---|
| `[engine]` | メインエージェントとルーティングカスケードのベースとなるプロバイダー（`provider` = プロバイダー名）+ モデル（`model` = モデル ID） |
| `[routing.tasks]` | タスクごとの `provider:model` の上書き — [タスク別ルーティング](../how-to/per-task-routing.md)を参照 |
| `[permissions]` | ツールごとのパーミッションポリシー（プロジェクトスコープ） |
| `[daemon]` | 無名/「デフォルト」デーモンのバインド + 自動起動 |
| `[daemon.<name>]` | 名前付きデーモンセッション（独自の model/provider/host/port/mode） |
| `[channels.<type>]` | 無名デーモンが提供するチャンネル（例: `telegram`） |
| `[daemon.<name>.channels.<type>]` | 名前付きデーモンセッションにバインドされたチャンネル |
| `[mcp.servers.<name>]` | 外部 MCP サーバー（ツールソース） |

`[routing.tasks]` のタスクタイプ: `default`、`curator`、`compressor`、`insights`、`skills`、`advisor`、`vision`、`embedding`。

> `AGENTS.md` 内の自然言語によるルーティングヒントは、自動生成される `routing.nl.toml` に解析されます。明示的な `[routing.tasks]` エントリが常に優先されます。再解析するには `veles route refresh` を実行してください。[タスク別ルーティング](../how-to/per-task-routing.md)を参照。

### バックエンドの固定、およびリクエストボディのその他のキー

`[engine.request.<provider>]` はそのプロバイダーのリクエストボディに**そのまま**
転送されます。Veles は上流のスキーマをモデル化しないため、プロバイダーが受け付ける
設定は Veles が対応するのを待たずにそのまま使えます。

```toml
[engine.request.openrouter.provider]
order = ["GMICloud"]
allow_fallbacks = false

[engine.request.openrouter.reasoning]
enabled = false
```

セクションのキーは**プロバイダー名**（`openrouter`、`anthropic`、`openai`、
`gemini`、`ollama`、`llamacpp`、`openai-compat`）です。こうすることで、一つの
プロジェクト設定がバックエンドの切り替えを乗り越えられます。OpenRouter の
`provider` ブロックを llama.cpp に送れば 400 になるので、各バックエンドは自分の
サブセクションだけを読みます。セクションを宣言しなければ、リクエストは以前と
バイト単位で同一です。

**必要になる場面：再現可能な計測。** OpenRouter のようなリレーは一つのモデルを
量子化の異なる多数のバックエンドに振り分けるため、同じ入力の 2 回の実行が入力とは
無関係な理由で食い違うことがあります。`session_id` によるスティッキールーティングは
一つの会話を一つのバックエンドに留めますが、それが**どれ**かは教えてくれません。

固定は `quantizations` ではなく `order` で行ってください。2026-09-18 時点で
`z-ai/glm-5.3-flash` には 29 のエンドポイントがあります：`fp8` が 16、`fp4` が 3、
`nvfp4` が 1、**量子化をまったく申告しないものが 9**、`bf16` はゼロです。つまり
`quantizations = ["fp8"]` でも候補は 16 残り、コンテキスト長は 262144 から
1310720 トークンまでばらつきます。一方、要素が一つだけの `order` と
`allow_fallbacks = false` を併用すればバックエンドは一意に決まります。モデルの
エンドポイント一覧：

```bash
curl -s https://openrouter.ai/api/v1/models/<author>/<slug>/endpoints \
  -H "Authorization: Bearer $OPENROUTER_API_KEY" | jq '.data.endpoints[]
  | {provider_name, quantization, context_length}'
```

固定は計測用プロジェクトにだけ残してください。本番にはスティッキールーティングが
適しており、可用性とフォールバックが保たれます。

**固定が維持されたかの確認。** モデル呼び出しごとに、意図と結果の両方が
`.veles/traces.jsonl` に記録されます。`request_extra` が送った内容、
`upstream_provider` が実際に応答したバックエンドです。1 行で分かります：

```bash
jq -r 'select(.session_id=="<sid>") | .upstream_provider' .veles/traces.jsonl | sort -u
```

2 行以上出れば、その実行はバックエンドを混ぜています。同じレコードには
`reasoning_tokens`（予算のうち推論に使われた分）と `est_cost_usd`（上流が報告する
実課金額）も含まれます。

**エラーは意図的に大きな音を立てます。** プロバイダー名の綴り間違いや、セクション
パスの誤り（`[engine.reqest.…]`）は `ConfigError` で実行を中断し、ファイル名と既知の
プロバイダーを示します。配線に届かなかった固定は、それを書いた目的である計測を
黙って無効にしてしまうからです。プロバイダーのサブセクション*内部*のキーは Veles は
検証しません。上流が検証するからです：OpenRouter は未知のキーに
`400 provider: Unrecognized key: "quantization"`、該当のない値に
`404 No endpoints found …` を返します。

### 会話記録の保持期間

```toml
[memory]
turn_retention_days = 90   # 0 は永久保持
```

生の会話ターンはこの日数を過ぎると削除されますが、そこから抽出された**インサイト**
とルールは永久に保持されます。会話記録は原材料であり、インサイトはそれを読んだ目的
です。こうして `memory.db` は無制限に増え続けるのをやめる一方、エージェントは学んだ
ことを保ち続けます。

会話記録が削除されるには**両方**の条件が必要です。保持期間より古いこと、**かつ**
キュレーターがそのセッションを既に処理済みであること。キュレーターがまだ到達して
いないセッションは、どれほど古くても削除されません。さもなければ、何も学ばないうちに
記録を破棄してしまいます。

目に見える代償：`veles sessions search` は保持期間内のテキストしか見つけられません。
`veles sessions list` は古い実行も表示し続けます。セッション行（id・タイトル・
タイムスタンプ）は残り、消えるのはメッセージ本文だけだからです。削除は
`veles dream` の中で、インサイト抽出の後に実行されます。

### ログのローテーション

`traces.jsonl` と `events.jsonl` は 50 MB で `<名前>.<unix_ts>` にローテーションし、
最新の **10** 世代を保持します。それより古いものは次のローテーション時に削除されます。
以前は無期限に保持されていました。

通常の利用量では設定は不要です。トレース 1 レコードあたり約 530 バイト、エージェント
1 ターンあたり約 1.1 KB のイベントなので、最初のローテーションまでには数年かかります。
この設定が存在するのは、方針のない無制限の増加が、そのマシンを引き継ぐ人が発見する
羽目になるリークだからです。

### 画像

チャンネルに送られた写真は、ターンが始まる前に説明が生成されます。使われるのは
`[routing.tasks].vision` が指すモデルで、明示的なルートがなければ `[engine]` の
モデルです。したがってマルチモーダルなエンジンなら設定は一切不要です。

`[vision] mode` がパイプラインを選びます：

- `model`（既定）— ビジョンモデルが画像を説明します。
- `ocr` — Tesseract のみ。ローカル・無料・LLM 呼び出しなし。テキストのスキャンに
  適します。
- `ocr+model` — まず逐語的なテキスト、続いてモデルによる説明。
- `off` — 何も読み取りません。ファイルは保存され、エージェントが必要と判断すれば
  自分で `image_describe` / `image_ocr` を呼べます。

エンジンがテキスト専用の場合は `[vision] model` を設定してください。ビジョン対応の
プロバイダーなら何でも使えます。ローカルサーバーも含みます：`ollama:llava`、
`llamacpp:…`、`openai-compat:…`。

### `project.toml`

`<project>/.veles/project.toml` には不変のプロジェクトメタデータ（`name`、`created_at`、`schema_version`、`layout`）が格納されます。通常、手動で編集することはありません。

---

## AGENTS.md

プロジェクトルートにあるプロジェクトのコンテキストファイルです。起動時にエージェントのシステムプロンプトに注入され、`CLAUDE.md` と `GEMINI.md` にシンボリックリンクされるため、そのディレクトリで起動した `claude` や `gemini` の CLI も同じコンテキストを取得します。

小さく保ってください。補助的な `.md` ファイル（例: `wiki/INDEX.md`）はオンデマンドで読み込まれます。必須セクションは `veles schema validate` で検証できます。[レイアウトパックと LLM-Wiki](../explanation/layout-packs-and-llm-wiki.md)を参照してください。

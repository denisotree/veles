# 設定リファレンス

> 🌐 **言語:** [English](../../en/reference/configuration.md) · **日本語** · [Русский](../../ru/reference/configuration.md)

Veles は 2 つの TOML ファイルと一連の状態ディレクトリで設定されます。シークレット
（API キー、ボットトークン）は **決して** これらのファイルに書き込まれません。OS
キーチェーンまたは環境変数に保存されます（[環境変数](environment-variables.md) を参照）。

## 状態の保存場所

| Path | Scope | Contents |
|---|---|---|
| `~/.veles/` | User-global | `config.toml`、trust の付与、プロジェクト横断のスキル／ツール、モデルキャッシュ、ロケール、レジストリ |
| `<project>/.veles/` | Project-local | `project.toml`、`config.toml`、`memory.db`、プロジェクトのスキル／ツール、プラン、実行時アーティファクト |
| `<project>/AGENTS.md` | Project | エージェントに注入されるコンテキストファイル（`CLAUDE.md` / `GEMINI.md` にシンボリックリンクされる） |
| `<project>/wiki/`, `sources/` | Project | ユーザーコンテンツ（デフォルトの LLM-Wiki レイアウト） |

`VELES_USER_HOME` は `~` をリダイレクトします（ユーザー状態は `<override>/.veles/` に置かれます）。
ツリー全体については [プロジェクトレイアウト](project-layout.md) を参照してください。

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
fetch_url  = "approval_required" # approval_required | always_confirm | always_allow
write_file = "always_confirm"

[routing.tasks]                  # optional user-scope routing (see below)
compressor = "openrouter:anthropic/claude-haiku-4.5"

[mcp.servers.my-server]          # optional user-scope MCP servers
transport = "stdio"
command = "python"               # executable only — arguments go in `args`
args = ["-m", "my_mcp_server"]
```

| Key | Type | Purpose |
|---|---|---|
| `[user] language` | `"en"` \| `"ru"` | UI 文字列のロケール（`VELES_LOCALE` で上書き可能） |
| `[user] default_provider` | string | プロバイダが指定されないときに使われるプロバイダ |
| `[user] default_model` | string | モデルが指定されないときに使われるモデル |
| `[user] tui_theme` | string | デフォルトの TUI カラーテーマ |
| `[permissions] <tool>` | policy | ツールごとのパーミッションポリシー（[trust とサンドボックス](../explanation/trust-and-sandbox.md) を参照） |

---

## プロジェクト設定 — `<project>/.veles/config.toml`

```toml
[provider]
default = "openrouter:anthropic/claude-sonnet-4.6"   # base for the main agent + routing

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

| Section | Purpose |
|---|---|
| `[provider]` | メインエージェントとルーティングカスケードのベースとなるプロバイダ／モデル |
| `[routing.tasks]` | タスクごとの `provider:model` の上書き — [タスク別ルーティング](../how-to/per-task-routing.md) を参照 |
| `[permissions]` | ツールごとのパーミッションポリシー（プロジェクトスコープ） |
| `[daemon]` | 無名／「デフォルト」デーモンのバインド＋自動起動 |
| `[daemon.<name>]` | 名前付きデーモンセッション（独自の model/provider/host/port/mode） |
| `[channels.<type>]` | 無名デーモンが提供するチャンネル（例: `telegram`） |
| `[daemon.<name>.channels.<type>]` | 名前付きデーモンセッションにバインドされたチャンネル |
| `[mcp.servers.<name>]` | 外部 MCP サーバー（ツールソース） |

`[routing.tasks]` のタスクタイプ: `default`、`curator`、`compressor`、`insights`、
`skills`、`advisor`、`vision`、`embedding`。

> `AGENTS.md` 内の自然言語によるルーティングヒントは、自動生成される
> `routing.nl.toml` に解析されます。明示的な `[routing.tasks]` エントリが常に優先されます。
> 再解析するには `veles route refresh` を実行してください。[タスク別ルーティング](../how-to/per-task-routing.md) を参照。

### `project.toml`

`<project>/.veles/project.toml` には不変のプロジェクトメタデータ（`name`、
`created_at`、`schema_version`、`layout`）が格納されます。通常、手動で編集することはありません。

---

## AGENTS.md

プロジェクトルートにあるプロジェクトのコンテキストファイルです。起動時にエージェントの
システムプロンプトに注入され、`CLAUDE.md` と `GEMINI.md` にシンボリックリンクされるため、
そのディレクトリで起動した `claude` や `gemini` の CLI も同じコンテキストを取得します。

小さく保ってください。補助的な `.md` ファイル（例: `wiki/INDEX.md`）はオンデマンドで読み込まれます。
必須セクションは `veles schema validate` で検証できます。
[レイアウトパックと LLM-Wiki](../explanation/layout-packs-and-llm-wiki.md) を参照してください。

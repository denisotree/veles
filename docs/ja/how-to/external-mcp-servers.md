# 外部 MCP サーバーを接続する方法

> 🌐 **言語:** [English](../../en/how-to/external-mcp-servers.md) · [简体中文](../../zh-CN/how-to/external-mcp-servers.md) · [繁體中文](../../zh-TW/how-to/external-mcp-servers.md) · **日本語** · [한국어](../../ko/how-to/external-mcp-servers.md) · [Español](../../es/how-to/external-mcp-servers.md) · [Français](../../fr/how-to/external-mcp-servers.md) · [Italiano](../../it/how-to/external-mcp-servers.md) · [Português (BR)](../../pt-BR/how-to/external-mcp-servers.md) · [Português (PT)](../../pt-PT/how-to/external-mcp-servers.md) · [Русский](../../ru/how-to/external-mcp-servers.md) · [العربية](../../ar/how-to/external-mcp-servers.md) · [हिन्दी](../../hi/how-to/external-mcp-servers.md) · [বাংলা](../../bn/how-to/external-mcp-servers.md) · [Tiếng Việt](../../vi/how-to/external-mcp-servers.md)

Veles は [MCP](https://modelcontextprotocol.io/) **クライアント** です: 外部の MCP サーバーに
接続し、それらのツールを組み込みであるかのようにエージェントへ公開できます
（GitHub、ライブラリドキュメント、ウェブ検索、独自のサービスなど）。

## サーバーを設定する

`<project>/.veles/config.toml`（または、ユーザーグローバルな `~/.veles/config.toml`）に
`[mcp.servers.<name>]` ブロックを追加します。`<name>` は
`[A-Za-z0-9][A-Za-z0-9_-]{0,31}` に一致する必要があります — これは各ツール名の一部になります。
サポートされるトランスポートは3種類です: `stdio`（デフォルト）、`http`、`sse`。

| キー | トランスポート | デフォルト | 用途 |
|---|---|---|---|
| `transport` | — | `"stdio"` | `stdio` \| `http` \| `sse` |
| `command` | stdio（必須） | — | 起動する実行ファイル — **プログラム本体のみ、引数は含めない** |
| `args` | stdio | `[]` | 引数のリスト、1要素につき1トークン |
| `env` | stdio | `{}` | サブプロセス用の追加環境変数（継承された環境にマージされる） |
| `url` | http/sse（必須） | — | サーバーのエンドポイント |
| `timeout_s` | — | `120` | 単一のツール呼び出しに対する制限時間 |
| `connect_timeout_s` | — | `30` | 初回接続に対する制限時間 |
| `enabled` | — | `true` | エントリを残したまま接続をスキップするには `false` を設定 |

`command`、`args`、`env`、`url` 内の文字列値は、環境から `${VAR}` を展開します
（未設定の変数は警告とともに空文字列になります） — シークレットはファイルに書かないでください。

> **`command` と `args` の違い。** Veles はプログラムを直接実行する（シェルを介さない）ため、
> 実行ファイルとその引数は **別々の** フィールドです。
> `command = "npx"`, `args = ["-y", "pkg"]` と書きます — `command = "npx -y pkg"` では **ありません**。

### stdio（ローカルサブプロセス）

```toml
[mcp.servers.github]
transport = "stdio"
command = "npx"
args = ["-y", "@modelcontextprotocol/server-github"]
env = { GITHUB_TOKEN = "${GITHUB_TOKEN}" }
```

自分で稼働させるサーバーも同じように動作します — `command`/`args` をそこへ向けます:

```toml
[mcp.servers.mytools]
transport = "stdio"
command = "python"
args = ["-m", "my_mcp_server"]
```

### API キーが必要なサーバー（context7）

[Context7](https://context7.com) は最新のライブラリドキュメントを提供します。`${VAR}` で
キーをファイルの外に保つよう、キーを引数として渡します:

```toml
[mcp.servers.context7]
transport = "stdio"
command = "npx"
args = ["-y", "@upstash/context7-mcp", "--api-key", "${CONTEXT7_API_KEY}"]
```

```bash
export CONTEXT7_API_KEY=...   # then start veles
```

### http / sse（リモート）

```toml
[mcp.servers.search]
transport = "http"            # streamable HTTP; use "sse" for an SSE endpoint
url = "https://mcp.example.com/mcp"
```

> **カスタムヘッダーは（まだ）非対応。** `http`/`sse` トランスポートは `url` のみを送信します —
> Veles は `Authorization` ヘッダーを付加できません。キーを必要とするリモートサーバーには、
> キーを `args`/`env` に入れた `stdio`（例: `npx`）版か、URL でキーを受け付けるエンドポイントを
> 推奨します。

## 特定のツールを隠す

`[mcp] disabled_tools` を設定します — 各サーバーをスキップするツール名にマッピングするテーブルです:

```toml
[mcp]
disabled_tools = { github = ["delete_repository"], search = ["raw_query"] }
```

## 確認とテスト

```bash
veles mcp list              # 設定済みの全サーバー: トランスポート、ステータス、ツール数
veles mcp test github       # 1つのサーバーに接続し、そのツールを一覧表示
```

`veles mcp list` は常に 0 で終了します — ヘルスゲートではなくインスペクターです。
`veles mcp test` は接続に失敗すると 1、未知のサーバー名の場合は 2 で終了します。

## ツールはどのように現れるか

設定すると、サーバーは次回の `veles run` / TUI / デーモン起動時に **自動的に** マウントされます —
別途「MCP を有効にする」フラグはなく、設定が存在することがスイッチになります。各ツールは
通常のレジストリに `mcp_<server>_<tool>` として登録され、組み込みツールと同様にエージェントから
呼び出せます。スキーマはサニタイズされる（名前・長さの制限、制御文字の除去）ため、信頼できない
サーバーがプロンプトへ注入することはできません。ツールのヒントは信頼ラダーにマッピングされます:
破壊的なツールは常に確認を求め、読み取り専用のツールは確認なしで実行され、それ以外はすべて通常の
[信頼（trust）](security-and-permissions.md) フローを経由します — 毎回尋ねられたくない場合は
`veles trust set` で常時承認を付与してください。

## 失敗時の扱い

接続に失敗したサーバー — `command` の欠落、不正な `url`、その他の無効なエントリ — は
警告としてログに記録され、スキップされます。起動やエージェントをブロックすることは決してありません。
ステータスとエラーを確認するには `veles mcp list` を再実行してください。

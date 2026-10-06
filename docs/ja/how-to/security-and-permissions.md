# セキュリティの管理方法: トラスト、オートパイロット、シークレット

> 🌐 **言語:** [English](../../en/how-to/security-and-permissions.md) · [简体中文](../../zh-CN/how-to/security-and-permissions.md) · [繁體中文](../../zh-TW/how-to/security-and-permissions.md) · **日本語** · [한국어](../../ko/how-to/security-and-permissions.md) · [Español](../../es/how-to/security-and-permissions.md) · [Français](../../fr/how-to/security-and-permissions.md) · [Italiano](../../it/how-to/security-and-permissions.md) · [Português (BR)](../../pt-BR/how-to/security-and-permissions.md) · [Português (PT)](../../pt-PT/how-to/security-and-permissions.md) · [Русский](../../ru/how-to/security-and-permissions.md) · [العربية](../../ar/how-to/security-and-permissions.md) · [हिन्दी](../../hi/how-to/security-and-permissions.md) · [বাংলা](../../bn/how-to/security-and-permissions.md) · [Tiếng Việt](../../vi/how-to/security-and-permissions.md)

Veles は危険なアクションを **トラストラダー** の背後でゲートし、ファイルアクセスをサンドボックス化し、
シークレットを OS のキーチェーンに保管します。その背景については
[トラストとサンドボックス](../explanation/trust-and-sandbox.md) を参照してください。

## トラストラダー

機密性の高いツール（`run_shell`、`write_file`、`fetch_url` など）は実行前に確認を求めます。
あなたは次から選びます。**今回だけ** 許可、**このプロジェクトでは常に** 許可、**どこでも常に** 許可、
または **拒否**。付与した許可は永続化されるので、再度尋ねられることはありません。

プロンプトを待たずに許可を管理します。

```bash
veles trust list                          # current grants (user + project)
veles trust set run_shell --scope project # pre-grant for this project
veles trust set write_file --scope user   # pre-grant everywhere
veles trust revoke run_shell              # remove a grant
veles trust clear --scope all             # wipe everything
```

一部のアクションは、許可があっても **常に確認されます**。ファイルの削除、URL の取得、新しい
スキル／ツール／モジュールのインストール、チャンネルの接続、プロジェクト外への書き込みです。

## オートパイロット — 時間制限付きのバイパス

無人実行（夜間バッチなど）のために、トラストプロンプトが自動的に許可されるウィンドウを開きます。

```bash
veles autopilot enable --until +2h
veles autopilot enable --until 2026-12-31T23:00:00Z
veles autopilot status
veles autopilot disable
```

オートパイロットのすべてのアクションは後で確認できるようにログに記録されます。非対話的なコンテキスト
（デーモン、バッチ）は、オートパイロットがアクティブでない限りデフォルトで拒否します。

## シークレット

API キーやボットトークンは OS のキーチェーンに保管され、設定ファイルには決して保存されません。

```bash
veles secret set OPENROUTER_API_KEY       # prompts (or pipe via stdin)
veles secret list                         # which secrets are configured
veles secret get OPENROUTER_API_KEY --reveal
veles secret delete OPENROUTER_API_KEY
veles secret set OPENROUTER_API_KEY --project myproj   # a key for one project only
```

検索は、`--no-env-fallback` を渡さない限り、対応する
[環境変数](../reference/environment-variables.md) にフォールバックします。

## サンドボックス

ツールはアクティブなプロジェクト内、`~/.veles/skills/`、`~/.veles/locales/` を読み取れます。
書き込みはプロジェクト内に限られ、レイアウトが書き込み可能ゾーンを宣言している場合はそのゾーンだけです。
高度なセットアップでは
`VELES_SANDBOX_ROOTS`（`:` 区切り）でルートを上書きできます。URL の取得には SSRF 拒否リストが
維持されており、`VELES_FETCH_ALLOW_PRIVATE=1` でプライベートネットワークのブロックが解除されます。

プロジェクトの `.veles/` 内では、エージェントのファイルツールが書き込めるのは `skills/`、`tools/`、
`tmp/`、`plans/`、`memory/`、`artifacts/` だけです。それ以外 —
`trust.json`、`config.toml`、`project.toml`、`modules/`、`wiki.toml`、`memory.db` —
は `veles` コマンドと Veles 自身のツールを通してのみ変更されます。ファイルツールは、プロジェクト内の
それ以外の `.veles/` ディレクトリ（サブプロジェクトのもの、またはエージェントが `wiki/` に置こうとするもの）も、
どの深さでも拒否します。そのため、ファイルツール経由でエージェントが自分にトラストを付与したり、Veles が
実行するコードを追加したりすることはできません（`.veles/tools/` に書いたツールは、そのファイルを承認した後に
初めて読み込まれます）。同じファイルの別の表記（大文字小文字、`..`、シンボリックリンク）も拒否されます。

明示的なコマンドなしで実行される、またはエージェント CLI を操作するファイル — `.git/`、`.githooks/`、
`.claude/`、`.gemini/`、`.agents/`、`.codex/`、`.vscode/`、`.devcontainer/`、`.husky/` 配下のすべて、および
`.envrc`、`.mcp.json`、`.pre-commit-config.yaml`、`lefthook.yml`（いずれも任意の深さ）、さらにリポジトリの
`core.hooksPath` ディレクトリと、シンボリックリンクの `.git` が指す先 — には、エージェントのファイルツールは
その書き込みを確認した後にのみ書き込みます。トラストの付与やオートパイロットはこれをカバーしません。
デーモンはチャンネルで確認を求め、確認する相手がいないバッチ実行は拒否します。

`claude-cli`、`codex`、`antigravity-cli` プロバイダーは、Veles のツールだけを持つモデルとして動作します。
それら自身のシェル、ファイル編集、Web ツール、プロジェクトの `.claude/` の設定とフック、
他の MCP サーバーは適用されず、呼び出す Veles のツールはすべて上記のトラストラダーを通ります
（そこにはプロンプトに答える人がいないため、付与済みでないものは拒否されます）。
それらの MCP 設定は `.veles/tmp/delegate-<pid>/` にあり、実行中のプロセスごとに 1 つで、エージェントのファイルツールはここに書き込めません。
`agy` はプロジェクトの外、`~/.veles/tmp/` 配下にある作業用の一時ワークスペースで実行されるため、
プロジェクト自身の `.agents/` のフックや MCP サーバーは届きません。Veles のツールを持つときは
`--dangerously-skip-permissions` が付きます（付けないと agy はヘッドレスで MCP 呼び出しを拒否します）。
そのワークスペースのフックが agy 自身のツールをすべて拒否し、失敗したフックも拒否になります。
Veles のファイルツールはプロジェクトの外には書き込めないため、agy がそれらを通じてそのフックを書き換えることはできません。
`codex` もプロジェクトの外で実行され、あなたの codex 設定は無視され、読み取り専用のサンドボックスの中で、
自身のツールは機能フラグによってオフにされます。Veles は初回の実行の前に毎回そのフラグ名を確認し、
依存しているフラグの名前が変わった codex は、開いたまま実行されるのではなく拒否されます。
MCP サーバーは（設定ファイルなしで）引数として渡され、承認されるのはそのサーバーのツールだけで、
サーバーが受け取る環境変数は名前を指定して転送されます。`VELES_TRUST_AUTO_ALLOW` は決して転送されません。

既知の制限:

- `run_shell` はシェルです。付与した場合（またはオートパイロット中）は、上記のどのファイルにも
  ファイルごとの確認なしで書き込めます。
- MCP の承認が固定するのはサーバーのコマンドラインであり、プロジェクトから実行されるファイル
  （`args` で指定されたスクリプト）ではありません。それらも確認してください。
- CLI プロバイダーを使う場合、自分自身にだけツールを事前承認する実行（デーモンのバックグラウンドジョブ、
  `veles research`）は、それを委譲先の CLI に引き継ぎません。事前承認は Veles のプロセス内にあり、
  CLI が起動する MCP サーバーは別のプロセスであるため、その Veles ツールには恒久的な
  `veles trust set` の付与かオートパイロットのウィンドウが必要です。親の実行のプランニングモードも
  同様に届きません。
- `antigravity-cli` は、agy がそのワークスペースの `.agents/hooks.json` に従うことを前提としています。
  ワークスペースのフックを読まなくなった agy のリリースがあれば、`--dangerously-skip-permissions` の下で
  agy 自身のツールが開いたままになります。

制御文字（ターミナルのエスケープ、bidi オーバーライド）を含むパスは拒否され、確認、トラストのプロンプト、
差分プレビューではそのような文字がエスケープして表示されます。ツール呼び出しが、あなたが承認する
テキストを偽装することはできません。

設定にある MCP サーバーは、承認した後にのみ起動します。
[外部 MCP サーバー](external-mcp-servers.md)を参照してください。

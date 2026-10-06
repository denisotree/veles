# スキル・ツール・モジュールの管理方法

> 🌐 **言語:** [English](../../en/how-to/manage-skills-and-tools.md) · [简体中文](../../zh-CN/how-to/manage-skills-and-tools.md) · [繁體中文](../../zh-TW/how-to/manage-skills-and-tools.md) · **日本語** · [한국어](../../ko/how-to/manage-skills-and-tools.md) · [Español](../../es/how-to/manage-skills-and-tools.md) · [Français](../../fr/how-to/manage-skills-and-tools.md) · [Italiano](../../it/how-to/manage-skills-and-tools.md) · [Português (BR)](../../pt-BR/how-to/manage-skills-and-tools.md) · [Português (PT)](../../pt-PT/how-to/manage-skills-and-tools.md) · [Русский](../../ru/how-to/manage-skills-and-tools.md) · [العربية](../../ar/how-to/manage-skills-and-tools.md) · [हिन्दी](../../hi/how-to/manage-skills-and-tools.md) · [বাংলা](../../bn/how-to/manage-skills-and-tools.md) · [Tiếng Việt](../../vi/how-to/manage-skills-and-tools.md)

Veles は時間とともに能力を蓄積していきます。**スキル** は再利用可能なワークフロー、
**ツール** は実行可能なアクション、**モジュール** はオプションのプラグインです。それぞれ
2 つのスコープに存在します。プロジェクトローカル（`<project>/.veles/`）とユーザーグローバル
（`~/.veles/`）です。概念については [スキルとツール](../explanation/skills-and-tools.md) を
参照してください。

## スキル

スキルとは、エージェントがツールのように呼び出せる `SKILL.md`（フロントマター + プロンプト
本文）です。

```bash
veles skill list                          # installed skills + telemetry
veles skill show <name>                   # print its SKILL.md
veles skill add https://github.com/org/skill.git
veles skill add ./local-skill --scope user   # install user-global
veles skill remove <name>
```

### スコープ間の昇格・降格

あるプロジェクトで有用だと分かったスキルは、ユーザースコープへ移動してすべてのプロジェクトから
参照できるようにできます（その逆も可能です）。

```bash
veles skill promote <name>     # project → ~/.veles/skills/
veles skill demote  <name>     # user → this project
```

### 重複と昇格候補の検出

```bash
veles skill dedup                         # near-duplicate skills (embedding/TF-IDF)
veles skill suggest-promote --save        # skills that meet the auto-promote bar
```

## ツール

ツールはプロジェクトの `memory.db` に利用テレメトリとともにカタログ化されます。Veles は作業を
進めながら自分自身のツールを書くこともできます。次のコマンドで管理します。

```bash
veles tool list                # tools in this project
veles tool show <name>         # manifest + telemetry
veles tool promote <name>      # move to ~/.veles/tools/ (cross-project)
```

機密性の高いツール（`run_shell`、`write_file`、`fetch_url` など）は
[トラストラダー](security-and-permissions.md) によってゲートされます。

## モジュール

モジュールは Python コード（`module.toml` + エントリーポイント）で、Veles の内部で動作し、
コアを肥大化させることなく、オプションの機能（メモリプロバイダー、埋め込み、ビジョン、STT）を追加します。
インストールにはデフォルトで確認が必要で、ファイルが承認時の内容と一致している間だけ、実行のたびに読み込まれます
（[インストールの健全性を保つ](../../en/how-to/extension-registries.md#keep-installs-honest)を参照）。

```bash
veles module list                              # 両方のスコープを `scope` 列付きで表示
veles module add https://github.com/org/module.git
veles module add ./local-module --user          # ~/.veles/modules/ にインストール（全プロジェクト共通）
veles module show <name> [--user]             # マニフェスト + ファイルの sha256
veles module remove <name> [--user]
veles module approve <name> [--user]          # ターミナルで `yes` と入力
veles module approve <name> --sha256 <hash>   # ターミナルなし: レビュー済みのハッシュ
```

モジュールは、スキルやツールと同じく 2 つのスコープに置かれます。プロジェクトローカル
（`<project>/.veles/modules/`）と、すべてのプロジェクトで読み込まれるユーザーグローバル
（`~/.veles/modules/`）です。ユーザーレベルのモジュールもプロジェクトのモジュールと同じ承認ゲートを通り、
ゲートは名前の比較より前に実行されます。プロジェクトとユーザーのモジュール名が同じ場合、承認済みの
プロジェクトモジュールが読み込まれ、Veles はユーザーレベルのモジュールが隠されることを警告します。
未承認のプロジェクトモジュールはスキップされ（警告にそのディレクトリ名が出ます）、ユーザーモジュールが
読み込まれます。同じスコープで承認済みの 2 つのモジュールが同じ名前を持つ場合は、最初の（ディレクトリ順で）
ものが読み込まれ、残りは警告してスキップされます。`veles module {show,approve,remove}` はマニフェスト名
（`list` に表示されるもの）を受け取り、スコープ内の複数のディレクトリが宣言している名前は、それらを
列挙して拒否します。`veles module add` は、スコープ内の別のディレクトリがすでに宣言している名前の
モジュールのインストールを拒否します。

### メモリプロバイダーを追加するモジュールを書く

モジュールの `register(api)` エントリーポイントは、`api.add_memory_provider(name, factory)` を呼び出して
外部のメモリソースを想起（recall）に組み込めます。`name` は `~/.veles/config.toml` の
`[memory.external.<name>]` セクションと一致する必要があります。`factory` はそのセクション（`dict`）を
受け取って呼び出され、Veles の `MemoryProvider` プロトコル（`veles.core.memory.provider`）を実装した
オブジェクトを返すか、そのプロバイダーをスキップするなら `None` を返します。

```toml
# module.toml
[module]
name = "my-provider"
description = "Recalls memories from my external store."
entrypoint = "my_provider.py:register"
version = "0.1.0"
```

```python
# my_provider.py
from veles.core.memory.provider import RecallHit


class MyProvider:
    name = "my-provider"

    def recall(self, query: str, *, limit: int) -> list[RecallHit]:
        ...  # query the external store, return RecallHit objects


def _build(cfg: dict) -> MyProvider | None:
    api_key = cfg.get("api_key")
    return MyProvider() if api_key else None


def register(api) -> None:
    api.add_memory_provider("my-provider", _build)
```

```toml
# ~/.veles/config.toml
[memory.external.my-provider]
api_key = "..."
```

`ingest(title, body, *, insight_id) -> bool`（`IngestingMemoryProvider` プロトコル）も実装している
プロバイダーには、読み取りだけでなく Veles の書き込みも渡されます。2 つのモジュールが同じプロバイダー名を
登録すると、2 番目のモジュールの読み込みは失敗し、警告付きでスキップされ、中途半端な登録は残りません。
`config.toml` に設定があるのに対応するモジュールがインストールされていないセクションは、インストール
コマンド付きの警告を 1 回出力します。その場合も想起は引き続き動作します。

レジストリには、Honcho、Mem0、Supermemory が既製のプロバイダーモジュールとして用意されています。
`veles registry install --user {honcho,mem0,supermemory}` でインストールし、インストール時に表示される
`uv tool install veles-ai --with '<package>'` コマンドを実行し（各モジュールは SDK — `mem0ai>=2.0`、
`honcho-ai>=2.5`、`supermemory>=3.62` — を宣言しており、Veles が代わりにインストールすることはありません）、
対応する `[memory.external.<name>]` セクションを記入します。

- **mem0**: `api_key`、`user_id`、任意の `agent_id`（そのエージェントのメモリも想起）と `host`。SDK の
  テレメトリーはデフォルトでオフ。想起のたびに追加で `GET /v1/ping/` リクエストを 1 回送ります。
- **supermemory**: `api_key`、任意の `user_id`（検索の `container_tag` として送信）と `base_url`。
- **honcho**: `api_key`、`workspace_id`、任意の `peer_id`（そのピアのメッセージだけを検索）と `base_url`。
  想起のたびにワークスペースの get-or-create を行い、`workspace_id` が存在しなければ作成します。

## さらに見つける

接続されたレジストリを検索します。

```bash
veles registry search [query] [--kind module|skill|layout|mcp]
```

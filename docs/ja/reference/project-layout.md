# プロジェクトレイアウトと状態

> 🌐 **言語:** [English](../../en/reference/project-layout.md) · [简体中文](../../zh-CN/reference/project-layout.md) · [繁體中文](../../zh-TW/reference/project-layout.md) · **日本語** · [한국어](../../ko/reference/project-layout.md) · [Español](../../es/reference/project-layout.md) · [Français](../../fr/reference/project-layout.md) · [Italiano](../../it/reference/project-layout.md) · [Português (BR)](../../pt-BR/reference/project-layout.md) · [Português (PT)](../../pt-PT/reference/project-layout.md) · [Русский](../../ru/reference/project-layout.md) · [العربية](../../ar/reference/project-layout.md) · [हिन्दी](../../hi/reference/project-layout.md) · [বাংলা](../../bn/reference/project-layout.md) · [Tiếng Việt](../../vi/reference/project-layout.md)

`veles init` が作成するもの、Veles が状態を保持する場所、そしてプロジェクトメモリのスキーマについて。

## `veles init` が生成するもの

ユーザーコンテンツ側は選択したレイアウトパック（`--layout`、デフォルトは `llm-wiki`）に依存しますが、`.veles/` の状態側はどのレイアウトでも同一です。

```
my-project/                  # veles init  (default llm-wiki layout)
├── AGENTS.md                # project context (injected into the agent)
├── CLAUDE.md → AGENTS.md    # symlink, so a `claude` CLI picks up the same context
├── GEMINI.md → AGENTS.md    # symlink, for a `gemini` CLI
├── sources/                 # raw, immutable source material (agent-readonly)
├── wiki/                    # the LLM-writable knowledge zone
│   ├── concepts/ entities/ queries/ self-doc/ sessions/ sources/
└── .veles/                  # project state (do not commit; machine-managed)
    ├── project.toml         # name, created_at, schema_version, layout
    ├── memory.db            # SQLite: sessions, turns, insights, rules, telemetry
    ├── memory/              # the agent's own memory artefacts:
    │   ├── LOG.md           #   append-only system-ops journal
    │   ├── insights/        #   rendered views of `insights` rows
    │   ├── sessions/        #   compaction summaries
    │   └── proposals/       #   subproject / skill-promotion proposals
    ├── jobs/                # scheduled-job outputs
    └── skills/              # project-local skills
```

`--layout notes` の場合、コンテンツ側は単一の `notes/` ディレクトリになります。`--layout bare` の場合、コンテンツのスキャフォールドはまったく作成されません。`wiki/INDEX.md`（オンデマンドのカタログ）は wiki の成長に合わせて生成されます。`config.toml`、`tools/`、`plans/` は、何かを設定したとき、エージェントがツールを書いたとき、あるいはゴールを実行したときに `.veles/` 配下に現れます。

## 状態ディレクトリ

| パス | スコープ | コミットする? |
|---|---|---|
| `<project>/AGENTS.md` + レイアウトコンテンツ（`wiki/`、`sources/`、`notes/` など） | プロジェクトコンテンツ | **はい** — これがあなたのナレッジベースです |
| `<project>/.veles/` | プロジェクトのマシン状態（メモリ、設定、ローカルスキル/ツール） | いいえ |
| `~/.veles/` | ユーザーグローバル: `config.toml`、信頼許可、プロジェクト横断のスキル/ツール、レイアウトパック、モデルキャッシュ、ロケール | いいえ |

`VELES_USER_HOME` はユーザーグローバルツリーの `~` をリダイレクトします（テスト、サンドボックス用）。

## プロジェクトメモリ（`.veles/memory.db` + `.veles/memory/`）

Veles のプロジェクトメモリは、あなたのコンテンツとは分離され、レイアウトに依存しない**構造化されたアーティファクト**です。SQLite データベース（WAL モード）が信頼できる情報源（source of truth）であり、`.veles/memory/` は人間が読める側（レンダリングされたインサイトビュー、セッションのダイジェスト、提案、システム運用ジャーナル）を保持します。主なテーブル:

| テーブル | 保持する内容 |
|---|---|
| `sessions`, `turns` | 会話履歴（ターンごとに1行） |
| `turns_fts` | ターンに対する全文インデックス（`veles sessions search` を支える） |
| `insights`, `insights_fts`, `insight_refs` | 学習されたインサイト（正規の行。markdown ビューは再生成可能）+ 重複排除リンク |
| `rules`, `rules_fts` | 安定プロンプトに注入されるフォーマット/do/don't/嗜好ルール |
| `skills`, `skill_uses`, `skill_tool_refs` | スキルレジストリ + テレメトリ + ツールリンク |
| `tools`, `tool_uses` | ツールレジストリ + テレメトリ（使用/成功/エラー回数） |
| `project_tree` | キャッシュされたプロジェクトファイルマップ + 関連度ランキング用のセマンティックタグ |

これらがどのように書き込まれ、想起されるかについては [プロジェクトメモリと学習ループ](../explanation/project-memory-and-learning-loop.md) を参照してください。

## レイアウトパック

`veles init --layout {llm-wiki|notes|bare|<custom>}` はコンテンツレイアウトを選びます。パックはスキャフォールド、AGENTS.md テンプレート、書き込み可能ゾーン、そして wiki エンジン（wiki ツール、INDEX プロンプト注入、wiki 想起）が有効かどうかを所有します。[レイアウトパックと LLM-Wiki](../explanation/layout-packs-and-llm-wiki.md) を参照してください。

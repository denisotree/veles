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

モジュールはコアを肥大化させることなく、オプションの機能（埋め込み、ビジョン、STT）を追加します。
インストールにはデフォルトで確認が必要です。

```bash
veles module list
veles module add https://github.com/org/module.git
veles module remove <name>
```

## さらに見つける

キュレーションされたレジストリを閲覧します。

```bash
veles browse skills [query]
veles browse modules [query]
```

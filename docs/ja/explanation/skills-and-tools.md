# 蓄積される能力としてのスキル & ツール

> 🌐 **言語:** [English](../../en/explanation/skills-and-tools.md) · [简体中文](../../zh-CN/explanation/skills-and-tools.md) · [繁體中文](../../zh-TW/explanation/skills-and-tools.md) · **日本語** · [한국어](../../ko/explanation/skills-and-tools.md) · [Español](../../es/explanation/skills-and-tools.md) · [Français](../../fr/explanation/skills-and-tools.md) · [Italiano](../../it/explanation/skills-and-tools.md) · [Português (BR)](../../pt-BR/explanation/skills-and-tools.md) · [Português (PT)](../../pt-PT/explanation/skills-and-tools.md) · [Русский](../../ru/explanation/skills-and-tools.md) · [العربية](../../ar/explanation/skills-and-tools.md) · [हिन्दी](../../hi/explanation/skills-and-tools.md) · [বাংলা](../../bn/explanation/skills-and-tools.md) · [Tiếng Việt](../../vi/explanation/skills-and-tools.md)

Veles は最小限のツールとスキルのセットから始まり、作業しながらそれを**成長させます**。
このページでは、両者の違いと、それらがどのように蓄積されるのかを説明します。コマンドについては
[スキル & ツールを管理する](../how-to/manage-skills-and-tools.md) を参照してください。

## ツール vs スキル

- **ツール**とは、単一の実行可能なアクションです。ファイルを読む、シェルコマンドを実行する、
  URL を取得する、Web を検索する、wiki ページを書く、といったものです。ツールはモデルが呼び出すものです。
- **スキル**とは、形式化された*プロセス*です。プロンプト本文と許可ツールリストを持つ
  `SKILL.md` で、焦点を絞ったサブエージェントとして実行されます。スキルはツールを組み合わせて
  繰り返し可能なワークフローにします（例: LLM-Wiki の `ingest`/`query`/`lint`）。

## 最小限の起動、オンデマンドの拡張

Veles は有用であるのに十分なだけのものに加え、より多くを引き出すための既知の場所とともに
起動します。追加要素（スキル、ツール、モジュール）のインストールはデフォルトで承認を求めますが、
継続的な自律性を付与することもできます。これにより、新規プロジェクトを軽量に保ちつつ、
必要な場所で能力を成長させられます。

## 能力はどのように蓄積されるか

1. **Veles は自らのツールを書く。** 繰り返しのタスクに気づくと、クリーンで型付けされ
   再利用可能な Python ツールを `<project>/.veles/tools/` に作成できます（アドバイザーによる
   コードレビューパス付き）。そのツールはテレメトリとともにレジストリに加わります。
2. **繰り返しのプロセスがスキルになる。** パターン検出器が繰り返されるツールの
   シーケンスを見つけ出し、それをスキルとして形式化することを提案します。スキルは別のスキルを
   `extends:` して、その本文とツールを継承できます。
3. **テレメトリがランキングを駆動する。** すべてのツール / スキルは使用回数 / 成功回数 /
   エラー回数を持ちます。これらは重複排除（`veles skill dedup`）と昇格の提案に供給されます。

## 2 つのスコープと昇格

ツールもスキルも 2 つのレベルに存在します:

- **プロジェクトローカル**（`<project>/.veles/`）— ここでのみ見えます。
- **ユーザーグローバル**（`~/.veles/`）— すべてのプロジェクトで利用可能です。

あるプロジェクトでその価値を証明した能力は、すべてのプロジェクトが恩恵を受けられるよう
ユーザースコープへ**昇格**でき（`veles skill promote`、`veles tool promote`）、または元に
**降格**できます。これが、Veles が苦労して獲得したワークフローをプロジェクト間で
持ち運ぶ仕組みです。

## なぜ単なるファイルではなくレジストリなのか

スキル / ツールをプレーンなファイルとして保存することで、それらは検査・編集可能なまま
保たれます。それらの*テレメトリ*を `memory.db` に保存することで、Veles はどれが実際に
機能するかを推論できます。この組み合わせこそが、「スクリプトのフォルダ」を、蓄積され
自己キュレーションされる能力へと変えるものです。

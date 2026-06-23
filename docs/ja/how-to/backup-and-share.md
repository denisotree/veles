# プロジェクトをバックアップして共有する方法

> 🌐 **言語:** [English](../../en/how-to/backup-and-share.md) · [简体中文](../../zh-CN/how-to/backup-and-share.md) · [繁體中文](../../zh-TW/how-to/backup-and-share.md) · **日本語** · [한국어](../../ko/how-to/backup-and-share.md) · [Español](../../es/how-to/backup-and-share.md) · [Français](../../fr/how-to/backup-and-share.md) · [Italiano](../../it/how-to/backup-and-share.md) · [Português (BR)](../../pt-BR/how-to/backup-and-share.md) · [Português (PT)](../../pt-PT/how-to/backup-and-share.md) · [Русский](../../ru/how-to/backup-and-share.md) · [العربية](../../ar/how-to/backup-and-share.md) · [हिन्दी](../../hi/how-to/backup-and-share.md) · [বাংলা](../../bn/how-to/backup-and-share.md) · [Tiếng Việt](../../vi/how-to/backup-and-share.md)

Veles プロジェクトはポータブルです。バックアップや移行のためにプロジェクトを単一の
`.tar.gz` バンドルにエクスポートしたり、データを漏らさずに共有するためにサニタイズされた
テンプレートとしてエクスポートしたりできます。

## フルバックアップ

ランタイムの一時データ（ロック、予算状態）を除き、プロジェクト全体（`.veles/` + `AGENTS.md`）を
パックします:

```bash
veles export full ./my-project-backup.tar.gz
```

どこにでも復元できます:

```bash
veles import ./my-project-backup.tar.gz                # into cwd
veles import ./my-project-backup.tar.gz --into ./restored
veles import ./my-project-backup.tar.gz --force        # overwrite an existing .veles/
```

フルバンドルには `memory.db`（セッション、インサイト）が含まれるため、プライベートデータとして
扱ってください。

## 共有可能なテンプレート

再利用可能な足場（スキーマ、スキル、モジュール、非セッションの wiki ページ）のみを
パックします。`memory.db`、`sources/`、`sessions/`、信頼の付与を**除去**し、
テキストを PII 編集します:

```bash
veles export template ./my-template.tar.gz
```

テンプレートを同僚に渡してください。彼らが `veles import` すれば、あなたの会話履歴や生の
ソースなしに、あなたの構造とスキルを得られます。

## どちらを使うか

| 目的 | コマンド |
|---|---|
| プロジェクトをそのままバックアップ / 移動する | `veles export full` |
| データではなく構造 + スキルを共有する | `veles export template` |

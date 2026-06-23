# Veles ドキュメント

> 🌐 **言語:** [English](../en/index.md) · [简体中文](../zh-CN/index.md) · [繁體中文](../zh-TW/index.md) · **日本語** · [한국어](../ko/index.md) · [Español](../es/index.md) · [Français](../fr/index.md) · [Italiano](../it/index.md) · [Português (BR)](../pt-BR/index.md) · [Português (PT)](../pt-PT/index.md) · [Русский](../ru/index.md) · [العربية](../ar/index.md) · [हिन्दी](../hi/index.md) · [বাংলা](../bn/index.md) · [Tiếng Việt](../vi/index.md)

Veles はミニマルでローカルファースト指向の CLI エージェントフレームワークです。プロジェクトディレクトリを指定すると、構造化された**プロジェクトメモリ**を保持し、あなたのセッションから**学習**し、任意の LLM プロバイダ（クラウドまたはローカル）を実行し、作業を進めながら再利用可能な**スキル**と**ツール**を蓄積していきます。

このドキュメントは [Diátaxis](https://diataxis.fr/) モデルに従っています。いま必要としているものに合った象限を選んでください。

## ここから始める

Veles を一度も実行したことがない場合は、2 つのチュートリアルを順番に進めてください。

1. **[はじめに](tutorials/getting-started.md)** — Veles をインストールし、API キーを設定し、最初のプロジェクトを作成して、最初のプロンプトを実行します。
2. **[ナレッジベースを構築する](tutorials/building-a-knowledge-base.md)** — ソースを LLM-Wiki に取り込み、質問し、セッションを統合します。

## チュートリアル — 手を動かして学ぶ

- [はじめに](tutorials/getting-started.md)
- [ナレッジベースを構築する](tutorials/building-a-knowledge-base.md)

## ハウツーガイド — タスクを達成する

- [プロバイダを設定する（クラウド & ローカル）](how-to/configure-providers.md)
- [異なるタスクを異なるモデルにルーティングする](how-to/per-task-routing.md)
- [Veles をデーモンとして実行する](how-to/run-as-daemon.md)
- [Telegram チャネルを接続する](how-to/connect-telegram.md)
- [スキル、ツール、モジュールを管理する](how-to/manage-skills-and-tools.md)
- [複数のプロジェクトとサブプロジェクトを扱う](how-to/multi-project-and-subprojects.md)
- [セキュリティ: trust、autopilot、シークレット](how-to/security-and-permissions.md)
- [長時間タスク: ゴール、ジョブ、ドリーミング、リサーチ](how-to/long-running-tasks.md)
- [外部 MCP サーバを接続する](how-to/external-mcp-servers.md)
- [プロジェクトをバックアップして共有する](how-to/backup-and-share.md)

## リファレンス — 調べる

- [CLI コマンドリファレンス](reference/cli.md)
- [設定（`config.toml`）](reference/configuration.md)
- [環境変数](reference/environment-variables.md)
- [プロバイダ](reference/providers.md)
- [TUI キーバインドとスラッシュコマンド](reference/tui.md)
- [プロジェクトレイアウトと状態](reference/project-layout.md)

## 解説 — 設計を理解する

- [アーキテクチャ概要](explanation/architecture.md)
- [プロジェクトメモリと学習ループ](explanation/project-memory-and-learning-loop.md)
- [蓄積される能力としてのスキルとツール](explanation/skills-and-tools.md)
- [実行モード](explanation/modes.md)
- [マルチエージェントオーケストレーション](explanation/multi-agent-orchestration.md)
- [レイアウトパックと LLM-Wiki](explanation/layout-packs-and-llm-wiki.md)
- [Trust とサンドボックス](explanation/trust-and-sandbox.md)

---

製品ビジョンと設計の根拠については `VISION.md`（リポジトリのルート）を、実装の完全な履歴については `MILESTONES.md` を参照してください。これらは開発者向けです。このドキュメントは Veles を**使う**ためのものです。

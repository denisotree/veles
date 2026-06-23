# 長時間タスクを実行する方法: ゴール、ジョブ、ドリーミング、リサーチ

> 🌐 **言語:** **English** · [Русский](../../ru/how-to/long-running-tasks.md)

単一のプロンプトを超えて、Veles は予算付きの複数ステップの **ゴール** を追求し、
**スケジュールされたジョブ** を実行し、メモリを統合するために **ドリーミング** し、ウェブを並列で
**リサーチ** し、**マネージャー** とサブエージェントにまたがって作業を分解できます。

## ゴール — 予算とチェックポイントを持つ目標

ゴールとは、明示的な制限と進捗ログを伴う長期スパンの目標です:

```bash
veles goal start "Draft a competitor analysis report" \
  --done-when "report.md exists and cites >=3 sources" \
  --max-steps 30 --max-cost-usd 5 --max-wall-time-s 3600

veles goal list
veles goal show <id>
veles goal checkpoint <id> "Outlined sections; cited 2 sources" --cost-usd 0.40
veles goal pause <id> ; veles goal resume <id>
veles goal done <id> --evidence report.md
veles goal cancel <id> --reason "scope changed"
```

TUI では、**goal** 実行モード（`Shift+Tab` で切り替え）が同じ FSM を
インタラクティブに駆動します: あなたにヒアリングし、プランを確認し、実行し、チェックします。

## ジョブ — スケジュールされたエージェント実行

cron 式、間隔、または特定時刻に一度だけプロンプトを実行するようスケジュールします:

```bash
veles job add --name daily-digest \
  --schedule "0 9 * * *" \
  --prompt "Summarise yesterday's sessions into wiki/digests/"

veles job list
veles job history <id>
veles job trigger <id>          # 次のティックで実行
veles job pause <id> ; veles job resume <id>
veles job remove <id>
```

`--schedule` は cron 式、`<N><s|m|h|d>`（例: `30m`）、または ISO
タイムスタンプを受け付けます。ジョブはデーモンが稼働しているときに実行されます。あるいは、
すべてを一度に同期実行することもできます:

```bash
veles job tick                  # 期限の来たジョブを今すぐ実行、デーモン不要
```

ジョブの出力をチャネルに配信するには `--deliver-to telegram:<chat_id>` を使います。

## ドリーミング — バックグラウンドでのメモリ統合

`dream` はインサイトを抽出し、スキルを重複排除し、昇格を提案し、wiki を lint します —
あなたを待たせることなくメモリを新鮮に保ちます:

```bash
veles dream
veles dream --include-consolidation     # （有料の）LLM 統合も実行する
veles dream --dry-run                    # 何をするかを表示する
```

稼働中のデーモンはアイドル時に自動的にドリーミングします。

## リサーチ — 並列ウェブ調査

```bash
veles research "What are the leading approaches to retrieval-augmented generation?" \
  --max-subquestions 4
```

Veles は質問を分解し、複数の角度を並列で探索し、引用付きのレポートを統合します。

## マネージャーモード — 任意のプロンプトを分解する

単一の実行に対してマルチエージェント分解を有効にします（マネージャーが explorer /
writer / advisor のサブエージェントを生成し、最終的な回答を自身では決して書きません）:

```bash
veles run --manager "Audit this codebase for security issues and write a report"
# or globally: export VELES_MANAGER_MODE=1   (=0 to force off)
```

[マルチエージェントオーケストレーション](../explanation/multi-agent-orchestration.md) を参照してください。

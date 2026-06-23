# 信頼とサンドボックス

> 🌐 **言語:** [English](../../en/explanation/trust-and-sandbox.md) · [简体中文](../../zh-CN/explanation/trust-and-sandbox.md) · [繁體中文](../../zh-TW/explanation/trust-and-sandbox.md) · **日本語** · [한국어](../../ko/explanation/trust-and-sandbox.md) · [Español](../../es/explanation/trust-and-sandbox.md) · [Français](../../fr/explanation/trust-and-sandbox.md) · [Italiano](../../it/explanation/trust-and-sandbox.md) · [Português (BR)](../../pt-BR/explanation/trust-and-sandbox.md) · [Português (PT)](../../pt-PT/explanation/trust-and-sandbox.md) · [Русский](../../ru/explanation/trust-and-sandbox.md) · [العربية](../../ar/explanation/trust-and-sandbox.md) · [हिन्दी](../../hi/explanation/trust-and-sandbox.md) · [বাংলা](../../bn/explanation/trust-and-sandbox.md) · [Tiếng Việt](../../vi/explanation/trust-and-sandbox.md)

Veles はあなたのマシン上で自律エージェントを実行するため、そのエージェントができることを
制約します。2 つのメカニズムが連携します: 機微なアクションのための**信頼のはしご**と、
ファイルシステムのための**サンドボックス**です。コマンドについては
[セキュリティと権限](../how-to/security-and-permissions.md) を参照してください。

## 信頼のはしご

すべてのツールが同等なわけではありません。ファイルを読むことは無害ですが、シェルコマンドを
実行したりディスクに書き込んだりすることはそうではありません。機微なツール（`run_shell`、`write_file`、`fetch_url` など）は
実行前に停止して尋ね、4 つの選択肢を提示します:

- **Once** — この 1 回の呼び出しのみを許可します。
- **Always for this project** — プロジェクトスコープの付与を永続化します。
- **Always everywhere** — ユーザースコープの付与を永続化します。
- **Refuse** — 拒否します。

付与は保存されるため、再度尋ねられることはありません。これにより段階的な制御が得られます:
ツールを 1 回だけ、1 つのプロジェクトで、またはグローバルに信頼する — あなたの選択を、
それが重要になる最初のときに行います。

### 常に確認するアクション

一部の操作は、**付与があっても** Veles が確認するほど危険です:
ファイルの削除、URL の取得、新しいスキル / ツール / モジュールのインストール、チャネルの
接続、そしてプロジェクト外への書き込みです。これらは外向きであるか元に戻しにくいため、
継続的な付与がこれらを暗黙にカバーすべきではありません。

### 非対話的な安全性

デーモン、バッチ、またはその他の非 TTY コンテキストでは、プロンプトを出す人間がいないため、
Veles はデフォルトで機微なアクションを**拒否**します。これにより、紛れ込んだ stdin が承認を
こっそり通すことはできません。意図的に無人で実行するには、[autopilot](../how-to/security-and-permissions.md#autopilot--a-time-boxed-bypass)
ウィンドウを開いてください。すべての autopilot アクションはレビュー用にログに記録されます。

## ファイルシステムのサンドボックス

パスガードが、ツールが読み書きできる場所を制限します:

- **読み取り** — アクティブなプロジェクト内（およびそのサブプロジェクト）に加え `~/.veles/`。
- **書き込み** — レイアウトの書き込み可能ゾーン（例: `wiki/`）のみ。`.veles/` はマシン状態のため
  常に書き込み可能です。

サンドボックスから脱出するシンボリックリンクは拒否され、`..` によるトラバーサルは
解決前に拒否されます。URL の取得は SSRF 拒否リストを保持します。高度なセットアップでは
`VELES_SANDBOX_ROOTS` でルートを上書きしたり、`VELES_FETCH_ALLOW_PRIVATE=1` で
プライベートネットワークのブロックを解除したりできます。どちらもオプトインです。

## なぜこの設計なのか

目標は**嫌な驚きのない有用な自律性**です: エージェントは読み取りのたびにプロンプトを出すこと
なく実際の作業を行えますが、あなたのマシンを損なったり、お金を使ったり、ボックスの外に
出たりしうるものはすべてゲートされます。1 回だけ、そしてあなたの好みに合わせて記憶されます。

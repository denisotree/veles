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
```

検索は、`--no-env-fallback` を渡さない限り、対応する
[環境変数](../reference/environment-variables.md) にフォールバックします。

## サンドボックス

ツールはアクティブなプロジェクト内と `~/.veles/` を読み取れますが、書き込みはレイアウトの書き込み
可能ゾーン（デフォルトでは `wiki/`、`.veles/`）に限られます。高度なセットアップでは
`VELES_SANDBOX_ROOTS`（`:` 区切り）でルートを上書きできます。URL の取得には SSRF 拒否リストが
維持されており、`VELES_FETCH_ALLOW_PRIVATE=1` でプライベートネットワークのブロックが解除されます。

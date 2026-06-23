# 如何連接 Telegram channel

> 🌐 **語言：** **English** · [Русский](../../ru/how-to/connect-telegram.md)

從 Telegram 與一個 Veles 專案對話。channel 是一個 gateway，會把
訊息轉發到一個 [daemon](run-as-daemon.md)，並把回覆串流回來。每個聊天都會擁有
它自己的對話 session。

## 先決條件

- 一個正在執行的 daemon（參閱[以 daemon 形式執行](run-as-daemon.md)）。
- 來自 [@BotFather](https://t.me/BotFather) 的 Telegram bot token。

## 方案 A——透過精靈附掛（建議）

在專案中執行 channel 精靈；它會寫入設定並把
token 存入作業系統的 keychain：

```bash
veles channel add --channel telegram
```

或附掛到某個具名的 daemon session：

```bash
veles channel add --channel telegram --session api
```

你也可以從 [daemon picker TUI](run-as-daemon.md#the-daemon-picker-tui) 做這件事：
在某個 daemon 上按 `c`，然後依提示操作。

這會產生一個設定區塊：

```toml
[channels.telegram]            # or [daemon.api.channels.telegram]
enabled = true
whitelist = ["@alice", "123456789"]
```

**whitelist** 限制 bot 會回應誰（Telegram `@username` 或數字
使用者 id）。留空則會回應所有人——不建議，因為每一則
訊息都會花費模型 tokens。

重啟 daemon 以套用：

```bash
veles daemon restart
```

## 方案 B——執行獨立的 gateway

若你偏好一個獨立的行程（而非 daemon 內的 channel），請執行：

```bash
export TELEGRAM_BOT_TOKEN=123456:ABC...
veles channel run --channel telegram \
  --daemon-url http://127.0.0.1:8765 \
  --daemon-token "$(veles daemon token add tg)"
```

## 管理聊天 sessions

```bash
veles channel list                       # registered platforms + session counts
veles channel list-sessions              # chat_id → session_id mappings
veles channel reset-session <chat_id>    # next message from that chat starts fresh
veles channel remove telegram            # drop the channel binding
```

## 多模態限制

傳送**照片或語音訊息**目前會回傳一則「not configured」通知。
Veles 定義了 `VisionAdapter` / STT adapter 的協定與一個 registry
（`modules/vision.py`、`modules/stt.py`），但**並未隨附任何具體的 adapter，也沒有任何
adapter 在 daemon 啟動時被註冊**，因此圖片與音訊尚未被分析。文字
聊天則完全可用。參閱 [providers 參考](../reference/providers.md#multimodal-status-vision--speech-to-text)。

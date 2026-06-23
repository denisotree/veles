# Telegram 채널 연결 방법

> 🌐 **언어:** **English** · [Русский](../../ru/how-to/connect-telegram.md)

Telegram에서 Veles 프로젝트와 대화하세요. 채널은 메시지를 [데몬](run-as-daemon.md)에
전달하고 응답을 스트리밍하는 게이트웨이입니다. 각 채팅은 자체적인 대화 세션을 갖습니다.

## 사전 요구 사항

- 실행 중인 데몬 ([데몬으로 실행](run-as-daemon.md) 참고).
- [@BotFather](https://t.me/BotFather)에서 발급한 Telegram 봇 토큰.

## 옵션 A — 마법사로 연결 (권장)

프로젝트에서 채널 마법사를 실행합니다. 마법사가 설정을 작성하고 토큰을 OS 키체인에
저장합니다:

```bash
veles channel add --channel telegram
```

또는 특정 이름의 데몬 세션에 연결합니다:

```bash
veles channel add --channel telegram --session api
```

[데몬 선택기 TUI](run-as-daemon.md#the-daemon-picker-tui)에서도 할 수 있습니다:
데몬에서 `c`를 누르고 프롬프트를 따라가세요.

이 과정에서 다음 설정 블록이 생성됩니다:

```toml
[channels.telegram]            # or [daemon.api.channels.telegram]
enabled = true
whitelist = ["@alice", "123456789"]
```

**화이트리스트**는 봇이 응답할 사용자를 제한합니다(Telegram `@username` 또는 숫자
사용자 ID). 모두에게 응답하려면 비워두면 되지만 — 모든 메시지가 모델 토큰을 소비하므로
권장하지 않습니다.

변경 사항 적용을 위해 데몬을 재시작합니다:

```bash
veles daemon restart
```

## 옵션 B — 독립 실행형 게이트웨이 실행

데몬 내장 채널 대신 별도 프로세스를 선호한다면 다음을 실행합니다:

```bash
export TELEGRAM_BOT_TOKEN=123456:ABC...
veles channel run --channel telegram \
  --daemon-url http://127.0.0.1:8765 \
  --daemon-token "$(veles daemon token add tg)"
```

## 채팅 세션 관리

```bash
veles channel list                       # 등록된 플랫폼 + 세션 수
veles channel list-sessions              # chat_id → session_id 매핑
veles channel reset-session <chat_id>    # 해당 채팅의 다음 메시지를 새 세션으로 시작
veles channel remove telegram            # 채널 바인딩 제거
```

## 멀티모달 제한 사항

현재 **사진이나 음성 메시지**를 전송하면 "구성되지 않음" 알림이 반환됩니다.
Veles는 `VisionAdapter` / STT 어댑터 프로토콜과 레지스트리(`modules/vision.py`,
`modules/stt.py`)를 정의하지만, **구체적인 어댑터가 제공되지 않으며 데몬 시작 시
등록되지 않아** 이미지와 오디오는 아직 분석되지 않습니다. 텍스트 채팅은 완전히
작동합니다. [프로바이더 레퍼런스](../reference/providers.md#multimodal-status-vision--speech-to-text)를
참고하세요.

# Telegram 채널 연결 방법

> 🌐 **언어:** [English](../../en/how-to/connect-telegram.md) · [简体中文](../../zh-CN/how-to/connect-telegram.md) · [繁體中文](../../zh-TW/how-to/connect-telegram.md) · [日本語](../../ja/how-to/connect-telegram.md) · **한국어** · [Español](../../es/how-to/connect-telegram.md) · [Français](../../fr/how-to/connect-telegram.md) · [Italiano](../../it/how-to/connect-telegram.md) · [Português (BR)](../../pt-BR/how-to/connect-telegram.md) · [Português (PT)](../../pt-PT/how-to/connect-telegram.md) · [Русский](../../ru/how-to/connect-telegram.md) · [العربية](../../ar/how-to/connect-telegram.md) · [हिन्दी](../../hi/how-to/connect-telegram.md) · [বাংলা](../../bn/how-to/connect-telegram.md) · [Tiếng Việt](../../vi/how-to/connect-telegram.md)

Telegram에서 Veles 프로젝트와 대화하세요. 채널은 메시지를 [데몬](run-as-daemon.md)에
전달하고 응답을 스트리밍하는 게이트웨이입니다. 각 채팅은 자체적인 대화 세션을 갖습니다.

Telegram은 Veles 코어의 일부가 아니라 공식 확장 레지스트리(`official/telegram`)의
모듈입니다. 직접 설치할 필요가 없습니다. `veles channel add`가 설치를 제안하고,
설정의 `[channels.telegram]` 블록은 다음 `veles daemon start` 때 모듈을 설치합니다.
채널을 선언했으므로 그것이 곧 승인입니다. 연결한 레지스트리에서만 설치됩니다.

## 사전 요구 사항

- Veles 프로젝트 (데몬은 작동하는 채널이 있을 때만 시작됩니다 — 이것이 그 채널입니다).
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

변경 사항 적용을 위해 데몬을 시작(또는 재시작)합니다:

```bash
veles daemon start      # or: veles daemon restart
```

블록을 직접 작성해도 똑같이 동작합니다. 토큰은 `veles channel add`로 키체인에
넣거나 블록에 `bot_token = "…"`로 넣으세요. 토큰이 없으면 데몬은 시작을 거부하고
해결 명령을 알려 줍니다.

## 옵션 B — 독립 실행형 게이트웨이 실행

데몬 내장 채널 대신 별도 프로세스를 선호한다면 다음을 실행합니다:

```bash
export TELEGRAM_BOT_TOKEN=123456:ABC...   # or pass --secret
veles channel run --channel telegram \
  --daemon-url http://127.0.0.1:8765 \
  --daemon-token "$(veles daemon token add tg)"
```

`veles channel run --channel telegram`은 모듈이 없으면 먼저 설치합니다.

## 채팅 세션 관리

```bash
veles channel list                       # 등록된 플랫폼 + 세션 수
veles channel list-sessions              # chat_id → session_id 매핑
veles channel reset-session <chat_id>    # 해당 채팅의 다음 메시지를 새 세션으로 시작
veles channel remove telegram            # 채널 바인딩 제거
```

## 채팅의 에이전트 모드

`/mode`는 채팅의 에이전트 모드를 바꿉니다: `default`(전환 전과 같이 에이전트가
바로 답함), `auto`(메시지마다 먼저 계획할지 결정), `planning`(계획만 하고 아무것도
바꾸지 않음), `writing`(도구로 직접 실행). 현재 모드에는 체크 표시가 붙습니다.
선택은 데몬이 재시작될 때까지 유지됩니다. 모드의 상태 줄(예: *auto → plan*)은
답변 위에 표시됩니다.

`/goal <작업>`은 채팅에서 목표를 실행합니다. 에이전트는 알아야 할 것을 묻고
따를 계획을 보여 줍니다. `yes`라고 답하면 스스로 작업하며, 목표를 달성하거나
예산이 소진될 때까지 각 단계 후에 한 줄씩 보냅니다. 승인 요청은 계속 버튼으로
옵니다. `/goal`은 진행 상황을 보여 주고, `/goal cancel`은 현재 단계 후에 멈추며,
`/goal resume`은 멈춘 목표를 이어 갑니다.

당신만 알려 줄 수 있는 정보가 필요하면 에이전트가 채팅에서 묻습니다. 제안된
답을 누르거나 직접 입력하세요. 5분 안에 답이 없으면 가장 그럴듯한 가정으로
진행하고 무엇을 가정했는지 알려 줍니다.

`/settings`는 모델(데몬 설정으로 고정), 채팅의 세션, 토큰 사용량, 모드 버튼을
한 메시지로 보여 줍니다. `/tokens`는 데몬이 시작된 이후 세션의 토큰 사용량을,
`/context`는 모델의 컨텍스트 창이 얼마나 찼는지 보여 줍니다.

## 멀티모달 제한 사항

현재 **사진이나 음성 메시지**를 전송하면 "구성되지 않음" 알림이 반환됩니다.
Veles는 `VisionAdapter` / STT 어댑터 프로토콜과 레지스트리(`modules/vision.py`,
`modules/stt.py`)를 정의하지만, **구체적인 어댑터가 제공되지 않으며 데몬 시작 시
등록되지 않아** 이미지와 오디오는 아직 분석되지 않습니다. 텍스트 채팅은 완전히
작동합니다. [프로바이더 레퍼런스](../reference/providers.md#multimodal-status-vision--speech-to-text)를
참고하세요.

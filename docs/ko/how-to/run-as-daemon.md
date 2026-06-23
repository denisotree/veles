# Veles를 데몬으로 실행하는 방법

> 🌐 **언어:** [English](../../en/how-to/run-as-daemon.md) · [简体中文](../../zh-CN/how-to/run-as-daemon.md) · [繁體中文](../../zh-TW/how-to/run-as-daemon.md) · [日本語](../../ja/how-to/run-as-daemon.md) · **한국어** · [Español](../../es/how-to/run-as-daemon.md) · [Français](../../fr/how-to/run-as-daemon.md) · [Italiano](../../it/how-to/run-as-daemon.md) · [Português (BR)](../../pt-BR/how-to/run-as-daemon.md) · [Português (PT)](../../pt-PT/how-to/run-as-daemon.md) · [Русский](../../ru/how-to/run-as-daemon.md) · [العربية](../../ar/how-to/run-as-daemon.md) · [हिन्दी](../../hi/how-to/run-as-daemon.md) · [বাংলা](../../bn/how-to/run-as-daemon.md) · [Tiếng Việt](../../vi/how-to/run-as-daemon.md)

데몬은 에이전트를 API로 노출하는 선택적이고 오래 실행되는 HTTP+WS 서버입니다 — [채널](connect-telegram.md)(Telegram, …), 예약 [작업](long-running-tasks.md), 원격/헤드리스 사용의 기반입니다.

## 시작과 중지

```bash
veles daemon start              # detaches by default; binds 127.0.0.1:8765
veles daemon status             # is it running?
veles daemon stop               # SIGTERM via the pid file
```

`start`는 백그라운드로 분리되어 셸을 반환합니다. 포그라운드 프로세스(systemd `Type=simple`, Docker, 디버깅)가 필요하면 `--foreground`를 전달하세요. 바인드를 재정의하려면:

```bash
veles daemon start --host 0.0.0.0 --port 9000
```

데몬의 모델과 프로바이더는 프로젝트 설정에서 가져오며 **수명 동안 고정**됩니다 — 시작하기 전에 설정하세요.

```toml
# <project>/.veles/config.toml
[provider]
default = "ollama"            # provider name
model = "qwen3:4b-instruct"   # model id
```

## 인증 토큰

API 클라이언트는 베어러 토큰으로 인증합니다.

```bash
veles daemon token add tui-client     # mint a token
veles daemon token list               # list (masked)
veles daemon token remove tui-client
```

## 데몬 피커 (TUI)

하위 명령 없이 `veles daemon`을 실행하면 제어판이 열립니다 — 프로젝트의 데몬과 각 데몬의 채널을 보여주는 트리입니다.

```
Project: my-project
  default   running  pid=…  up 1.2h  qwen3:4b-instruct
    chan: telegram
  api       stopped
Other projects
  other-proj  running
```

키: `Enter`로 데몬 로그 열기; `s`/`t`/`r`로 시작/중지/재시작; `d`로 삭제; `c`/`x`로 채널 추가/제거; `q`로 종료.

## 프로젝트당 여러 데몬 (이름 있는 세션)

한 프로젝트에서 서로 다른 모델/포트를 가진 데몬 여러 개를 동시에 실행할 수 있습니다. 이름 있는 세션을 선언한 뒤 시작하세요.

```bash
veles daemon session create api --port 8801 --provider anthropic --model claude-opus-4.8
veles daemon start --name api
veles daemon session list
```

각 이름 있는 세션은 자체 `[daemon.<name>]` 설정 블록과 자체 채널(`[daemon.<name>.channels.*]`)을 가집니다.

## 프로젝트 전반의 데몬 나열

```bash
veles daemon list
veles daemon restart <project-or-slug>
veles daemon delete  <project-or-slug>
```

## 다음

- [Telegram 채널 연결하기](connect-telegram.md)
- [작업 예약하기](long-running-tasks.md)

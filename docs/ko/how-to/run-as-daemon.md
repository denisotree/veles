# Veles를 데몬으로 실행하는 방법

> 🌐 **언어:** **English** · [Русский](../../ru/how-to/run-as-daemon.md)

데몬은 선택적으로 실행할 수 있는 장기 실행 HTTP+WS 서버로, 에이전트를 API 형태로 노출합니다. [채널](connect-telegram.md)(Telegram 등), 예약된 [작업](long-running-tasks.md), 그리고 원격/헤드리스 사용의 기반이 됩니다.

## 시작 및 중지

```bash
veles daemon start              # 기본적으로 백그라운드로 실행; 127.0.0.1:8765에 바인딩
veles daemon status             # 실행 중인지 확인
veles daemon stop               # pid 파일을 통해 SIGTERM 전송
```

`start`는 백그라운드로 분리되어 셸로 돌아옵니다. 포그라운드 프로세스로 실행하려면(systemd `Type=simple`, Docker, 디버깅 시) `--foreground`를 전달하세요. 바인딩 주소를 변경하려면:

```bash
veles daemon start --host 0.0.0.0 --port 9000
```

데몬의 모델과 프로바이더는 프로젝트 설정에서 가져오며, **데몬이 실행되는 동안 고정됩니다**. 시작 전에 미리 설정하세요:

```toml
# <project>/.veles/config.toml
[provider]
default = "ollama:qwen3:4b-instruct"
```

## 인증 토큰

API 클라이언트는 베어러 토큰으로 인증합니다:

```bash
veles daemon token add tui-client     # 토큰 발급
veles daemon token list               # 목록 조회 (마스킹 처리)
veles daemon token remove tui-client
```

## 데몬 선택기 (TUI)

서브커맨드 없이 `veles daemon`을 실행하면 제어판이 열립니다. 프로젝트의 데몬 목록과 각 데몬의 채널을 트리 구조로 보여줍니다:

```
Project: my-project
  default   running  pid=…  up 1.2h  qwen3:4b-instruct
    chan: telegram
  api       stopped
Other projects
  other-proj  running
```

단축키: `Enter`로 데몬 로그 열기, `s`/`t`/`r`로 시작/중지/재시작, `d`로 삭제, `c`/`x`로 채널 추가/제거, `q`로 종료.

## 프로젝트당 여러 데몬 (이름 있는 세션)

하나의 프로젝트에서 서로 다른 모델/포트로 여러 데몬을 동시에 실행할 수 있습니다. 이름 있는 세션을 선언한 뒤 시작하세요:

```bash
veles daemon session create api --port 8801 --provider anthropic --model claude-opus-4.8
veles daemon start --name api
veles daemon session list
```

각 이름 있는 세션은 고유한 `[daemon.<name>]` 설정 블록과 고유한 채널(`[daemon.<name>.channels.*]`)을 가집니다.

## 여러 프로젝트의 데몬 목록 조회

```bash
veles daemon list
veles daemon restart <project-or-slug>
veles daemon delete  <project-or-slug>
```

## 다음 단계

- [Telegram 채널 연결하기](connect-telegram.md)
- [작업 예약하기](long-running-tasks.md)

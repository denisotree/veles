# 신뢰와 샌드박스

> 🌐 **언어:** [English](../../en/explanation/trust-and-sandbox.md) · [简体中文](../../zh-CN/explanation/trust-and-sandbox.md) · [繁體中文](../../zh-TW/explanation/trust-and-sandbox.md) · [日本語](../../ja/explanation/trust-and-sandbox.md) · **한국어** · [Español](../../es/explanation/trust-and-sandbox.md) · [Français](../../fr/explanation/trust-and-sandbox.md) · [Italiano](../../it/explanation/trust-and-sandbox.md) · [Português (BR)](../../pt-BR/explanation/trust-and-sandbox.md) · [Português (PT)](../../pt-PT/explanation/trust-and-sandbox.md) · [Русский](../../ru/explanation/trust-and-sandbox.md) · [العربية](../../ar/explanation/trust-and-sandbox.md) · [हिन्दी](../../hi/explanation/trust-and-sandbox.md) · [বাংলা](../../bn/explanation/trust-and-sandbox.md) · [Tiếng Việt](../../vi/explanation/trust-and-sandbox.md)

Veles는 여러분의 머신에서 자율 에이전트를 실행하므로, 에이전트가 할 수 있는 것을
제한합니다. 두 가지 메커니즘이 함께 작동합니다: 민감한 동작을 위한 **신뢰 사다리**와
파일시스템을 위한 **샌드박스**. 관련 명령어는
[보안 및 권한](../how-to/security-and-permissions.md)을 참고하세요.

## 신뢰 사다리

모든 툴이 동등하지는 않습니다. 파일 읽기는 무해하지만, 셸 명령 실행이나 디스크 쓰기는
그렇지 않습니다. 민감한 툴(`run_shell`, `write_file`, `fetch_url` 등)은 실행 전에
멈추고 네 가지 선택지를 제시합니다.

- **한 번만** — 이번 호출만 허용합니다.
- **이 프로젝트에서 항상** — 프로젝트 범위의 권한을 영구 저장합니다.
- **어디서나 항상** — 사용자 범위의 권한을 영구 저장합니다.
- **거부** — 허용하지 않습니다.

권한은 저장되므로 다시 묻지 않습니다. 이를 통해 단계적 제어가 가능합니다:
툴을 한 번만, 특정 프로젝트에서만, 또는 전역으로 신뢰할 수 있으며 — 첫 번째로
필요할 때 선택하면 됩니다.

### 항상 확인이 필요한 동작

일부 작업은 권한이 있더라도 Veles가 **반드시 확인**할 만큼 위험합니다:
파일 삭제, URL 가져오기, 새 스킬/툴/모듈 설치, 채널 연결, 프로젝트 외부에 쓰기.
이 작업들은 외부 영향을 미치거나 되돌리기 어렵기 때문에 사전 권한만으로 조용히
처리되어서는 안 됩니다.

### 비대화형 안전성

데몬, 배치, 또는 다른 비-TTY 환경에서는 사람이 프롬프트를 볼 수 없으므로, Veles는
기본적으로 민감한 동작을 **거부**합니다 — 스트레이 stdin이 승인을 몰래 통과시킬 수
없습니다. 의도적으로 무인 실행하려면
[오토파일럿](../how-to/security-and-permissions.md#autopilot--a-time-boxed-bypass)
창을 열면 됩니다. 모든 오토파일럿 동작은 검토를 위해 로깅됩니다.

## 파일시스템 샌드박스

경로 가드가 툴이 읽고 쓸 수 있는 범위를 제한합니다.

- **읽기** — 활성 프로젝트(및 하위 프로젝트) 내부와 `~/.veles/`.
- **쓰기** — 레이아웃의 쓰기 가능 영역(예: `wiki/`)만 가능. `.veles/`는 머신 상태를
  위해 항상 쓰기 가능합니다.

샌드박스를 벗어나는 심볼릭 링크는 거부되며, `..` 탐색은 해석 전에 차단됩니다.
URL 가져오기는 SSRF 차단 목록을 유지합니다. 고급 설정에서는 `VELES_SANDBOX_ROOTS`로
루트를 재정의하거나, `VELES_FETCH_ALLOW_PRIVATE=1`로 사설 네트워크 차단을 해제할 수
있습니다 — 두 가지 모두 명시적 선택입니다.

## 이 설계의 의도

목표는 **불쾌한 놀라움 없이 유용한 자율성**을 제공하는 것입니다: 에이전트는 읽기마다
프롬프트 없이 실제 작업을 수행할 수 있지만, 머신을 손상시키거나 비용을 발생시키거나
외부로 나가는 작업은 한 번 묻고 — 그 후에는 취향에 맞게 기억됩니다.

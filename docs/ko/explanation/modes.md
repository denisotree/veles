# 실행 모드

> 🌐 **언어:** [English](../../en/explanation/modes.md) · [简体中文](../../zh-CN/explanation/modes.md) · [繁體中文](../../zh-TW/explanation/modes.md) · [日本語](../../ja/explanation/modes.md) · **한국어** · [Español](../../es/explanation/modes.md) · [Français](../../fr/explanation/modes.md) · [Italiano](../../it/explanation/modes.md) · [Português (BR)](../../pt-BR/explanation/modes.md) · [Português (PT)](../../pt-PT/explanation/modes.md) · [Русский](../../ru/explanation/modes.md) · [العربية](../../ar/explanation/modes.md) · [हिन्दी](../../hi/explanation/modes.md) · [বাংলা](../../bn/explanation/modes.md) · [Tiếng Việt](../../vi/explanation/modes.md)

TUI에서 각 프롬프트는 **실행 모드**로 처리됩니다 — 해당 턴이 얼마나 많은 자율성을
가지고 어떤 도구를 사용할지 결정하는 전략입니다. `Shift+Tab`으로 모드를 순환합니다.
순서는 `auto → planning → writing → goal`입니다.

## 네 가지 모드

### `writing` — 직접 대화
간단한 모드: 프롬프트가 전체 도구셋을 갖춘 에이전트에게 전달되고, 에이전트가 응답합니다.
에이전트가 실제로 행동하기를 원하는 일반적인 작업에 사용하세요.

### `planning` — 읽기 전용 조사 + 계획
변경(뮤테이션)이 차단됩니다 (`write_file` 없음, `run_shell` 없음). 에이전트는
읽기/검색 도구를 사용해 컨텍스트를 수집한 다음 구조화된 계획 아티팩트를 생성합니다.
아무것도 건드리기 전에 생각할 때 사용하세요 — 또는 CLI에서 동일한 효과를 위해
`veles run`에 `--plan`을 전달하세요.

### `auto` — 스마트 라우팅 (기본값)
빠른 분류가 프롬프트가 직접 요청인지 계획이 필요한지 판단하고, 그에 따라 `writing`
또는 `planning`으로 디스패치합니다. 의도를 명시하지 않았을 때 가장 스마트한 기본
선택이기 때문에 순환의 첫 번째 정류장이 됩니다.

### `goal` — 장기 목표
다단계 목표를 위한 유한 상태 기계를 구동합니다: 명확화를 위해 인터뷰하고, 계획을
확인하고, 단계를 실행하고 (어드바이저 체크와 함께), 완료 조건을 검증합니다 — 모두
명시적인 예산 아래서. CLI 동등 명령은
[`veles goal`](../how-to/long-running-tasks.md#goals--objectives-with-budgets-and-checkpoints)
명령어 패밀리입니다.

## 모드가 존재하는 이유

다른 요청은 다른 수준의 신중함을 필요로 합니다. 빠른 질문에는 의례가 필요 없지만,
위험한 변경은 먼저 읽기 전용 계획 패스의 혜택을 받습니다. 큰 목표는 예산과 체크포인트가
필요합니다. 모드는 세션 전체에 하나의 동작을 고정하는 대신 턴마다 명시적이고 전환
가능하게 그 선택을 만듭니다.

세션 중간에 전환하면 에이전트에게 새 규칙이 알려지므로 동작이 즉시 바뀝니다.

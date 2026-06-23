# 장기 실행 작업 처리 방법: 목표, 작업, 드리밍, 리서치

> 🌐 **언어:** [English](../../en/how-to/long-running-tasks.md) · [简体中文](../../zh-CN/how-to/long-running-tasks.md) · [繁體中文](../../zh-TW/how-to/long-running-tasks.md) · [日本語](../../ja/how-to/long-running-tasks.md) · **한국어** · [Español](../../es/how-to/long-running-tasks.md) · [Français](../../fr/how-to/long-running-tasks.md) · [Italiano](../../it/how-to/long-running-tasks.md) · [Português (BR)](../../pt-BR/how-to/long-running-tasks.md) · [Português (PT)](../../pt-PT/how-to/long-running-tasks.md) · [Русский](../../ru/how-to/long-running-tasks.md) · [العربية](../../ar/how-to/long-running-tasks.md) · [हिन्दी](../../hi/how-to/long-running-tasks.md) · [বাংলা](../../bn/how-to/long-running-tasks.md) · [Tiếng Việt](../../vi/how-to/long-running-tasks.md)

단순한 단일 프롬프트를 넘어, Veles는 예산이 설정된 다단계 **목표(goal)**를 추구하고, **예약 작업(job)**을 실행하며, **드림(dream)**을 통해 메모리를 정리하고, 웹을 병렬로 **리서치**하며, **매니저**와 하위 에이전트에 작업을 분배할 수 있습니다.

## 목표 — 예산과 체크포인트가 있는 장기 목표

목표는 명시적인 제한과 진행 로그를 가진 장기 목표입니다:

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

TUI에서 **goal** 실행 모드(`Shift+Tab`으로 전환)를 사용하면 동일한 FSM을 대화형으로 구동합니다: 인터뷰 → 계획 확인 → 실행 → 검증 순서로 진행됩니다.

## 작업(Job) — 예약된 에이전트 실행

크론 표현식, 인터벌, 또는 특정 시각에 프롬프트를 예약하여 실행합니다:

```bash
veles job add --name daily-digest \
  --schedule "0 9 * * *" \
  --prompt "Summarise yesterday's sessions into wiki/digests/"

veles job list
veles job history <id>
veles job trigger <id>          # 다음 틱에 실행
veles job pause <id> ; veles job resume <id>
veles job remove <id>
```

`--schedule`은 크론 표현식, `<N><s|m|h|d>` 형식(예: `30m`), 또는 ISO 타임스탬프를 받습니다. 작업은 데몬이 실행 중일 때 동작하며, 데몬 없이 모든 작업을 한 번에 동기적으로 실행할 수도 있습니다:

```bash
veles job tick                  # 지금 당장 만료된 작업 실행, 데몬 불필요
```

`--deliver-to telegram:<chat_id>`로 작업 결과를 채널에 전달합니다.

## 드리밍 — 백그라운드 메모리 통합

`dream`은 인사이트를 추출하고, 스킬을 중복 제거하며, 프로모션을 제안하고, 위키를 린트합니다 — 기다리지 않고도 메모리를 신선하게 유지합니다:

```bash
veles dream
veles dream --include-consolidation     # LLM 통합(유료)도 함께 실행
veles dream --dry-run                    # 실행될 내용을 미리 확인
```

데몬이 실행 중이면 유휴 상태일 때 자동으로 드림을 수행합니다.

## 리서치 — 병렬 웹 조사

```bash
veles research "What are the leading approaches to retrieval-augmented generation?" \
  --max-subquestions 4
```

Veles는 질문을 분해하여 여러 각도를 병렬로 탐색하고, 출처가 명시된 보고서로 종합합니다.

## 매니저 모드 — 모든 프롬프트 분해

단일 실행에 멀티 에이전트 분해를 활성화합니다 (매니저가 탐색자/작성자/어드바이저 하위 에이전트를 생성하며, 최종 답변은 직접 작성하지 않습니다):

```bash
veles run --manager "Audit this codebase for security issues and write a report"
# 또는 전역으로: export VELES_MANAGER_MODE=1   (=0으로 강제 비활성화)
```

[멀티 에이전트 오케스트레이션](../explanation/multi-agent-orchestration.md)을 참고하세요.

# 아키텍처 개요

> 🌐 **언어:** [English](../../en/explanation/architecture.md) · [简体中文](../../zh-CN/explanation/architecture.md) · [繁體中文](../../zh-TW/explanation/architecture.md) · [日本語](../../ja/explanation/architecture.md) · **한국어** · [Español](../../es/explanation/architecture.md) · [Français](../../fr/explanation/architecture.md) · [Italiano](../../it/explanation/architecture.md) · [Português (BR)](../../pt-BR/explanation/architecture.md) · [Português (PT)](../../pt-PT/explanation/architecture.md) · [Русский](../../ru/explanation/architecture.md) · [العربية](../../ar/explanation/architecture.md) · [हिन्दी](../../hi/explanation/architecture.md) · [বাংলা](../../bn/explanation/architecture.md) · [Tiếng Việt](../../vi/explanation/architecture.md)

이 페이지는 Veles가 *무엇인지*, 그리고 각 구성 요소가 어떻게 맞물려 있는지 설명합니다.
나머지 문서를 이해하는 데 도움이 됩니다. 공식적인 제품 비전은 저장소 루트의 `VISION.md`를
참조하세요.

## 설계 의도

Veles는 의도적으로 **미니멀하고 깔끔하게 분리**되어 있습니다 — 단일 책임 모듈, 갓파일 없음.
**로컬 우선**이기도 합니다: 사용자 머신의 디렉터리에서 실행하고, 그곳에 구조화된 메모리를
유지합니다.

## 다섯 가지 핵심 기둥

코어의 모든 것은 다섯 가지 역할 중 하나를 담당합니다:

1. **프로젝트 메모리** — 콘텐츠와 분리된 구조화된 아티팩트로, 세션 로그, 학습된 규칙/인사이트,
   프로젝트 파일 맵, 텔레메트리가 있는 스킬/도구 레지스트리를 포함합니다.
   [프로젝트 메모리 & 학습 루프](project-memory-and-learning-loop.md)를 참조하세요.
2. **학습 루프** — 큐레이터, 인사이트 추출기, 드리밍이 메모리를 최신 상태로 유지하고
   경험을 재사용 가능한 규칙으로 전환합니다.
3. **멀티 에이전트 오케스트레이션** — 작업을 분해하고 전문화된 워커를 생성하는 매니저.
   [멀티 에이전트 오케스트레이션](multi-agent-orchestration.md)을 참조하세요.
4. **공급자 프로토콜** — 다양한 LLM 백엔드(클라우드, 로컬, CLI 위임)에 대한 단일 인터페이스.
   [공급자](../reference/providers.md)를 참조하세요.
5. **최소한의 도구 & 스킬** — Veles가 자체 도구를 작성하고 반복 프로세스를 스킬로
   공식화하면서 **축적**되는 소규모 부트스트랩 세트.
   [스킬 & 도구](skills-and-tools.md)를 참조하세요.

## 나머지는 모두 선택적 모듈

게이트웨이/채널, 데몬, 스케줄러, TUI, 비전/STT — 모두 **플러그 가능**하며 사용 시에만
로드됩니다. Veles는 최소한으로 부팅하고 필요에 따라 확장되므로, 단순한 `veles run`은
단순하게 유지됩니다.

## 한 번의 턴이 흐르는 방식

```
사용자 프롬프트
   │
   ▼
컨텍스트: AGENTS.md (소규모) + 프로젝트 메모리에서 필요 시 회상
   │
   ▼
에이전트 루프  ──►  공급자 (작업별 라우팅)  ──►  도구 호출
   │                                               │
   │            (신뢰 사다리가 민감한 도구를 게이팅)
   ▼
응답  ──►  메모리에 저장  ──►  학습 트리거 (인사이트, 큐레이터)
```

컨텍스트 파일(`AGENTS.md`)은 의도적으로 작게 유지됩니다. 보조 지식(위키 페이지,
프로젝트 파일 맵, 관련 과거 턴)은 미리 모두 덤프하는 대신 **필요 시** 가져옵니다.

## 상태가 저장되는 곳

- `<project>/.veles/` — 이 프로젝트의 메모리, 설정, 로컬 스킬/도구.
- `~/.veles/` — 사용자 전역 설정, 크로스 프로젝트 스킬/도구, 캐시, 신뢰.
- `<project>/AGENTS.md`, `wiki/`, `sources/` — 사용자 콘텐츠 (LLM-Wiki 레이아웃).

[프로젝트 레이아웃](../reference/project-layout.md)을 참조하세요.

## 하나의 루프로 여러 프로젝트

하나의 에이전트 루프가 여러 프로젝트를 처리합니다. 각 프로젝트는 자체 컨텍스트와
메모리를 가진 디렉터리를 가집니다. `AGENTS.md`는 `CLAUDE.md`/`GEMINI.md`에 심링크되어
있어 외부 CLI가 해당 디렉터리에서 실행될 때 동일한 컨텍스트를 볼 수 있습니다.
[여러 프로젝트](../how-to/multi-project-and-subprojects.md)를 참조하세요.

## 인터페이스

- **CLI** (`veles run`, `veles add`, …) — 일회성 및 스크립트 사용.
- **TUI** (`veles tui`) — [실행 모드](modes.md)가 있는 인터랙티브 REPL.
- **데몬 + 채널** — 헤드리스 API, Telegram, 예약 작업.

세 인터페이스 모두 동일한 코어 에이전트 루프를 구동합니다.

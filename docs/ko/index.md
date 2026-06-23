# Veles 문서

> 🌐 **언어:** [English](../en/index.md) · [简体中文](../zh-CN/index.md) · [繁體中文](../zh-TW/index.md) · [日本語](../ja/index.md) · **한국어** · [Español](../es/index.md) · [Français](../fr/index.md) · [Italiano](../it/index.md) · [Português (BR)](../pt-BR/index.md) · [Português (PT)](../pt-PT/index.md) · [Русский](../ru/index.md) · [العربية](../ar/index.md) · [हिन्दी](../hi/index.md) · [বাংলা](../bn/index.md) · [Tiếng Việt](../vi/index.md)

Veles는 미니멀하고 로컬 우선의 CLI 에이전트 프레임워크입니다. 프로젝트 디렉터리를 지정하면,
구조화된 **프로젝트 메모리**를 유지하고, 세션에서 **학습**하며, 어떤 LLM 공급자(클라우드 또는 로컬)도
실행할 수 있고, 작업하면서 재사용 가능한 **스킬**과 **도구**를 축적합니다.

이 문서는 [Diátaxis](https://diataxis.fr/) 모델을 따릅니다. 지금 필요한 것에 맞는
사분면을 선택하세요.

## 시작하기

Veles를 처음 실행하는 경우, 두 튜토리얼을 순서대로 진행하세요:

1. **[시작 가이드](tutorials/getting-started.md)** — Veles를 설치하고, API 키를 설정하고,
   첫 번째 프로젝트를 만들고, 첫 번째 프롬프트를 실행합니다.
2. **[지식 베이스 구축](tutorials/building-a-knowledge-base.md)** — LLM-Wiki에 소스를
   수집하고, 질문하고, 세션을 통합합니다.

## 튜토리얼 — 실습으로 배우기

- [시작 가이드](tutorials/getting-started.md)
- [지식 베이스 구축](tutorials/building-a-knowledge-base.md)

## 방법 가이드 — 작업 수행하기

- [공급자 설정 (클라우드 & 로컬)](how-to/configure-providers.md)
- [작업별로 다른 모델로 라우팅하기](how-to/per-task-routing.md)
- [Veles를 데몬으로 실행하기](how-to/run-as-daemon.md)
- [Telegram 채널 연결하기](how-to/connect-telegram.md)
- [스킬, 도구, 모듈 관리하기](how-to/manage-skills-and-tools.md)
- [여러 프로젝트 및 서브프로젝트로 작업하기](how-to/multi-project-and-subprojects.md)
- [보안: 신뢰, 자율 운전, 시크릿](how-to/security-and-permissions.md)
- [장기 실행 작업: 목표, 잡, 드리밍, 리서치](how-to/long-running-tasks.md)
- [외부 MCP 서버 연결하기](how-to/external-mcp-servers.md)
- [프로젝트 백업 및 공유하기](how-to/backup-and-share.md)

## 레퍼런스 — 찾아보기

- [CLI 명령어 레퍼런스](reference/cli.md)
- [설정 (`config.toml`)](reference/configuration.md)
- [환경 변수](reference/environment-variables.md)
- [공급자](reference/providers.md)
- [TUI 단축키 & 슬래시 명령어](reference/tui.md)
- [프로젝트 레이아웃 & 상태](reference/project-layout.md)

## 설명 — 설계 이해하기

- [아키텍처 개요](explanation/architecture.md)
- [프로젝트 메모리 & 학습 루프](explanation/project-memory-and-learning-loop.md)
- [축적되는 역량으로서의 스킬 & 도구](explanation/skills-and-tools.md)
- [실행 모드](explanation/modes.md)
- [멀티 에이전트 오케스트레이션](explanation/multi-agent-orchestration.md)
- [레이아웃 팩 & LLM-Wiki](explanation/layout-packs-and-llm-wiki.md)
- [신뢰 & 샌드박스](explanation/trust-and-sandbox.md)

---

제품 비전과 설계 근거는 저장소 루트의 `VISION.md`를 참조하고, 전체 구현 이력은
`MILESTONES.md`를 참조하세요. 이 두 파일은 개발자용입니다 — 이 문서는 Veles를
**사용하기** 위한 것입니다.

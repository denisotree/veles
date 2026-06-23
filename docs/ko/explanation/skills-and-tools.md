# 누적되는 역량으로서의 스킬과 툴

> 🌐 **언어:** [English](../../en/explanation/skills-and-tools.md) · [简体中文](../../zh-CN/explanation/skills-and-tools.md) · [繁體中文](../../zh-TW/explanation/skills-and-tools.md) · [日本語](../../ja/explanation/skills-and-tools.md) · **한국어** · [Español](../../es/explanation/skills-and-tools.md) · [Français](../../fr/explanation/skills-and-tools.md) · [Italiano](../../it/explanation/skills-and-tools.md) · [Português (BR)](../../pt-BR/explanation/skills-and-tools.md) · [Português (PT)](../../pt-PT/explanation/skills-and-tools.md) · [Русский](../../ru/explanation/skills-and-tools.md) · [العربية](../../ar/explanation/skills-and-tools.md) · [हिन्दी](../../hi/explanation/skills-and-tools.md) · [বাংলা](../../bn/explanation/skills-and-tools.md) · [Tiếng Việt](../../vi/explanation/skills-and-tools.md)

Veles는 최소한의 툴과 스킬 세트로 시작하여 작업을 수행하면서 **점차 성장**합니다.
이 페이지에서는 둘의 차이점과 누적 방식을 설명합니다. 관련 명령어는
[스킬 및 툴 관리](../how-to/manage-skills-and-tools.md)를 참고하세요.

## 툴 vs 스킬

- **툴(tool)**은 단일 실행 가능한 동작입니다 — 파일 읽기, 셸 명령 실행,
  URL 가져오기, 웹 검색, 위키 페이지 작성 등이 이에 해당합니다. 툴은 모델이 직접 호출합니다.
- **스킬(skill)**은 형식화된 *프로세스*입니다 — 프롬프트 본문과 허용된 툴 목록을 담은
  `SKILL.md`로, 집중된 서브 에이전트로 실행됩니다. 스킬은 툴을 조합해 반복 가능한
  워크플로우를 만듭니다 (예: LLM-Wiki의 `ingest`/`query`/`lint`).

## 최소 시작, 온디맨드 확장

Veles는 당장 쓸 수 있는 최소한의 구성으로 부팅되며, 더 많은 것을 가져올 수 있는
저장소를 기본으로 갖춥니다. 추가 설치(스킬, 툴, 모듈)는 기본적으로 승인을 요청하며,
지속적인 자율권을 부여할 수도 있습니다. 이를 통해 새 프로젝트는 가볍게 유지하면서
필요한 곳에서만 역량이 성장할 수 있습니다.

## 역량이 누적되는 방식

1. **Veles가 자체 툴을 작성합니다.** 반복 작업을 감지하면 깔끔하고 타입이 명시된
   재사용 가능한 Python 툴을 `<project>/.veles/tools/`에 작성합니다
   (어드바이저 코드 리뷰 과정 포함). 해당 툴은 텔레메트리와 함께 레지스트리에 등록됩니다.
2. **반복 프로세스가 스킬이 됩니다.** 패턴 감지기가 반복적인 툴 사용 순서를 발견하면
   스킬로 형식화할 것을 제안합니다. 스킬은 `extends:`를 통해 다른 스킬의 본문과 툴을
   상속할 수 있습니다.
3. **텔레메트리가 순위를 결정합니다.** 모든 툴/스킬은 사용 횟수, 성공 횟수, 오류
   횟수를 기록합니다. 이 데이터는 중복 제거(`veles skill dedup`)와 승격 제안에
   활용됩니다.

## 두 가지 범위와 승격

툴과 스킬은 모두 두 가지 수준에 존재합니다.

- **프로젝트 로컬** (`<project>/.veles/`) — 해당 프로젝트에서만 사용 가능.
- **사용자 글로벌** (`~/.veles/`) — 모든 프로젝트에서 사용 가능.

한 프로젝트에서 검증된 역량은 사용자 범위로 **승격**하여 모든 프로젝트가 혜택을 받을 수
있고 (`veles skill promote`, `veles tool promote`), 다시 **강등**할 수도 있습니다.
이것이 Veles가 프로젝트 간에 어렵게 쌓은 워크플로우를 공유하는 방식입니다.

## 파일이 아닌 레지스트리를 사용하는 이유

스킬/툴을 일반 파일로 저장하면 검사하고 편집하기 쉽습니다. *텔레메트리*를 `memory.db`에
저장하면 Veles가 실제로 효과 있는 것이 무엇인지 추론할 수 있습니다. 이 조합이 단순한
"스크립트 폴더"를 누적되고 자기 선별되는 역량으로 바꿉니다.

# 레이아웃 팩 & LLM-Wiki

> 🌐 **언어:** [English](../../en/explanation/layout-packs-and-llm-wiki.md) · [简体中文](../../zh-CN/explanation/layout-packs-and-llm-wiki.md) · [繁體中文](../../zh-TW/explanation/layout-packs-and-llm-wiki.md) · [日本語](../../ja/explanation/layout-packs-and-llm-wiki.md) · **한국어** · [Español](../../es/explanation/layout-packs-and-llm-wiki.md) · [Français](../../fr/explanation/layout-packs-and-llm-wiki.md) · [Italiano](../../it/explanation/layout-packs-and-llm-wiki.md) · [Português (BR)](../../pt-BR/explanation/layout-packs-and-llm-wiki.md) · [Português (PT)](../../pt-PT/explanation/layout-packs-and-llm-wiki.md) · [Русский](../../ru/explanation/layout-packs-and-llm-wiki.md) · [العربية](../../ar/explanation/layout-packs-and-llm-wiki.md) · [हिन्दी](../../hi/explanation/layout-packs-and-llm-wiki.md) · [বাংলা](../../bn/explanation/layout-packs-and-llm-wiki.md) · [Tiếng Việt](../../vi/explanation/layout-packs-and-llm-wiki.md)

**레이아웃 팩**은 프로젝트의 *사용자 콘텐츠*를 어떻게 구성할지 정의합니다 — 어떤
디렉터리가 존재하는지, 에이전트가 어디에 쓸 수 있는지, 어떤 작업을 제공하는지.
기본값은 **`bare`**로, `.veles/`와 `AGENTS.md` 외에는 디렉터리에 아무것도 추가하지 않습니다.
**LLM-Wiki**는 확장 레지스트리에 있는 옵션 중 하나이지, Veles의 핵심 원칙이 **아닙니다**.

## 레이아웃 팩이란

레이아웃 팩은 `layout.toml` 매니페스트(그리고 선택적인 스킬 및 템플릿 파일)를 가진
디렉터리입니다. 매니페스트는 다음을 선언합니다:

- **쓰기 가능 구역** — 에이전트가 콘텐츠를 쓸 수 있는 디렉터리
  (모든 `write_file`에서 강제됨).
- **읽기 전용 구역** — 에이전트가 읽지만 절대 수정하지 않는 자료.
- **작업** — 팩 내의 스킬로 제공되는 명명된 워크플로.
- **스캐폴드** (`[layout.scaffold]`) — `veles init`이 생성하는 것: 디렉터리와
  선택적인 `AGENTS.md` 템플릿 (`{name}`이 대체됨).
- **엔진** (`[layout.engines]`) — 팩이 요구하는 콘텐츠 기계. 엔진은 모듈이 제공합니다
  (레지스트리의 `wiki` 모듈이 `wiki`를 제공). 이것 없이는 위키 도구, 위키 회상, INDEX 주입이 프로젝트에 존재하지 않습니다.
- **컨텍스트 파일** (`context_file`) — 에이전트의 안정적인 시스템 프롬프트에 주입되는
  파일 (LLM-Wiki는 `INDEX.md`를 사용).

## 사용 가능한 팩

| 팩 | 출처 | `veles init --layout <name>`이 생성하는 것 |
|---|---|---|
| `bare` *(기본값)* | 내장 | 콘텐츠 스캐폴드 전혀 없음 — 코드 저장소 및 자유 형식 작업용. 프로젝트 루트 내에서 쓰기 허용 (여전히 신뢰 사다리 적용). |
| `llm-wiki` | 레지스트리 (`public:official/llm-wiki`, `wiki` 모듈을 함께 가져옴) | [Karpathy 스타일 LLM-Wiki](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f): `sources/` (관례상 읽기 전용, 강제되지 않음), `wiki/` (에이전트 쓰기 가능), `INDEX.md`가 프롬프트에 주입됨, `ingest`/`query`/`lint`/`organize`/`structure_design` 스킬, 위키 엔진 활성화, `veles add`와 `/wiki`. 레이아웃이 선언한 행동 프롬프트(`templates/behaviour.md`)가 sources/wiki 규율과 마이그레이션/로그 패치 규칙을 담당합니다. |
| `notes` | 레지스트리 (`public:official/notes`) | 에이전트가 쓰는 단일 플랫 `notes/` 디렉터리. 위키 기계 없음. |

터미널에서 `veles init`은 어떤 팩을 쓸지 묻습니다(설치된 팩과 레지스트리에 있는 팩).
설치되지 않은 팩을 고르면 설치를 제안합니다. `veles registry install llm-wiki`로 미리 설치할 수 있습니다.

## 1.2.3 이전의 프로젝트

레이아웃이 설치되지 않은 프로젝트(업그레이드 후의 `llm-wiki` 프로젝트, 또는 `layout` 키가 없는 프로젝트 —
당시에는 모두 위키 프로젝트였습니다)도 그대로 열립니다. 터미널에서는 `veles`와 `veles run`이
한 번의 확인으로 팩(필요한 엔진 포함)의 설치를 제안합니다. 그 밖의 경우 — 데몬, 채널, 다른 동사 —
Veles는 설치 명령을 한 번만 출력하고 위키 없이 동작합니다. `wiki/` 안의 어떤 것도 건드리지 않습니다.

## 커스텀 레이아웃

`~/.veles/layouts/<name>/layout.toml` (사용자 전역) 또는
`<project>/.veles/layouts/<name>/` (프로젝트 로컬; 동일한 이름의 사용자 및 내장 팩을
오버라이드)에 팩을 넣고 `veles init --layout <name>`을 전달하세요. 레지스트리의 `notes` 팩이
복사할 수 있는 최소 예제입니다. 설치된 어떤 모듈도 제공하지 않는 엔진을 요구하는 팩에도
같은 설치 제안이 표시됩니다. `AGENTS.md`에서 규칙을 설명할 수도 있습니다 —
레이아웃은 구역을 강제하고, AGENTS.md는 동작을 안내합니다.

## 레이아웃이 *아닌* 것

레이아웃은 **사용자 콘텐츠만** 관장합니다. Veles 자체의 프로젝트 메모리 —
`memory.db`와 `.veles/memory/` 아티팩트 트리 (인사이트, 세션 다이제스트, 제안,
시스템 운영 저널) — 는 시스템 측에 있으며 어떤 레이아웃에서도 동일하게 작동합니다.
레이아웃을 전환해도 학습 루프, 세션, 레지스트리는 건드리지 않습니다.
[아키텍처](architecture.md)와 [프로젝트 레이아웃](../reference/project-layout.md)을
참조하세요.

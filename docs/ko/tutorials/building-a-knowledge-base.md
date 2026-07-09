# 지식 베이스 구축하기

> 🌐 **언어:** [English](../../en/tutorials/building-a-knowledge-base.md) · [简体中文](../../zh-CN/tutorials/building-a-knowledge-base.md) · [繁體中文](../../zh-TW/tutorials/building-a-knowledge-base.md) · [日本語](../../ja/tutorials/building-a-knowledge-base.md) · **한국어** · [Español](../../es/tutorials/building-a-knowledge-base.md) · [Français](../../fr/tutorials/building-a-knowledge-base.md) · [Italiano](../../it/tutorials/building-a-knowledge-base.md) · [Português (BR)](../../pt-BR/tutorials/building-a-knowledge-base.md) · [Português (PT)](../../pt-PT/tutorials/building-a-knowledge-base.md) · [Русский](../../ru/tutorials/building-a-knowledge-base.md) · [العربية](../../ar/tutorials/building-a-knowledge-base.md) · [हिन्दी](../../hi/tutorials/building-a-knowledge-base.md) · [বাংলা](../../bn/tutorials/building-a-knowledge-base.md) · [Tiếng Việt](../../vi/tutorials/building-a-knowledge-base.md)

이 튜토리얼에서는 Veles 프로젝트를 살아있는 지식 베이스로 만듭니다: 몇 가지 소스를 인제스트하고, Veles가 위키 페이지를 작성하게 하고, 질문을 던지고, 학습한 내용을 통합합니다. 이것이 기본 **LLM-Wiki** 워크플로입니다. 약 15분 소요됩니다.

먼저 [시작하기](getting-started.md)를 완료해야 합니다.

## 개념

Veles 프로젝트에는 두 개의 콘텐츠 영역이 있습니다:

- `sources/` — 제공하는 원시적이고 불변의 자료 (에이전트는 읽기 전용).
- `wiki/` — 에이전트 자체의 LLM이 생성한 지식 (에이전트가 콘텐츠를 쓰는 유일한 영역).

소스를 제공하면 Veles가 링크된 위키 페이지로 정제합니다. 위키를 자연어로 쿼리할 수 있습니다. 이유에 대해서는 [레이아웃 팩 및 LLM-Wiki](../explanation/layout-packs-and-llm-wiki.md)를 참조하세요.

## 1. 소스 인제스트

`veles add`는 파일이나 URL을 읽고 요약한 위키 페이지를 작성합니다:

```bash
veles add https://en.wikipedia.org/wiki/Knowledge_management
veles add ./notes/meeting-2026-06-01.md
```

각 `add`는 `wiki/` 아래에 페이지를 생성하고 위키 그래프에 링크합니다.

## 2. 위키 성장 확인

작성된 내용을 확인하세요:

```bash
ls wiki/concepts wiki/entities
```

페이지들은 서로 교차 참조합니다. 온디맨드 `wiki/INDEX.md` 카탈로그는 에이전트가 필요할 때 로드하는 맵을 유지합니다(모놀리식 컨텍스트 덤프가 아닙니다).

## 3. 질문하기

이제 자연어로 지식 베이스에 쿼리하세요:

```bash
veles run "Using the wiki, summarise the main approaches to knowledge management
and cite the pages you used."
```

Veles는 위키를 검색하고, 관련 페이지를 읽고, 훈련 데이터만이 아닌 인제스트된 내용을 바탕으로 답변합니다.

인터랙티브한 대화를 원한다면 TUI(`veles tui`)에서 동일하게 할 수 있습니다.

## 4. 세션 통합

작업하면서 대화가 쌓입니다. 큐레이터를 실행하여 내구성 있는 위키 페이지로 압축하고 교훈을 추출하세요:

```bash
veles curate
```

이 명령은 `wiki/sessions/` 페이지를 작성하고 프로젝트의 인사이트와 규칙을 업데이트합니다. Veles는 시간이 지나면서 자동으로 이를 수행합니다 — [프로젝트 메모리 및 학습 루프](../explanation/project-memory-and-learning-loop.md)를 참조하세요.

## 5. 위키 건강 유지

시간이 지나면 페이지가 오래되거나 고아가 됩니다. `lint` 작업이 이를 찾아냅니다:

```bash
veles run "lint"
```

(`ingest`, `query`, `lint`는 LLM-Wiki 레이아웃과 함께 번들된 스킬입니다. `veles run "<operation>"`으로 호출하거나 에이전트가 직접 호출하게 할 수 있습니다.)

## 완성한 것

자기 조직화 지식 베이스: 소스를 넣으면 링크된 위키 페이지가 나오고, 자연어로 쿼리 가능하며, Veles가 통합하면서 점점 깔끔해집니다. 다음 단계:

- **[스킬, 도구, 모듈 관리](../how-to/manage-skills-and-tools.md)** —
  재사용 가능한 워크플로를 Veles에 가르칩니다.
- **[데몬으로 실행](../how-to/run-as-daemon.md)** + **[Telegram 연결](../how-to/connect-telegram.md)** —
  휴대폰에서 지식 베이스와 대화합니다.
- **[복수 프로젝트 및 서브프로젝트](../how-to/multi-project-and-subprojects.md)** —
  여러 지식 베이스로 확장합니다.

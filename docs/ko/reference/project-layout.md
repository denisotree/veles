# 프로젝트 레이아웃 및 상태

> 🌐 **언어:** [English](../../en/reference/project-layout.md) · [简体中文](../../zh-CN/reference/project-layout.md) · [繁體中文](../../zh-TW/reference/project-layout.md) · [日本語](../../ja/reference/project-layout.md) · **한국어** · [Español](../../es/reference/project-layout.md) · [Français](../../fr/reference/project-layout.md) · [Italiano](../../it/reference/project-layout.md) · [Português (BR)](../../pt-BR/reference/project-layout.md) · [Português (PT)](../../pt-PT/reference/project-layout.md) · [Русский](../../ru/reference/project-layout.md) · [العربية](../../ar/reference/project-layout.md) · [हिन्दी](../../hi/reference/project-layout.md) · [বাংলা](../../bn/reference/project-layout.md) · [Tiếng Việt](../../vi/reference/project-layout.md)

`veles init`이 생성하는 파일들, Veles가 상태를 저장하는 위치, 그리고 프로젝트 메모리 스키마를 설명합니다.

## `veles init`이 생성하는 것

사용자 콘텐츠 부분은 선택한 레이아웃 팩(`--layout`, 기본값 `llm-wiki`)에 따라 달라지며, `.veles/` 상태 부분은 어디서나 동일합니다.

```
my-project/                  # veles init  (default llm-wiki layout)
├── AGENTS.md                # project context (injected into the agent)
├── CLAUDE.md → AGENTS.md    # symlink, so a `claude` CLI picks up the same context
├── GEMINI.md → AGENTS.md    # symlink, for a `gemini` CLI
├── sources/                 # raw, immutable source material (agent-readonly)
├── wiki/                    # the LLM-writable knowledge zone
│   ├── concepts/ entities/ queries/ self-doc/ sessions/
└── .veles/                  # project state (do not commit; machine-managed)
    ├── project.toml         # name, created_at, schema_version, layout
    ├── memory.db            # SQLite: sessions, turns, insights, rules, telemetry
    ├── memory/              # the agent's own memory artefacts:
    │   ├── LOG.md           #   append-only system-ops journal
    │   ├── insights/        #   rendered views of `insights` rows
    │   ├── sessions/        #   compaction summaries
    │   └── proposals/       #   subproject / skill-promotion proposals
    ├── jobs/                # scheduled-job outputs
    └── skills/              # project-local skills
```

`--layout notes`를 사용하면 콘텐츠 부분이 단일 `notes/` 디렉터리가 되고, `--layout bare`를 사용하면 콘텐츠 스캐폴드가 전혀 생성되지 않습니다. `wiki/INDEX.md`(온디맨드 카탈로그)는 위키가 성장함에 따라 생성됩니다. `config.toml`, `tools/`, `plans/`는 무언가를 설정하거나, 에이전트가 도구를 작성하거나, 목표를 실행할 때 `.veles/` 아래에 나타납니다.

## 상태 디렉터리

| 경로 | 범위 | 커밋 여부 |
|---|---|---|
| `<project>/AGENTS.md` + 레이아웃 콘텐츠 (`wiki/`, `sources/`, `notes/`, …) | 프로젝트 콘텐츠 | **예** — 이것이 지식 베이스입니다 |
| `<project>/.veles/` | 프로젝트 머신 상태 (메모리, 설정, 로컬 스킬/도구) | 아니요 |
| `~/.veles/` | 사용자 전역: `config.toml`, 신뢰 부여, 크로스 프로젝트 스킬/도구, 레이아웃 팩, 모델 캐시, 로케일 | 아니요 |

`VELES_USER_HOME`은 사용자 전역 트리의 `~` 경로를 재지정합니다(테스트, 샌드박스용).

## 프로젝트 메모리 (`.veles/memory.db` + `.veles/memory/`)

Veles의 프로젝트 메모리는 콘텐츠와 별개이며 레이아웃에 독립적인 **구조화된 아티팩트**입니다. SQLite 데이터베이스(WAL 모드)가 신뢰할 수 있는 소스이며, `.veles/memory/`는 사람이 읽을 수 있는 측면(렌더링된 인사이트 뷰, 세션 다이제스트, 제안, 시스템 운영 저널)을 담당합니다.
주요 테이블:

| 테이블 | 저장 내용 |
|---|---|
| `sessions`, `turns` | 대화 기록 (턴당 한 행) |
| `turns_fts` | 턴에 대한 전체 텍스트 인덱스 (`veles sessions search` 기능 제공) |
| `insights`, `insights_fts`, `insight_refs` | 학습된 인사이트 (정규 행; 마크다운 뷰는 재생성 가능) + 중복 제거 링크 |
| `rules`, `rules_fts` | 안정적인 프롬프트에 주입되는 형식/do/don't/선호도 규칙 |
| `skills`, `skill_uses`, `skill_tool_refs` | 스킬 레지스트리 + 텔레메트리 + 도구 링크 |
| `tools`, `tool_uses` | 도구 레지스트리 + 텔레메트리 (사용/성공/오류 횟수) |
| `project_tree` | 캐시된 프로젝트 파일 맵 + 관련성 순위 지정을 위한 의미 태그 |

이것들이 어떻게 작성되고 회상되는지는 [프로젝트 메모리 및 학습 루프](../explanation/project-memory-and-learning-loop.md)를 참조하세요.

## 레이아웃 팩

`veles init --layout {llm-wiki|notes|bare|<custom>}`은 콘텐츠 레이아웃을 선택합니다. 팩은 스캐폴드, AGENTS.md 템플릿, 쓰기 가능 영역, 그리고 위키 엔진(위키 도구, INDEX 프롬프트 주입, 위키 회상)의 활성화 여부를 소유합니다. [레이아웃 팩 및 LLM-Wiki](../explanation/layout-packs-and-llm-wiki.md)를 참조하세요.

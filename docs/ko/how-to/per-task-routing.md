# 작업별 모델 라우팅 방법

> 🌐 **언어:** [English](../../en/how-to/per-task-routing.md) · [简体中文](../../zh-CN/how-to/per-task-routing.md) · [繁體中文](../../zh-TW/how-to/per-task-routing.md) · [日本語](../../ja/how-to/per-task-routing.md) · **한국어** · [Español](../../es/how-to/per-task-routing.md) · [Français](../../fr/how-to/per-task-routing.md) · [Italiano](../../it/how-to/per-task-routing.md) · [Português (BR)](../../pt-BR/how-to/per-task-routing.md) · [Português (PT)](../../pt-PT/how-to/per-task-routing.md) · [Русский](../../ru/how-to/per-task-routing.md) · [العربية](../../ar/how-to/per-task-routing.md) · [हिन्दी](../../hi/how-to/per-task-routing.md) · [বাংলা](../../bn/how-to/per-task-routing.md) · [Tiếng Việt](../../vi/how-to/per-task-routing.md)

Veles는 하나의 모델에 묶여 있지 않습니다. 각 내부 **태스크**는 서로 다른 `provider:model`을 사용할 수 있습니다 — 컨텍스트 압축에는 저렴한 모델, 메인 에이전트에는 강력한 모델, 이미지에는 비전 모델. 이것이 *앙상블 라우팅* 시스템입니다.

## 태스크 유형

| 태스크 | 용도 |
|---|---|
| `default` | 메인 에이전트 루프 |
| `curator` | 세션 → 위키 통합 |
| `compressor` | 슬라이딩 윈도우 컨텍스트 압축 |
| `insights` | 실행 후 인사이트 추출 |
| `skills` | 스킬 실행 |
| `advisor` | `advisor_review` 자체 점검 |
| `vision` | `image_describe`(비전 어댑터가 연결된 경우) |
| `embedding` | `veles skill dedup` 유사도 |

## 현재 라우팅 확인

```bash
veles route show
```

이 명령은 모든 태스크에 대해 확정된 `provider:model`과, 어느 계층이 그것을 결정했는지 나타내는 `source` 레이블을 출력합니다.

## 태스크를 모델에 고정

```bash
veles route set compressor openrouter:anthropic/claude-haiku-4.5
veles route set advisor    openrouter:anthropic/claude-opus-4.8
veles route set vision     openai:gpt-4o
```

이 명령들은 `<project>/.veles/config.toml`에 `[routing.tasks]`를 기록합니다.

```toml
[routing.tasks]
compressor = "openrouter:anthropic/claude-haiku-4.5"
advisor    = "openrouter:anthropic/claude-opus-4.8"
vision     = "openai:gpt-4o"
```

## 재설정

```bash
veles route reset compressor   # one task back to default
veles route reset              # all tasks back to default
```

## AGENTS.md의 자연어 힌트

`AGENTS.md`에 라우팅을 산문으로 표현할 수 있습니다(예: "압축에는 저렴한 모델을 사용하라"). Veles는 이를 자동 생성되는 `routing.nl.toml`로 파싱합니다.

```bash
veles route refresh            # re-parse AGENTS.md hints
veles route refresh --force    # even if AGENTS.md hasn't changed
```

명시적인 `[routing.tasks]` 항목이 NL 힌트보다 언제나 우선합니다.

## 해석 순서

각 태스크에 대해, 스펙을 산출하는 첫 번째 계층이 우선합니다.

1. 프로젝트 `[routing.tasks][task]`
2. 프로젝트 `[routing.tasks].default`
3. 프로젝트 NL 힌트(`routing.nl.toml`)
4. 프로젝트 `[provider]` 기반
5. 사용자 `[routing.tasks][task]` / `.default`
6. 사용자 `[user] default_provider` + `default_model`

이 중 어느 것도 해석되지 않으면 **하드코딩된 폴백은 없습니다** — 태스크는 설정되지 않은 채로 남고, 그 호출자는 (해당 기능을 건너뛰며) 우아하게 성능을 낮추거나 명확하게 오류를 냅니다. 조용히 클라우드 모델을 끌어다 쓰지 않습니다.

(`embedding`은 catch-all을 건너뜁니다 — 챗 모델은 임베딩 모델이 아니므로 — 따라서 오직 명시적인 `[routing.tasks].embedding`만이 이를 충족합니다.)

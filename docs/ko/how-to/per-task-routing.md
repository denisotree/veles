# 작업별 모델 라우팅 방법

> 🌐 **언어:** **English** · [Русский](../../ru/how-to/per-task-routing.md)

Veles는 하나의 모델에 고정되지 않습니다. 각 내부 **작업(task)**은 서로 다른 `provider:model`을 사용할 수 있습니다 — 컨텍스트 압축에는 저렴한 모델, 메인 에이전트에는 강력한 모델, 이미지에는 비전 모델 등. 이것이 *앙상블 라우팅* 시스템입니다.

## 작업 유형

| 작업 | 사용 목적 |
|---|---|
| `default` | 메인 에이전트 루프 |
| `curator` | 세션 → 위키 통합 |
| `compressor` | 슬라이딩 윈도우 컨텍스트 압축 |
| `insights` | 실행 후 인사이트 추출 |
| `skills` | 스킬 실행 |
| `advisor` | `advisor_review` 자가 점검 |
| `vision` | `image_describe` (비전 어댑터가 연결된 경우) |
| `embedding` | `veles skill dedup` 유사도 계산 |

## 현재 라우팅 확인

```bash
veles route show
```

모든 작업에 대해 결정된 `provider:model`과 어떤 레이어에서 결정했는지 나타내는 `source` 레이블을 출력합니다.

## 작업을 특정 모델에 고정

```bash
veles route set compressor openrouter:anthropic/claude-haiku-4.5
veles route set advisor    openrouter:anthropic/claude-opus-4.8
veles route set vision     openai:gpt-4o
```

이 명령들은 `<project>/.veles/config.toml`의 `[routing.tasks]`에 기록됩니다:

```toml
[routing.tasks]
compressor = "openrouter:anthropic/claude-haiku-4.5"
advisor    = "openrouter:anthropic/claude-opus-4.8"
vision     = "openai:gpt-4o"
```

## 초기화

```bash
veles route reset compressor   # 특정 작업을 기본값으로 되돌림
veles route reset              # 모든 작업을 기본값으로 되돌림
```

## AGENTS.md의 자연어 힌트

`AGENTS.md`에 자연어로 라우팅을 표현할 수 있습니다 (예: "압축에는 저렴한 모델 사용"). Veles는 이를 파싱하여 자동 생성된 `routing.nl.toml`에 저장합니다:

```bash
veles route refresh            # AGENTS.md 힌트 재파싱
veles route refresh --force    # AGENTS.md 변경 여부와 관계없이 강제 실행
```

명시적인 `[routing.tasks]` 항목은 항상 자연어 힌트보다 우선합니다.

## 결정 순서

각 작업에 대해 명세를 제공하는 첫 번째 레이어가 우선됩니다:

1. 프로젝트 `[routing.tasks][task]`
2. 프로젝트 `[routing.tasks].default`
3. 프로젝트 자연어 힌트 (`routing.nl.toml`)
4. 프로젝트 `[provider]` 기본값
5. 사용자 `[routing.tasks][task]` / `.default`
6. 사용자 `[user] default_provider` + `default_model`
7. 해당 작업에 대한 내장 기본값

(`embedding`은 범용 기본값을 건너뜁니다 — 채팅 모델은 임베딩 모델이 아닙니다.)

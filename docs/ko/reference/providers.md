# 프로바이더

> 🌐 **Languages:** **English** · [Русский](../../ru/reference/providers.md)

Veles는 프로바이더에 종속되지 않습니다. 어떤 에이전트 명령에든 `--provider <name>`을 전달하거나 설정에서 기본값을 지정하세요. 모델 ID는 각 프로바이더 자체 명명 규칙을 따릅니다.

| 프로바이더 | 종류 | API 키 | 비고 |
|---|---|---|---|
| `openrouter` | 클라우드 게이트웨이 | `OPENROUTER_API_KEY` | **기본값.** 수백 개의 모델을 중계; `anthropic/claude-sonnet-4.6` 같은 모델 ID |
| `anthropic` | 클라우드 직접 | `ANTHROPIC_API_KEY` | Claude Messages API, 프롬프트 캐싱 |
| `openai` | 클라우드 직접 | `OPENAI_API_KEY` | GPT 챗 컴플리션 |
| `gemini` | 클라우드 직접 | `GEMINI_API_KEY` / `GOOGLE_API_KEY` | Google Gemini |
| `claude-cli` | 서브프로세스 | — (CLI 세션) | 로컬 `claude` CLI를 JSON 스트림 모드로 위임 |
| `gemini-cli` | 서브프로세스 | — (CLI 세션) | 로컬 `gemini` CLI로 위임 |
| `ollama` | 로컬 | 없음 | `OLLAMA_BASE_URL`(기본값 `http://localhost:11434/v1`) |
| `llamacpp` | 로컬 | 없음 | `LLAMACPP_BASE_URL`(기본값 `http://localhost:8080/v1`) |
| `openai-compat` | 로컬/커스텀 | 없음 | `OPENAI_COMPAT_BASE_URL`(필수, 기본값 없음) |

기본 프로바이더: `openrouter`. **하드코딩된 기본 모델은 없습니다** — 설정 마법사, `[provider] model`, 또는 `--model`로 하나를 지정하세요(그렇지 않으면 에이전트가 "no model configured"라고 보고합니다). 태스크별 라우트는 `[routing.tasks]`에서 재정의하지 않는 한 `[provider]`를 기반으로 상속합니다 — [태스크별 라우팅](../how-to/per-task-routing.md)을 참고하세요.

## 로컬 프로바이더

`ollama`, `llamacpp`, `openai-compat`는 API 키가 필요 없습니다. 설치된 모델은 `veles models <provider>`로 나열하세요(로컬 프로바이더는 항상 실시간).

**로컬 프로바이더에서는 도구 호출이 기본적으로 꺼져 있습니다** — 많은 로컬 모델이 잘못된 형식의 도구 호출을 내보냅니다. 도구를 다룰 수 있는 모델을 선택한 뒤 활성화하세요.

```bash
export VELES_LOCAL_TOOLS=1
veles run --provider ollama --model qwen3:4b-instruct "..."
```

엔드포인트는 `*_BASE_URL` 환경 변수로 재정의하세요([환경 변수](environment-variables.md) 참고).

## CLI 위임 (`claude-cli`, `gemini-cli`)

Claude 또는 Gemini CLI 구독이 있다면, Veles가 그 바이너리를 JSON 스트리밍 모드로 실행하고 코디네이터 역할을 할 수 있습니다 — 별도의 API 키 없이 루프를 로컬 우선으로 유지합니다. Veles 도구는 MCP 브리지가 설정된 경우에만 서브프로세스에 도달합니다.

## 멀티모달 상태 (비전 / 음성-텍스트 변환)

Veles는 `VisionAdapter`와 STT 어댑터 프로토콜(`modules/vision.py`, `modules/stt.py`), 그리고 프로세스 전역 레지스트리를 정의하지만, **구체적인 어댑터는 함께 제공되지 않으며 데몬 시작 시 아무것도 등록되지 않습니다**. 따라서 채널로 보낸 사진이나 음성 메시지는 현재 분석되지 않고 "not configured" 알림을 반환합니다. `vision` 라우팅 태스크는 어댑터가 연결될 때를 위해 존재합니다. [Telegram 연결](../how-to/connect-telegram.md#multimodal-limitation)을 참고하세요.

## 모델 선택

```bash
veles models openrouter            # cached 24h
veles models openrouter --refresh  # bypass cache
veles models ollama                # always live
```

서로 다른 작업에 서로 다른 모델을 사용하려면(압축에는 저렴한 모델, 계획에는 강력한 모델), [태스크별 라우팅](../how-to/per-task-routing.md)을 참고하세요.

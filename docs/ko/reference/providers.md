# 프로바이더

> 🌐 **언어:** **English** · [Русский](../../ru/reference/providers.md)

Veles는 프로바이더에 구애받지 않습니다. 에이전트 명령에 `--provider <name>`을 전달하거나 설정에서 기본값을 지정하세요. 모델 ID는 각 프로바이더 고유의 명명 규칙을 따릅니다.

| 프로바이더 | 종류 | API 키 | 비고 |
|---|---|---|---|
| `openrouter` | 클라우드 게이트웨이 | `OPENROUTER_API_KEY` | **기본값.** 수백 개의 모델 중계; 모델 ID 예시: `anthropic/claude-sonnet-4.6` |
| `anthropic` | 클라우드 직접 | `ANTHROPIC_API_KEY` | Claude Messages API, 프롬프트 캐싱 |
| `openai` | 클라우드 직접 | `OPENAI_API_KEY` | GPT 채팅 완성 |
| `gemini` | 클라우드 직접 | `GEMINI_API_KEY` / `GOOGLE_API_KEY` | Google Gemini |
| `claude-cli` | 서브프로세스 | — (CLI 세션) | JSON 스트림 모드의 로컬 `claude` CLI에 위임 |
| `gemini-cli` | 서브프로세스 | — (CLI 세션) | 로컬 `gemini` CLI에 위임 |
| `ollama` | 로컬 | 없음 | `OLLAMA_BASE_URL` (기본값 `http://localhost:11434/v1`) |
| `llamacpp` | 로컬 | 없음 | `LLAMACPP_BASE_URL` (기본값 `http://localhost:8080/v1`) |
| `openai-compat` | 로컬/커스텀 | 없음 | `OPENAI_COMPAT_BASE_URL` (필수, 기본값 없음) |

기본값: 프로바이더 `openrouter`, 모델 `anthropic/claude-sonnet-4.6`, 컴프레서 `anthropic/claude-haiku-4.5`.

## 로컬 프로바이더

`ollama`, `llamacpp`, `openai-compat`은 API 키가 필요 없습니다. `veles models <provider>`로 설치된 모델 목록을 확인하세요(로컬 프로바이더에서는 항상 실시간으로 조회).

로컬 프로바이더에서는 **도구 호출이 기본적으로 비활성화**되어 있습니다 — 많은 로컬 모델이 잘못된 형식의 도구 호출을 생성하기 때문입니다. 도구 호출 가능한 모델을 선택한 후 활성화하세요:

```bash
export VELES_LOCAL_TOOLS=1
veles run --provider ollama --model qwen3:4b-instruct "..."
```

`*_BASE_URL` 환경 변수로 엔드포인트를 재지정하세요([환경 변수](environment-variables.md) 참조).

## CLI 위임 (`claude-cli`, `gemini-cli`)

Claude 또는 Gemini CLI 구독이 있다면, Veles가 해당 바이너리를 JSON 스트리밍 모드로 실행하고 코디네이터 역할을 수행할 수 있습니다 — 별도의 API 키 없이 루프를 로컬 우선으로 유지합니다. Veles 도구는 MCP 브리지가 설정된 경우에만 서브프로세스에 전달됩니다.

## 멀티모달 지원 현황 (비전 / 음성-텍스트 변환)

Veles는 `VisionAdapter`와 STT 어댑터 프로토콜(`modules/vision.py`, `modules/stt.py`) 및 프로세스 전역 레지스트리를 정의하지만, **구체적인 어댑터는 제공되지 않으며 데몬 시작 시 등록되는 것도 없습니다**. 따라서 채널로 전송된 사진이나 음성 메시지는 현재 분석되지 않고 "설정되지 않음" 안내를 반환합니다. `vision` 라우팅 태스크는 어댑터가 연결되었을 때를 위해 존재합니다. [Telegram 연결](../how-to/connect-telegram.md#multimodal-limitation)을 참조하세요.

## 모델 선택

```bash
veles models openrouter            # cached 24h
veles models openrouter --refresh  # bypass cache
veles models ollama                # always live
```

압축에는 저렴한 모델, 계획에는 강력한 모델 등 작업별로 다른 모델을 사용하려면 [태스크별 라우팅](../how-to/per-task-routing.md)을 참조하세요.

# 프로바이더

> 🌐 **언어:** [English](../../en/reference/providers.md) · [简体中文](../../zh-CN/reference/providers.md) · [繁體中文](../../zh-TW/reference/providers.md) · [日本語](../../ja/reference/providers.md) · **한국어** · [Español](../../es/reference/providers.md) · [Français](../../fr/reference/providers.md) · [Italiano](../../it/reference/providers.md) · [Português (BR)](../../pt-BR/reference/providers.md) · [Português (PT)](../../pt-PT/reference/providers.md) · [Русский](../../ru/reference/providers.md) · [العربية](../../ar/reference/providers.md) · [हिन्दी](../../hi/reference/providers.md) · [বাংলা](../../bn/reference/providers.md) · [Tiếng Việt](../../vi/reference/providers.md)

Veles는 프로바이더에 종속되지 않습니다. 어떤 에이전트 명령에든 `--provider <id>`를 전달하거나 설정에서 기본값을 지정하세요. 모델 ID는 각 프로바이더 자체 명명 규칙을 따릅니다.

## 프로바이더 카탈로그

Veles가 아는 모든 프로바이더는 세 가지 출처로 만들어지는 하나의 카탈로그의 항목입니다.

1. **내장** — 아래 표, Veles와 함께 제공됩니다.
2. **사용자 정의** — `~/.veles/providers.toml`: 항목을 추가해 호스팅되는 OpenAI 호환 API나 직접 운영하는 서버를 등록합니다(자세한 내용은 [나만의 프로바이더 추가](../how-to/configure-providers.md#나만의-프로바이더-추가) 참고). 내장 id를 가진 항목은 해당 프로바이더의 설정(예: `base_url`)을 재정의합니다.
3. **모듈** — 레지스트리 모듈이 프로바이더를 제공합니다(`antigravity-cli`). `[engine] provider`, 라우트 또는 `--provider`에 이름을 지정하면 다음 실행 때 연결된 레지스트리에서 설치됩니다. 선언된 채널과 같은 방식입니다.

`--provider`, `veles models`, 설정 마법사, 라우팅, `veles doctor`는 모두 카탈로그를 읽으므로, 어떤 출처의 프로바이더든 내장 프로바이더가 동작하는 모든 곳에서 동작합니다. 알 수 없는 id는 존재하는 목록을 보여 주는 한 줄 오류가 됩니다. `veles doctor`는 `~/.veles/providers.toml`과 라우트에 지정된 모든 프로바이더도 점검합니다.

| 프로바이더 | 종류 | API 키 | 비고 |
|---|---|---|---|
| `openrouter` | 클라우드 게이트웨이 | `OPENROUTER_API_KEY` | **기본값.** 수백 개의 모델을 중계; `anthropic/claude-sonnet-4.6` 같은 모델 ID |
| `anthropic` | 클라우드 직접 | `ANTHROPIC_API_KEY` | Claude Messages API, 프롬프트 캐싱 |
| `openai` | 클라우드 직접 | `OPENAI_API_KEY` | GPT 챗 컴플리션 |
| `gemini` | 클라우드 직접 | `GEMINI_API_KEY` / `GOOGLE_API_KEY` | Google Gemini |
| `claude-cli` | CLI 위임 | — (CLI 세션) | 로컬 `claude` CLI를 JSON 스트림 모드로 위임 |
| `codex` | CLI 위임 | — (CLI 세션) | 로컬 `codex` CLI에 위임 (ChatGPT 구독) |
| `ollama` | 로컬 | 없음 | `OLLAMA_BASE_URL`(기본값 `http://localhost:11434/v1`) |
| `llamacpp` | 로컬 | 없음 | `LLAMACPP_BASE_URL`(기본값 `http://localhost:8080/v1`) |
| `openai-compat` | 로컬/커스텀 | 선택 사항 `OPENAI_COMPAT_API_KEY` | `OPENAI_COMPAT_BASE_URL`(필수, 기본값 없음) |

`gemini-cli`는 1.2.6에서 제거되었습니다 — Google이 더 이상 개인 계정에 Gemini CLI를 제공하지 않습니다. API 키를 사용하는 `gemini` 또는 `antigravity-cli` 모듈을 사용하세요.

기본 프로바이더: `openrouter`. **하드코딩된 기본 모델은 없습니다** — 설정 마법사, `[engine] model`, 또는 `--model`로 하나를 지정하세요(그렇지 않으면 에이전트가 "no model configured"라고 보고합니다). 태스크별 라우트는 `[routing.tasks]`에서 재정의하지 않는 한 `[engine]`를 기반으로 상속합니다 — [태스크별 라우팅](../how-to/per-task-routing.md)을 참고하세요.

## 로컬 프로바이더

`ollama`, `llamacpp`, `openai-compat`는 API 키가 필요 없습니다. 설치된 모델은 `veles models <provider>`로 나열하세요(로컬 프로바이더는 항상 실시간).

**도구 호출은 백엔드가 알리는 내용으로 감지됩니다**: ollama는 모델별 기능을, llama.cpp 서버는 채팅 템플릿의 기능을 보고합니다. `VELES_LOCAL_TOOLS=1`은 도구 호출을 강제로 켜고 `=0`은 끕니다. 설정하지 않으면 감지합니다.

```bash
veles run --provider ollama --model qwen3:4b-instruct "..."
```

엔드포인트는 `*_BASE_URL` 환경 변수로 재정의하세요([환경 변수](environment-variables.md) 참고).

## CLI 위임 (`claude-cli`, `codex`, `antigravity-cli`)

Claude, ChatGPT 또는 Google 구독이 있다면, Veles가 해당 CLI를 헤드리스로 실행하고 코디네이터 역할을 할 수 있습니다 — 별도의 API 키가 필요 없습니다. `claude-cli`와 `codex`는 내장이며, `antigravity-cli`(`agy` CLI)는 이름을 지정하면 스스로 설치되는 레지스트리 모듈입니다.

위임 대상은 모델일 뿐입니다. Veles 도구는 MCP 브리지를 통해 전달되며, 모든 호출은 Veles의 신뢰 단계(trust ladder)를 거칩니다. 브리지의 설정은 실행 중인 프로세스의 디렉터리인 `.veles/tmp/delegate-<pid>/`에 있으며, 프로세스가 종료되면 삭제됩니다. `agy`는 프로젝트 밖(`~/.veles/tmp/` 아래)의 스크래치 워크스페이스에서 실행되므로 프로젝트 자체의 `.agents/` 설정이 닿지 않으며, 자체 셸 및 파일 도구를 거부하는 게이트 뒤에 있습니다.

`codex`도 프로젝트 밖(`~/.veles/tmp/` 아래)에서 실행되며, 사용자의 codex 설정은 무시되고 자체 도구(셸, 파일 편집, 이미지, 서브에이전트, 브라우저, 웹 검색)는 꺼집니다. Veles는 이 플래그 이름을 프로세스당 한 번 확인하며, 의존하는 플래그의 이름이 바뀐 codex는 실행을 거부합니다. MCP 서버는 파일이 아닌 인수로 전달됩니다. `veles run`에서 codex는 claude보다 Veles의 도구 프로토콜을 덜 안정적으로 따릅니다. 도구를 호출하지 않고 파일을 읽을 수 없다고 답할 수 있습니다 — 다시 물어보거나 도구 이름을 지정하세요("use read_file on …").

## 멀티모달 상태 (비전 / 음성-텍스트 변환)

Veles는 `VisionAdapter`와 STT 어댑터 프로토콜(`modules/vision.py`, `modules/stt.py`), 그리고 프로세스 전역 레지스트리를 정의하지만, **구체적인 어댑터는 함께 제공되지 않으며 데몬 시작 시 아무것도 등록되지 않습니다**. 따라서 채널로 보낸 사진이나 음성 메시지는 현재 분석되지 않고 "not configured" 알림을 반환합니다. `vision` 라우팅 태스크는 어댑터가 연결될 때를 위해 존재합니다. [Telegram 연결](../how-to/connect-telegram.md#multimodal-limitation)을 참고하세요.

## 모델 선택

```bash
veles models openrouter            # cached 24h
veles models openrouter --refresh  # bypass cache
veles models ollama                # always live
```

서로 다른 작업에 서로 다른 모델을 사용하려면(압축에는 저렴한 모델, 계획에는 강력한 모델), [태스크별 라우팅](../how-to/per-task-routing.md)을 참고하세요.

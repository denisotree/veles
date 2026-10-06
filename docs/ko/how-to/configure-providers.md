# 프로바이더 구성 방법

> 🌐 **언어:** [English](../../en/how-to/configure-providers.md) · [简体中文](../../zh-CN/how-to/configure-providers.md) · [繁體中文](../../zh-TW/how-to/configure-providers.md) · [日本語](../../ja/how-to/configure-providers.md) · **한국어** · [Español](../../es/how-to/configure-providers.md) · [Français](../../fr/how-to/configure-providers.md) · [Italiano](../../it/how-to/configure-providers.md) · [Português (BR)](../../pt-BR/how-to/configure-providers.md) · [Português (PT)](../../pt-PT/how-to/configure-providers.md) · [Русский](../../ru/how-to/configure-providers.md) · [العربية](../../ar/how-to/configure-providers.md) · [हिन्दी](../../hi/how-to/configure-providers.md) · [বাংলা](../../bn/how-to/configure-providers.md) · [Tiếng Việt](../../vi/how-to/configure-providers.md)

Veles를 OpenRouter, Anthropic, OpenAI, Gemini, 로컬 모델, 또는 CLI 구독 사이에서 전환합니다. 전체 프로바이더 목록은 [프로바이더 레퍼런스](../reference/providers.md)를 참고하세요.

## 명령마다 프로바이더 선택

```bash
veles run --provider anthropic --model claude-sonnet-4.6 "..."
veles run --provider openai     --model gpt-4o            "..."
veles run --provider gemini     --model gemini-2.5-pro    "..."
```

## 프로젝트 기본값 설정

`<project>/.veles/config.toml`에 기본 설정을 지정하세요.

```toml
[engine]
provider = "openrouter"                 # provider name
model = "anthropic/claude-sonnet-4.6"  # model id
```

또는 `~/.veles/config.toml`에 사용자 전역 기본값을 지정하세요.

```toml
[user]
default_provider = "openrouter"
default_model = "anthropic/claude-sonnet-4.6"
```

## API 키 제공

클라우드 프로바이더는 키가 필요합니다. OS 키체인에 한 번 저장하세요.

```bash
veles secret set OPENROUTER_API_KEY
veles secret set ANTHROPIC_API_KEY
```

…또는 [환경 변수](../reference/environment-variables.md)를 export하세요.

```bash
export OPENROUTER_API_KEY=sk-or-v1-...
```

조회 순서: 키체인(프로젝트 범위) → 키체인(기본) → 환경 변수. 키는 설정 파일에 **절대** 기록되지 않습니다.

## 완전 로컬 모델 사용 (키 없음)

[Ollama](https://ollama.com)를 설치하고, 모델을 받은 뒤 Veles가 그것을 가리키도록 하세요.

```bash
ollama pull qwen3:4b-instruct
veles models ollama                     # confirm it's listed
veles run --provider ollama --model qwen3:4b-instruct "Hello"
```

도구 호출은 서버가 알리는 내용으로 **감지됩니다**. `VELES_LOCAL_TOOLS=1`로 강제로 켜고(`=0`이면 끕니다).

서버가 기본 포트에 있지 않다면 엔드포인트를 재정의하세요.

```bash
export OLLAMA_BASE_URL=http://localhost:11434/v1
export LLAMACPP_BASE_URL=http://localhost:8080/v1
export OPENAI_COMPAT_BASE_URL=http://my-host:8000/v1   # required for openai-compat
```

## 나만의 프로바이더 추가

호스팅되는 OpenAI 호환 API나 직접 운영하는 서버는 `~/.veles/providers.toml`에 항목을 추가하기만 하면 프로바이더가 됩니다 — 코드는 필요 없습니다. id는 테이블 이름입니다.

```toml
[providers.groq]
kind = "openai-api"                          # a hosted API; needs a key
label = "Groq"                               # shown in the wizards (optional)
base_url = "https://api.groq.com/openai/v1"
key_env = ["GROQ_API_KEY"]

[providers.lmstudio]
kind = "local"                               # a server you run; a key is optional
base_url = "http://localhost:1234/v1"
```

그런 다음 내장 프로바이더처럼 사용하세요.

```bash
veles secret set GROQ_API_KEY      # into the keychain, where the groq entry reads it
veles models groq
veles run --provider groq --model llama-3.3-70b-versatile "..."
```

| 키 | 의미 |
|---|---|
| `kind` | `openai-api`(호스팅되는 API) 또는 `local`(직접 운영하는 서버) |
| `base_url` | `/v1`로 끝나는 OpenAI 호환 엔드포인트(또는 프로바이더의 동등한 경로) |
| `base_url_env` | 설정되어 있으면 `base_url`을 재정의하는 환경 변수 |
| `key_env` | 키를 읽어 올 환경 변수 이름. 키체인을 먼저 확인합니다 |
| `label`, `tagline` | 마법사가 표시하는 방식 |
| `tools` | `auto`(기본값), `on`, `off` — 모델에 도구 호출을 허용할지 여부 |

내장 id를 가진 항목(`[providers.ollama]`)은 해당 프로바이더의 설정(예: `base_url`)은 바꾸지만 종류(kind)는 바꾸지 않습니다. 파일이 잘못된 경우 한 번만 보고하고 Veles는 내장 프로바이더로 계속 동작합니다. `veles doctor`가 무엇이 잘못되었는지 알려 줍니다.

널리 쓰이는 API의 출발점입니다 — **Veles 팀이 검증하지 않았으므로**, 현재 엔드포인트는 프로바이더 문서에서 확인하세요.

| id | `base_url` | `key_env` |
|---|---|---|
| `groq` | `https://api.groq.com/openai/v1` | `GROQ_API_KEY` |
| `deepseek` | `https://api.deepseek.com/v1` | `DEEPSEEK_API_KEY` |
| `mistral` | `https://api.mistral.ai/v1` | `MISTRAL_API_KEY` |
| `together` | `https://api.together.xyz/v1` | `TOGETHER_API_KEY` |
| `xai` | `https://api.x.ai/v1` | `XAI_API_KEY` |
| `fireworks` | `https://api.fireworks.ai/inference/v1` | `FIREWORKS_API_KEY` |
| `deepinfra` | `https://api.deepinfra.com/v1/openai` | `DEEPINFRA_API_KEY` |
| `nebius` | `https://api.studio.nebius.com/v1` | `NEBIUS_API_KEY` |
| `cerebras` | `https://api.cerebras.ai/v1` | `CEREBRAS_API_KEY` |
| `zai` | `https://api.z.ai/api/paas/v4` | `ZAI_API_KEY` |
| `moonshot` | `https://api.moonshot.ai/v1` | `MOONSHOT_API_KEY` |
| `lmstudio` (`local`) | `http://localhost:1234/v1` | — |
| `vllm` (`local`) | `http://localhost:8000/v1` | — |

## Claude / ChatGPT / Google 구독으로 위임

`claude` CLI가 인증되어 있다면, Veles가 그것을 구동할 수 있습니다.

```bash
veles run --provider claude-cli "..."
```

ChatGPT 구독의 경우 Codex CLI를 설치하고 한 번 로그인하세요(`codex login`).

```bash
veles run --provider codex --model gpt-6-luna "..."
veles models codex      # the models your account has
```

Google 구독의 경우 Antigravity CLI(`agy`)를 설치하고 한 번 로그인한 뒤 해당 프로바이더 이름을 지정하세요. 그 실행에서 `antigravity-cli` 모듈이 연결된 레지스트리에서 스스로 설치됩니다.

```bash
veles run --provider antigravity-cli --model gemini-3.8-flash-high "..."
veles models antigravity-cli
```

API 키가 필요 없습니다 — CLI가 인증을 처리합니다.

## 사용 가능한 모델 나열

```bash
veles models openrouter            # cloud: cached 24h
veles models openrouter --refresh  # force re-fetch
veles models ollama                # local: always live
```

## 다음

- [서로 다른 작업을 서로 다른 모델로 라우팅하기](per-task-routing.md) — 압축에는 저렴한 모델, 계획에는 강력한 모델.

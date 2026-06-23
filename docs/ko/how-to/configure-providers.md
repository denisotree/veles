# 프로바이더 구성 방법

> 🌐 **언어:** **English** · [Русский](../../ru/how-to/configure-providers.md)

Veles를 OpenRouter, Anthropic, OpenAI, Gemini, 로컬 모델, 또는 CLI 구독으로
전환하세요. 전체 프로바이더 목록: [프로바이더 레퍼런스](../reference/providers.md).

## 명령어별 프로바이더 선택

```bash
veles run --provider anthropic --model claude-sonnet-4.6 "..."
veles run --provider openai     --model gpt-4o            "..."
veles run --provider gemini     --model gemini-2.5-pro    "..."
```

## 프로젝트 기본값 설정

`<project>/.veles/config.toml`에 기본값을 지정합니다:

```toml
[provider]
default = "openrouter:anthropic/claude-sonnet-4.6"
```

또는 `~/.veles/config.toml`에 사용자 전역 기본값을 설정합니다:

```toml
[user]
default_provider = "openrouter"
default_model = "anthropic/claude-sonnet-4.6"
```

## API 키 제공

클라우드 프로바이더에는 키가 필요합니다. OS 키체인에 한 번 저장합니다:

```bash
veles secret set OPENROUTER_API_KEY
veles secret set ANTHROPIC_API_KEY
```

…또는 [환경 변수](../reference/environment-variables.md)를 내보냅니다:

```bash
export OPENROUTER_API_KEY=sk-or-v1-...
```

조회 순서: 키체인(프로젝트 범위) → 키체인(기본값) → 환경 변수. 키는 설정 파일에
**절대** 기록되지 않습니다.

## 완전한 로컬 모델 사용 (키 불필요)

[Ollama](https://ollama.com)를 설치하고, 모델을 받아서 Veles가 사용하도록 설정합니다:

```bash
ollama pull qwen3:4b-instruct
veles models ollama                     # 목록에 있는지 확인
veles run --provider ollama --model qwen3:4b-instruct "Hello"
```

로컬 프로바이더에서 툴 호출은 **기본적으로 비활성화**됩니다. 툴을 지원하는 모델을
선택한 후 활성화합니다:

```bash
export VELES_LOCAL_TOOLS=1
```

서버가 기본 포트가 아닌 경우 엔드포인트를 재정의합니다:

```bash
export OLLAMA_BASE_URL=http://localhost:11434/v1
export LLAMACPP_BASE_URL=http://localhost:8080/v1
export OPENAI_COMPAT_BASE_URL=http://my-host:8000/v1   # openai-compat에 필수
```

## Claude / Gemini CLI 구독에 위임

`claude` 또는 `gemini` CLI가 인증된 경우, Veles가 이를 구동할 수 있습니다:

```bash
veles run --provider claude-cli "..."
veles run --provider gemini-cli "..."
```

API 키가 필요 없습니다 — CLI가 인증을 처리합니다.

## 사용 가능한 모델 목록

```bash
veles models openrouter            # 클라우드: 24시간 캐시
veles models openrouter --refresh  # 강제 재조회
veles models ollama                # 로컬: 항상 실시간
```

## 다음 단계

- [다른 모델에 다른 작업 라우팅](per-task-routing.md) — 압축에는 경량 모델,
  계획에는 강력한 모델.

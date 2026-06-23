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

`<project>/.veles/config.toml`에 기반을 지정하세요.

```toml
[provider]
default = "openrouter"                 # provider name
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

로컬 프로바이더에서는 도구 호출이 **기본적으로 꺼져 있습니다**. 도구를 다룰 수 있는 모델을 선택한 뒤 활성화하세요.

```bash
export VELES_LOCAL_TOOLS=1
```

서버가 기본 포트에 있지 않다면 엔드포인트를 재정의하세요.

```bash
export OLLAMA_BASE_URL=http://localhost:11434/v1
export LLAMACPP_BASE_URL=http://localhost:8080/v1
export OPENAI_COMPAT_BASE_URL=http://my-host:8000/v1   # required for openai-compat
```

## Claude / Gemini CLI 구독으로 위임

`claude`나 `gemini` CLI가 인증되어 있다면, Veles가 그것을 구동할 수 있습니다.

```bash
veles run --provider claude-cli "..."
veles run --provider gemini-cli "..."
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

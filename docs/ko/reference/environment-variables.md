# 환경 변수

> 🌐 **언어:** [English](../../en/reference/environment-variables.md) · [简体中文](../../zh-CN/reference/environment-variables.md) · [繁體中文](../../zh-TW/reference/environment-variables.md) · [日本語](../../ja/reference/environment-variables.md) · **한국어** · [Español](../../es/reference/environment-variables.md) · [Français](../../fr/reference/environment-variables.md) · [Italiano](../../it/reference/environment-variables.md) · [Português (BR)](../../pt-BR/reference/environment-variables.md) · [Português (PT)](../../pt-PT/reference/environment-variables.md) · [Русский](../../ru/reference/environment-variables.md) · [العربية](../../ar/reference/environment-variables.md) · [हिन्दी](../../hi/reference/environment-variables.md) · [বাংলা](../../bn/reference/environment-variables.md) · [Tiếng Việt](../../vi/reference/environment-variables.md)

Veles는 런타임에 다음 변수들을 읽습니다. API 키와 토큰은 OS 키체인(`veles secret set …`)에 저장하는 것이 가장 좋으며, 환경 변수는 폴백이자 재정의 수단입니다.

## 프로바이더 API 키

API 키 조회 순서: OS 키체인(프로젝트 범위) → OS 키체인(기본 범위) → 환경 변수.

| 변수 | 프로바이더 | 비고 |
|---|---|---|
| `OPENROUTER_API_KEY` | openrouter | 기본 프로바이더 |
| `ANTHROPIC_API_KEY` | anthropic | Anthropic 직접 API |
| `OPENAI_API_KEY` | openai | OpenAI 직접 API |
| `GEMINI_API_KEY` | gemini | Google Gemini의 기본 키 |
| `GOOGLE_API_KEY` | gemini | Google Gemini의 폴백 |

`claude-cli`와 `gemini-cli`는 각자의 바이너리를 통해 인증하므로 환경 변수가 없습니다.

## 로컬 프로바이더

| 변수 | 기본값 | 용도 |
|---|---|---|
| `OLLAMA_BASE_URL` | `http://localhost:11434/v1` | Ollama 엔드포인트 |
| `OLLAMA_HOST` | `OLLAMA_BASE_URL`을 따름 | 임베딩용 Ollama 호스트 |
| `LLAMACPP_BASE_URL` | `http://localhost:8080/v1` | llama.cpp 서버 엔드포인트 |
| `OPENAI_COMPAT_BASE_URL` | — (필수) | `openai-compat` 프로바이더의 엔드포인트 |
| `VELES_LOCAL_TOOLS` | off | 로컬 프로바이더에서 도구 호출 활성화(`1`/`true`) |
| `VELES_OLLAMA_EMBED_MODEL` | 프로바이더 기본값 | Ollama 임베딩 모델 재정의 |

## 채널 & 데몬

| 변수 | 기본값 | 용도 |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | — | `veles channel run --channel telegram`용 Telegram 봇 토큰 |
| `VELES_DAEMON_URL` | `http://127.0.0.1:8765` | 채널 게이트웨이가 사용하는 데몬 기본 URL |
| `VELES_DAEMON_TOKEN` | — | 데몬 인증용 베어러 토큰 |

## 경로 & 로케일

| 변수 | 기본값 | 용도 |
|---|---|---|
| `VELES_USER_HOME` | `~` | `~/.veles/`(상태, 캐시, 키체인 인덱스)를 담는 홈 재정의 |
| `VELES_REGISTRY_PATH` | `~/.veles/…` | 멀티 프로젝트 레지스트리 경로 재정의 |
| `VELES_LOCALE` | `[user] language` 또는 `en` | 한 번의 실행 동안 활성 UI 로케일 재정의 |
| `VELES_LOG_LEVEL` | `INFO` | 데몬/로그 상세도(`DEBUG`/`INFO`/`WARNING`/`ERROR`) |

## 동작 & 기능 플래그

| 변수 | 기본값 | 용도 |
|---|---|---|
| `VELES_NO_WIZARD` | off | 첫 실행 마법사 건너뛰기(TTY도 필요) |
| `VELES_MANAGER_MODE` | off | `veles run`에 멀티 에이전트 매니저 강제(`1` on / `0` 킬 스위치) |
| `VELES_VERIFY_MODE` | off | `veles run`에 verify→escalate 패스 강제(`1` on / `0` 킬 스위치) |
| `VELES_FENCED_TOOLS` | off | 펜스/샌드박스 실행 경로로 도구 실행 |
| `VELES_TRUST_AUTO_ALLOW` | off | 신뢰 사다리 우회(CI / 오토파일럿 / 사전 승인된 서브 에이전트) |
| `VELES_SANDBOX_ROOTS` | 프로젝트 + `~/.veles` | 읽기/쓰기 샌드박스 루트의 `:`로 구분된 재정의 |
| `VELES_FETCH_ALLOW_PRIVATE` | off | 도구가 RFC-1918 / 사설 주소를 가져오도록 허용 |
| `VELES_MEMORY_RERANK` | on | 메모리 리콜의 벡터 재정렬(`0`/`false`이면 비활성화) |
| `VELES_WEB_SEARCH_BACKEND` | auto | `research`와 `web_search`의 웹 검색 백엔드 |

## 레지스트리

| 변수 | 용도 |
|---|---|
| `VELES_SKILLS_REGISTRY_URL` | `veles browse skills`의 소스 |
| `VELES_MODULES_REGISTRY_URL` | `veles browse modules`의 소스 |

## 내부 / 테스트

| 변수 | 용도 |
|---|---|
| `VELES_BUNDLE_VERSION` | 내부용이며 직접 설정할 필요가 없습니다 |
| `VELES_REPL_SIMPLE` | `1`로 설정하면 전체 화면 `prompt_toolkit` 앱 대신 단순한 줄 기반 REPL 루프를 강제합니다(제한적인 터미널용 폴백) |

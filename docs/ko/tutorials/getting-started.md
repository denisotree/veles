# 시작하기

> 🌐 **Languages:** **English** · [Русский](../../ru/tutorials/getting-started.md)

이 튜토리얼에서는 Veles를 설치하고, API 키를 등록하고, 첫 프로젝트를 만들고, 첫 프롬프트를 실행합니다. 약 10분 정도 걸립니다. 마치고 나면 대화할 수 있는 동작하는 Veles 프로젝트가 생깁니다.

## 사전 준비

- **Python 3.13+**(Veles는 `>=3.13`을 요구합니다).
- LLM API 키. 여기서는 **OpenRouter**(기본 프로바이더)를 사용하지만, 키가 전혀 필요 없는 완전 로컬 옵션을 포함해 [다른 프로바이더](../reference/providers.md) 중 어느 것이든 됩니다.

## 1. 설치

Veles는 [uv](https://docs.astral.sh/uv/)를 통해 전역 `veles` 명령으로 설치됩니다.

```bash
# install uv if you don't have it
curl -LsSf https://astral.sh/uv/install.sh | sh

# install veles (published as `veles-ai`; the command is `veles`)
uv tool install veles-ai
# …or from a source checkout: uv tool install .

# verify
veles --help
```

나중에 업데이트하려면: `uv tool upgrade veles-ai`.

## 2. Veles에 API 키 등록

[openrouter.ai](https://openrouter.ai)에서 키를 받아 export하세요.

```bash
export OPENROUTER_API_KEY=sk-or-v1-...
```

매 셸마다 다시 export하지 않도록 OS 키체인에 저장할 수도 있습니다.

```bash
veles secret set OPENROUTER_API_KEY
```

(키 없는 완전 로컬 설정을 원하시나요? [Ollama](https://ollama.com)를 설치하고, `ollama pull qwen3:4b-instruct`를 실행한 뒤 아래에서 `--provider ollama`를 사용하세요.)

## 3. 첫 프로젝트 만들기

Veles 프로젝트는 `.veles/` 상태 폴더가 있는 디렉터리일 뿐입니다. 하나 만들어 봅시다.

```bash
mkdir my-notes && cd my-notes
veles init my-notes
```

이 명령은 `AGENTS.md`(프로젝트 컨텍스트), `sources/`와 `wiki/`(기본 [LLM-Wiki 레이아웃](../explanation/layout-packs-and-llm-wiki.md)), 그리고 `.veles/`(머신 상태)를 만듭니다. [프로젝트 레이아웃](../reference/project-layout.md)을 참고하세요.

## 4. 첫 프롬프트 실행

```bash
veles run "Read AGENTS.md and describe this project in three sentences."
```

Veles는 프로젝트 컨텍스트를 로드하고, 모델을 호출하고, 답을 출력합니다. 해당 턴은 프로젝트 메모리에 저장됩니다.

토큰이 도착하는 대로 보려면 `--stream`을, 턴별 진행 상황을 보려면 `--verbose`를 추가하세요.

```bash
veles run --stream "What files exist in this project right now?"
```

## 5. 대화형 REPL 열기

여러 턴에 걸친 대화를 하려면 TUI를 여세요.

```bash
veles tui
```

메시지를 입력하고 Enter를 누르세요. 유용한 키: `Ctrl+D`로 종료, `Shift+Tab`으로 [실행 모드](../explanation/modes.md) 전환, `/help`로 슬래시 명령 목록 보기. 전체 목록은 [TUI 레퍼런스](../reference/tui.md)에 있습니다.

## 6. Veles가 기억하는 내용 확인

모든 실행은 저장됩니다. 세션을 나열하고 검색해 보세요.

```bash
veles sessions list
veles sessions search "three sentences"
```

## 다음으로

- **[지식 베이스 구축하기](building-a-knowledge-base.md)** — 소스를 위키로 가져와 그에 대해 질문하기.
- **[프로바이더 설정](../how-to/configure-providers.md)** — Anthropic, OpenAI, Gemini, 또는 완전 로컬 모델로 전환하기.
- **[아키텍처 개요](../explanation/architecture.md)** — Veles가 내부에서 무엇을 하는지 이해하기.

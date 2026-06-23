# 시작하기

> 🌐 **언어:** **English** · [Русский](../../ru/tutorials/getting-started.md)

이 튜토리얼에서는 Veles를 설치하고, API 키를 제공하고, 첫 번째 프로젝트를 만들고, 첫 번째 프롬프트를 실행합니다. 약 10분 소요됩니다. 완료하면 대화할 수 있는 작동하는 Veles 프로젝트를 갖게 됩니다.

## 사전 요구 사항

- **Python 3.13+** (Veles는 `>=3.13`을 요구합니다).
- LLM API 키. **OpenRouter**(기본 프로바이더)를 사용합니다. API 키가 없는 완전한 로컬 설정을 포함해 [다른 프로바이더](../reference/providers.md)도 사용 가능합니다.

## 1. 설치

Veles는 [uv](https://docs.astral.sh/uv/)를 통해 전역 `veles` 명령으로 설치됩니다:

```bash
# install uv if you don't have it
curl -LsSf https://astral.sh/uv/install.sh | sh

# from the Veles source directory
uv tool install .

# verify
veles --help
```

나중에 업데이트하려면: `uv tool install . --reinstall`.

## 2. API 키 설정

[openrouter.ai](https://openrouter.ai)에서 키를 발급받고 내보내세요:

```bash
export OPENROUTER_API_KEY=sk-or-v1-...
```

매번 셸에서 재내보내지 않으려면 OS 키체인에 저장할 수도 있습니다:

```bash
veles secret set OPENROUTER_API_KEY
```

(키 없이 완전한 로컬 설정을 원하신다면? [Ollama](https://ollama.com)를 설치하고, `ollama pull qwen3:4b-instruct`를 실행한 후 아래에서 `--provider ollama`를 사용하세요.)

## 3. 첫 번째 프로젝트 만들기

Veles 프로젝트는 `.veles/` 상태 폴더가 있는 디렉토리입니다. 하나 만들어 보겠습니다:

```bash
mkdir my-notes && cd my-notes
veles init my-notes
```

이 명령은 `AGENTS.md`(프로젝트 컨텍스트), `sources/`와 `wiki/`(기본 [LLM-Wiki 레이아웃](../explanation/layout-packs-and-llm-wiki.md)), `.veles/`(머신 상태)를 생성합니다. [프로젝트 레이아웃](../reference/project-layout.md)을 참조하세요.

## 4. 첫 번째 프롬프트 실행

```bash
veles run "Read AGENTS.md and describe this project in three sentences."
```

Veles는 프로젝트 컨텍스트를 로드하고, 모델을 호출하고, 답변을 출력합니다. 해당 턴은 프로젝트 메모리에 저장됩니다.

토큰이 도착하는 것을 보려면 `--stream`을 추가하고, 턴별 진행 상황을 보려면 `--verbose`를 추가하세요:

```bash
veles run --stream "What files exist in this project right now?"
```

## 5. 인터랙티브 REPL 열기

멀티턴 대화를 위해 TUI를 열어보세요:

```bash
veles tui
```

메시지를 입력하고 Enter를 누르세요. 유용한 키: `Ctrl+D`로 종료, `Shift+Tab`으로 [실행 모드](../explanation/modes.md) 순환, `/help`로 슬래시 명령 목록 표시. 전체 목록은 [TUI 참조](../reference/tui.md)에서 확인하세요.

## 6. Veles가 기억하는 것 확인

모든 실행은 저장됩니다. 세션을 나열하고 검색하세요:

```bash
veles sessions list
veles sessions search "three sentences"
```

## 다음 단계

- **[지식 베이스 구축하기](building-a-knowledge-base.md)** — 위키에 소스를 인제스트하고 질문합니다.
- **[프로바이더 설정](../how-to/configure-providers.md)** — Anthropic, OpenAI, Gemini, 또는 완전한 로컬 모델로 전환합니다.
- **[아키텍처 개요](../explanation/architecture.md)** — Veles가 내부적으로 무엇을 하는지 이해합니다.

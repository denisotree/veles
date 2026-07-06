# Veles

[![CI](https://github.com/denisotree/veles/actions/workflows/ci.yml/badge.svg)](https://github.com/denisotree/veles/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/veles-ai.svg)](https://pypi.org/project/veles-ai/)
[![License: Apache-2.0](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)
[![Python 3.13+](https://img.shields.io/badge/python-3.13%2B-blue.svg)](pyproject.toml)

<p align="center">
  <a href="README.md">English</a> ·
  <a href="README.zh-CN.md">简体中文</a> ·
  <a href="README.zh-TW.md">繁體中文</a> ·
  <a href="README.ja.md">日本語</a> ·
  <b>한국어</b> ·
  <a href="README.es.md">Español</a> ·
  <a href="README.fr.md">Français</a> ·
  <a href="README.it.md">Italiano</a> ·
  <a href="README.pt-BR.md">Português (BR)</a> ·
  <a href="README.pt-PT.md">Português (PT)</a> ·
  <a href="README.ru.md">Русский</a> ·
  <a href="README.ar.md">العربية</a> ·
  <a href="README.hi.md">हिन्दी</a> ·
  <a href="README.bn.md">বাংলা</a> ·
  <a href="README.vi.md">Tiếng Việt</a>
</p>

**세션을 거듭할수록 더 똑똑해지는 미니멀 CLI 에이전트 프레임워크.**

<p align="center">
  <img src="docs/assets/tui-hero.gif" alt="Veles REPL — 질문을 던지면 프로젝트 자체의 메모리에 기반한 답을 받습니다" width="800">
</p>

매번 처음부터 시작하는 채팅 도구와 달리, Veles는 **구조화된 프로젝트 메모리** — 인사이트, 규칙, 큐레이션된 지식 — 를 유지합니다. 이 지식은 세션을 거치며 축적되어, 오래 사용할수록 에이전트가 더 유용해집니다. *콘텐츠*를 어떻게 구성할지는 플러그형으로 선택할 수 있습니다. 기본값은 Karpathy 스타일의 LLM 위키, 평면 노트, 또는 코드 저장소를 위한 무구조 방식입니다. 깔끔하게 설계되었습니다. god-file 없음, 벤더 종속 없음, 클라우드 동기화 없음.

```bash
uv tool install veles-ai          # installs the `veles` command
veles init && veles run "Summarize the project architecture."
veles        # interactive REPL (bare `veles` with no subcommand)
```

---

## 왜 Veles인가?

**복리처럼 쌓이는 메모리** — 모든 세션은 Curator가 정제하여 프로젝트별 메모리(`.veles/`에 저장되는 인사이트, 행동 규칙, 세션 다이제스트)로 만듭니다. 에이전트는 관련 사실과 과거 결정을 자동으로 떠올리므로, 같은 맥락을 다시 설명할 필요가 없어집니다. 메모리는 *어떤* 콘텐츠 레이아웃에서도 동작합니다.

**플러그형 콘텐츠 레이아웃** — `veles init`은 기본적으로 Karpathy 스타일의 LLM 위키를 스캐폴딩합니다. `--layout notes`는 평면 노트 디렉터리를, `--layout bare`는 아무 구조도 추가하지 않습니다(코드 저장소에 이상적). 커스텀 레이아웃 팩은 `~/.veles/layouts/`에 들어가는 단일 TOML 파일입니다.

**프로바이더에 구애받지 않는 라우팅** — OpenRouter, Anthropic, OpenAI, Gemini, Ollama, llamacpp, 또는 `claude`/`gemini` CLI 구독. 작업 유형(계획 수립, 압축, 인사이트 추출)에 따라 서로 다른 모델로 라우팅할 수 있습니다.

**축적되는 스킬** — 재사용 가능한 프롬프트 블록이 에이전트 도구가 됩니다. 프로젝트의 스킬을 사용자 전역으로 승격하면 어디서나 사용할 수 있습니다. 내장 중복 제거 기능은 스킬이 변질되기 전에 거의 동일한 스킬을 찾아냅니다.

**로컬 우선 + 샌드박스** — 텔레메트리 없음, 클라우드 동기화 없음. 에이전트는 활성 프로젝트 디렉터리만 봅니다. Trust ladder는 모든 민감한 도구 호출마다 확인을 요청하며, CI를 위해 사전 승인할 수 있습니다.

**모놀리식이 아닌 모듈식** — 최소한의 코어(메모리, 에이전트 루프, 프로바이더 프로토콜, 도구 레지스트리). 그 밖의 모든 것 — TUI, 데몬, Telegram 게이트웨이, 심층 리서치, 잡 스케줄러 — 은 선택적이며 로드 가능한 모듈입니다.

---

## 빠른 시작

**요구 사항:** Python 3.13+, macOS / Linux (Windows는 best-effort 지원). 먼저 [uv](https://docs.astral.sh/uv/)를 설치하세요.

```bash
# 1. Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# 2. Install veles (the package is published as `veles-ai`; the command is `veles`)
uv tool install veles-ai
# …or from source:
#   git clone https://github.com/denisotree/veles.git && cd veles && uv tool install .

# 3. Set an API key — OpenRouter is recommended (access to all models, one key)
export OPENROUTER_API_KEY=sk-or-v1-...

# 4. Create a project
mkdir my-project && cd my-project
veles init

# 5. Talk to the agent
veles run "Read AGENTS.md and describe this project."
```

대신 대화형 REPL을 여세요(인자 없는 `veles`도 동일하게 동작합니다):

```bash
veles
```

처음 실행할 때, 설정 마법사가 선호하는 언어, 프로바이더, 프로젝트 이름을 묻습니다.

---

## 프로바이더

| 프로바이더 | 환경 변수 | 비고 |
|---|---|---|
| **OpenRouter** *(권장)* | `OPENROUTER_API_KEY` | Claude, GPT, Gemini, Llama — 키 하나로 수백 개의 모델 |
| Anthropic | `ANTHROPIC_API_KEY` | 직접 API |
| OpenAI | `OPENAI_API_KEY` | 직접 API |
| Gemini | `GEMINI_API_KEY` 또는 `GOOGLE_API_KEY` | 직접 API |
| `claude` CLI | — | Claude 구독을 사용하며 API 키가 필요 없습니다 |
| `gemini` CLI | — | Gemini 구독을 사용하며 API 키가 필요 없습니다 |
| Ollama | — | 로컬 모델, `http://localhost:11434/v1` |
| llamacpp | — | 로컬 모델, `http://localhost:8080/v1` |
| openai-compat | `OPENAI_COMPAT_BASE_URL` | OpenAI 호환 엔드포인트 모두 |

실행마다 재정의:

```bash
veles run --provider anthropic --model anthropic/claude-opus-4-8 "..."
veles run --provider ollama --model llama3.2 "..."
```

환경 변수 대신 OS 키체인에 API 키를 저장:

```bash
veles secret set OPENROUTER_API_KEY    # prompts for value, stores in keychain
```

---

## 핵심 워크플로

### 콘텐츠 레이아웃 선택

```bash
veles init                  # default: Karpathy-style LLM wiki (sources/ + wiki/)
veles init --layout notes   # a single flat notes/ directory
veles init --layout bare    # no content scaffold — code repos, free-form work
```

에이전트 자체의 메모리(`.veles/`에 저장되는 인사이트, 규칙, 세션 다이제스트)는 모든 레이아웃에서 동일하게 동작합니다. 커스텀 팩은 `~/.veles/layouts/<name>/`에 들어가는 하나의 `layout.toml`입니다.

### 지식 베이스 구축 (llm-wiki 레이아웃)

```bash
veles add paper.pdf                   # read a source → write a wiki page
veles add https://example.com/post    # web pages, PDFs, plain text

veles run "What do we know about the authentication design?"
veles curate                          # explicit session → memory consolidation
```

<p align="center">
  <img src="docs/assets/kb-ingest.gif" alt="Veles 지식 베이스 — 소스를 위키 페이지로 수집한 뒤 질문하면 그 페이지를 인용하는 답을 받습니다" width="800">
</p>

Curator는 세션이 끝난 후 자동으로 실행됩니다. 인사이트 추출은 "always prefer X"나 "never do Y" 같은 문구를 포착하여 지속적인 프로젝트 인사이트로 기록합니다.

### 심층 리서치

```bash
veles research "What are the trade-offs between SQLite and PostgreSQL for this use case?"
```

질문을 병렬 하위 질문으로 분해하고, 각각을 탐색한 뒤, 구조화된 보고서로 종합합니다.

### 장기 목표

```bash
veles goal start "Migrate auth module to the new provider" --max-cost-usd 2.00
veles goal list
veles goal checkpoint <id> "Completed step 1: identified all call sites"
```

### 예약 작업

```bash
veles job add --name "weekly-review" --schedule "0 9 * * 1" --prompt "Generate a weekly progress summary"
veles job list
```

---

## 모델 라우팅 (앙상블)

작업 유형마다 다른 모델로 라우팅하세요 — 한 번 설정하면 신경 쓸 필요가 없습니다.

**CLI로:**
```bash
veles route show                                          # current routing table
veles route set compressor anthropic/claude-haiku-4-5    # typed override
veles route reset compressor                             # back to default
```

**`AGENTS.md` 안의 자연어로:**
```markdown
## Routing
Use Opus for planning and architecture decisions.
Haiku is fine for compression and insight extraction.
```

```bash
veles route refresh    # parse the NL hints; typed overrides always win
```

---

## 스킬과 모듈

**스킬**은 자동으로 에이전트 도구가 되는 재사용 가능한 프롬프트 블록(`SKILL.md`)입니다.

```bash
veles skill add https://github.com/org/skill-repo    # install from git
veles skill add ./local-skill-dir                    # or from local path
veles skill list                                     # list with telemetry
veles skill promote my-skill                         # copy to ~/.veles/skills (global)
veles skill dedup                                    # find near-duplicates
veles skill suggest-promote --save                   # propose promotions based on usage
```

**모듈**은 에이전트 라이프사이클(`pre_turn`, `post_turn`, `pre_tool_call`, `post_tool_call`)에 후킹하고 도구 디스패치를 거부할 수 있는 Python 플러그인입니다.

```bash
veles module add https://github.com/org/module-repo
veles module list
```

---

## 대화형 세션 (REPL)

```bash
veles                        # new session (bare `veles` launches the interactive REPL)
veles --resume <id>      # continue a session
```

<p align="center">
  <img src="docs/assets/tui-tour.gif" alt="Veles REPL — 슬래시 인스펙터(/status, /context), 모드 전환, 그리고 명령 팔레트" width="800">
</p>

슬래시 명령이 모든 것을 실시간으로 보여줍니다 — `/status`, `/tokens`, `/context`, `/mode`, `/help` — 그리고 `Shift+Tab`으로 모드(auto / planning / writing / goal)를 순환합니다.

| 키 | 동작 |
|---|---|
| `Enter` | 메시지 보내기 |
| `Shift+Enter` | 작성창에서 줄바꿈 |
| `Ctrl+I` | 도구 활동 인스펙터 토글 |
| `Ctrl+R` | 세션 선택 오버레이 |
| `Ctrl+G` | 현재 초안을 `$EDITOR`로 열기 |
| `Tab` | 슬래시 명령 자동완성 |
| `Ctrl+D` | 종료 |

슬래시 명령: `/help` · `/model` · `/mode` · `/status` · `/tokens` · `/context` · `/wiki` · `/save <slug>` · `/history` · `/insights` · `/rules` · `/daemon` 외 다수.

---

## 데몬 + Telegram

HTTP/WebSocket API를 갖춘 영속 데몬으로 Veles를 실행하세요. 새 프로젝트 디렉터리에서 `veles daemon start`는 설정 과정을 안내합니다 — 프로젝트를 초기화하고, 데몬을 활성화하고, **채널을 연결**합니다. 먼저 채널 *유형*을 고르고(현재 플랫폼은 Telegram뿐이지만, 이 선택기는 새 채널이 등록되는 이음새입니다), 그다음 해당 채널의 필드(봇 토큰, 화이트리스트)를 채웁니다. TUI를 먼저 열 필요가 없습니다.

<p align="center">
  <img src="docs/assets/daemon-setup.gif" alt="veles daemon start — 데몬을 띄우고 Telegram 채널을 연결하는 마법사(채널 유형 먼저, 그다음 토큰과 화이트리스트)" width="800">
</p>

```bash
veles daemon start                        # wizard (fresh dir) → starts on 127.0.0.1:8765
veles daemon status                       # is it running?
veles daemon list                         # daemons across all projects
```

인자 없는 `veles daemon`은 라이브 제어판 — 프로젝트 → 데몬 → 채널의 트리 — 를 엽니다. 데몬을 시작, 중지, 재시작, 삭제하고, 모든 프로젝트에 걸쳐 채널을 추가/제거(동일한 채널-유형-우선 흐름, 키 `c`)할 수 있으며, 전부 키보드로 조작합니다:

<p align="center">
  <img src="docs/assets/daemon-panel.gif" alt="veles daemon — 제어판 TUI: 프로젝트 → 데몬 → 채널 트리와 시작/중지/재시작/삭제, 그리고 인라인 채널 관리" width="800">
</p>

동일한 채널 마법사는 이미 실행 중인 프로젝트에서 독립적으로도 사용할 수 있습니다(`veles channel add`).

API 엔드포인트: `POST /v1/runs`로 프롬프트 제출, `WS /v1/runs/{id}/events`로 응답 스트리밍, `GET /v1/sessions`로 세션 목록 조회. `GET /v1/health`를 제외한 모든 엔드포인트는 `Authorization: Bearer <token>`을 요구합니다(`veles daemon token add <name>`으로 토큰 발급).

각 Telegram 사용자는 영속 세션을 갖습니다. `veles channel list-sessions` / `reset-session`으로 매핑을 관리하세요.

---

## 멀티 프로젝트

```bash
veles project list                       # registered projects
veles project switch <slug>              # print the absolute path
cd $(veles project switch <slug>)        # jump to a project

veles subproject init frontend           # create a child project
veles subproject suggest --save          # agent-detected topic clusters → proposals
```

---

## 신뢰와 안전

모든 민감한 도구 호출(셸 실행, 파일 쓰기, URL 가져오기)은 확인을 요청합니다:

```
Tool 'run_shell' wants to execute. Allow?
  [1] Once  [2] Always for this project  [3] Always everywhere  [4] Refuse
```

CI나 장시간 자율 실행을 위한 사전 승인:

```bash
veles trust set run_shell --scope project   # pre-grant for this project
veles autopilot enable --until +2h          # temporary trust bypass (audit-logged)
veles autopilot disable
```

에이전트는 활성 프로젝트 디렉터리만 봅니다 — 다른 프로젝트, 심링크 탈출, `..` 경로 이동은 모두 차단됩니다.

---

## 내보내기 / 가져오기

```bash
veles export full ./backup.tar.gz        # full backup: memory, sessions, telemetry
veles export template ./template.tar.gz  # sanitised template (no sources/sessions/PII)
veles import ./backup.tar.gz --into ./new-dir
```

---

## CLI 레퍼런스

| 명령 | 용도 |
|---|---|
| `veles init [name]` | 새 프로젝트 생성 |
| `veles run "<prompt>"` | 단일 턴 에이전트 실행 |
| `veles` | 대화형 REPL |
| `veles add <file\|url>` | 소스 수집 → 위키 페이지 |
| `veles research "<question>"` | 다각도 심층 리서치 |
| `veles curate` | 세션을 위키로 통합 |
| `veles sessions {list,show,delete,search}` | 세션 관리 |
| `veles skill {list,add,remove,promote,demote,dedup,suggest-promote}` | 스킬 관리 |
| `veles tool {list,show,promote}` | 도구 관리 |
| `veles module {list,add,remove}` | 플러그인 관리 |
| `veles route {show,set,reset,refresh}` | 모델 라우팅 |
| `veles goal {list,show,start,checkpoint,pause,resume,done,cancel}` | 장기 목표 |
| `veles job {list,add,show,pause,resume,trigger,remove,history}` | 예약 작업 |
| `veles dream` | 백그라운드 메모리 통합 사이클 |
| `veles project {list,add,remove,switch}` | 멀티 프로젝트 레지스트리 |
| `veles subproject {init,list,switch,remove,suggest}` | 자식 프로젝트 |
| `veles trust {list,set,revoke,clear}` | 신뢰 권한 부여 |
| `veles autopilot {enable,disable,status}` | 임시 신뢰 우회 |
| `veles secret {set,get,list,delete}` | OS 키체인 시크릿 |
| `veles daemon {start,stop,status,list,restart,delete,session,token}` | HTTP/WS 데몬 |
| `veles channel {run,list-sessions,reset-session}` | 외부 채널 게이트웨이 |
| `veles mcp {list,test}` | 외부 MCP 서버 |
| `veles models <provider>` | 프로바이더 모델 목록 |
| `veles doctor` | 상태 점검 |
| `veles export / import` | 프로젝트 백업 및 이전 |

모든 명령에는 `--help`가 있습니다.

---

## 문서

전체 문서 — Diátaxis 방식으로 구성(튜토리얼 · 사용 가이드 · 레퍼런스 · 설명):

- **한국어:** [`docs/ko/index.md`](docs/ko/index.md)

다른 언어: 모든 문서 페이지 상단의 🌐 전환기를 사용하세요.

---

## 기여하기

기여를 적극 환영합니다 — Veles는 **확장하도록 설계되었습니다**. 코어는 작게 유지되며(에이전트 루프 + 프로젝트 메모리 + 프로바이더 프로토콜), 그 밖의 거의 모든 것은 플러그형 확장 지점이므로, 기능을 추가할 때 코어를 건드릴 일은 거의 없습니다:

- **프로바이더 어댑터** (`src/veles/adapters/`) — 새 모델 백엔드 연결.
- **스킬** — `extends:` 상속을 갖춘 재사용 가능한 프롬프트 블록과 도구로, 프로젝트에서 사용자 전역으로 승격 가능.
- **도구** — 에이전트가 작성하고 재사용하는 타입 지정 Python으로, `<project>/.veles/tools/`에 위치.
- **레이아웃 팩** — `~/.veles/layouts/<name>/`의 단일 `layout.toml`이 콘텐츠 레이아웃 전체를 정의.
- **모듈 후크** — `pre_turn` / `post_turn` 후크(`src/veles/core/modules.py`)를 통한 관측성, 로깅, 정책.
- **채널 & MCP 서버** — 새 게이트웨이와 외부 도구 소스.
- **로케일** — `src/veles/locales/`의 번역.

```bash
git clone https://github.com/denisotree/veles.git && cd veles
uv sync                              # runtime + dev dependencies
uv run pytest                        # the full suite (3200+ tests, no network)
uv run ruff check src tests && uv run mypy
```

코드베이스는 의도적으로 분해되어 있습니다 — 단일 책임, god-file 없음. PR을 열기 전에 [`CONTRIBUTING.md`](CONTRIBUTING.md)에서 규약을, [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md)를 읽어 보세요. 첫 기여로 좋은 것들: 프로바이더 어댑터, 워크플로 스킬, 모듈 후크, 로케일 파일.

---

## 라이선스

특허 부여를 포함한 Apache 2.0 — [`LICENSE`](LICENSE)와 [`NOTICE`](NOTICE)를 참조하세요.

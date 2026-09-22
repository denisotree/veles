# 설정 레퍼런스

> 🌐 **언어:** [English](../../en/reference/configuration.md) · [简体中文](../../zh-CN/reference/configuration.md) · [繁體中文](../../zh-TW/reference/configuration.md) · [日本語](../../ja/reference/configuration.md) · **한국어** · [Español](../../es/reference/configuration.md) · [Français](../../fr/reference/configuration.md) · [Italiano](../../it/reference/configuration.md) · [Português (BR)](../../pt-BR/reference/configuration.md) · [Português (PT)](../../pt-PT/reference/configuration.md) · [Русский](../../ru/reference/configuration.md) · [العربية](../../ar/reference/configuration.md) · [हिन्दी](../../hi/reference/configuration.md) · [বাংলা](../../bn/reference/configuration.md) · [Tiếng Việt](../../vi/reference/configuration.md)

Veles는 두 개의 TOML 파일과 일련의 상태 디렉터리로 설정됩니다. 시크릿(API 키, 봇 토큰)은 이 파일들에 **절대** 기록되지 않으며, OS 키체인이나 환경 변수에 저장됩니다([환경 변수](environment-variables.md) 참고).

## 상태가 저장되는 위치

| 경로 | 범위 | 내용 |
|---|---|---|
| `~/.veles/` | 사용자 전역 | `config.toml`, 신뢰 권한, 프로젝트 간 스킬/도구, 모델 캐시, 로케일, 레지스트리 |
| `<project>/.veles/` | 프로젝트 로컬 | `project.toml`, `config.toml`, `memory.db`, 프로젝트 스킬/도구, 계획, 런타임 임시 파일 |
| `<project>/AGENTS.md` | 프로젝트 | 에이전트에 주입되는 컨텍스트 파일(`CLAUDE.md` / `GEMINI.md`로 심볼릭 링크됨) |
| `<project>/wiki/`, `sources/` | 프로젝트 | 사용자 콘텐츠(기본 LLM-Wiki 레이아웃) |

`VELES_USER_HOME`은 `~`를 다른 위치로 바꿉니다(사용자 상태가 `<override>/.veles/`에 저장됨). 전체 트리는 [프로젝트 레이아웃](project-layout.md)을 참고하세요.

---

## 사용자 설정 — `~/.veles/config.toml`

첫 실행 마법사가 작성하며, 직접 손으로 편집해도 안전합니다.

```toml
[user]
language = "en"                  # "en" | "ru" — UI string locale
default_provider = "openrouter"  # default provider for new projects
default_model = "anthropic/claude-sonnet-4.6"
first_project_name = "myorg"     # recorded by the wizard
tui_theme = "everforest"         # everforest | dracula | gruvbox | tokyo-night | catppuccin

[permissions]                    # optional per-tool policy
fetch_url  = "approval_required" # allow | approval_required | always_confirm
write_file = "always_confirm"

[routing.tasks]                  # optional user-scope routing (see below)
compressor = "openrouter:anthropic/claude-haiku-4.5"

[mcp.servers.my-server]          # optional user-scope MCP servers
transport = "stdio"
command = "python"               # executable only — arguments go in `args`
args = ["-m", "my_mcp_server"]
```

| 키 | 타입 | 용도 |
|---|---|---|
| `[user] language` | `"en"` \| `"ru"` | UI 문자열 로케일(`VELES_LOCALE`로 재정의 가능) |
| `[user] default_provider` | string | 프로바이더가 지정되지 않았을 때 사용 |
| `[user] default_model` | string | 모델이 지정되지 않았을 때 사용 |
| `[user] tui_theme` | string | 기본 TUI 색상 테마 |
| `[permissions] <tool>` | policy | 도구별 권한 정책([신뢰 & 샌드박스](../explanation/trust-and-sandbox.md) 참고) |

---

## 프로젝트 설정 — `<project>/.veles/config.toml`

```toml
[engine]
provider = "openrouter"                               # provider name for the main agent + routing base
model = "anthropic/claude-sonnet-4.6"                # model id (omit to require --model or the user default_model)
request_timeout_s = 180                              # 선택. 한 번의 응답을 기다리는 시간
max_retries = 1                                      # 선택. 요청당 재시도 횟수

[routing.tasks]                  # per-task overrides (highest priority below explicit flags)
default    = "openrouter:anthropic/claude-sonnet-4.6"
compressor = "openrouter:anthropic/claude-haiku-4.5"
insights   = "openrouter:anthropic/claude-haiku-4.5"
advisor    = "openrouter:anthropic/claude-opus-4.8"
vision     = "openai:gpt-4o"
embedding  = "openai:text-embedding-3-small"

[daemon]                         # the unnamed/"default" daemon
enabled = true
host = "127.0.0.1"
port = 8765
autostart = false

[daemon.api]                     # a named daemon session ("api")
provider = "anthropic"
model = "claude-opus-4.8"
host = "127.0.0.1"
port = 8801
mode = "auto"

[channels.telegram]              # global channels (served by the unnamed daemon)
enabled = true
whitelist = ["@alice", "123456789"]

[daemon.api.channels.telegram]   # channels bound to a named daemon session
enabled = true
whitelist = ["@bob"]

[mcp.servers.github]             # external MCP servers (project scope)
transport = "stdio"             # stdio | http | sse
command = "npx"                  # executable only — arguments go in `args`
args = ["-y", "@modelcontextprotocol/server-github"]
env = { GITHUB_TOKEN = "${GITHUB_TOKEN}" }   # ${VAR} interpolates from the environment
```

### 섹션

| 섹션 | 용도 |
|---|---|
| `[engine]` | 메인 에이전트와 라우팅 캐스케이드의 기반 프로바이더(`provider` = 프로바이더 이름) + 모델(`model` = 모델 ID), 그리고 클라이언트 예산 `request_timeout_s` / `max_retries` |
| `[routing.tasks]` | 태스크별 `provider:model` 재정의 — [태스크별 라우팅](../how-to/per-task-routing.md) 참고 |
| `[permissions]` | 도구별 권한 정책(프로젝트 범위) |
| `[daemon]` | 이름 없는/"기본" 데몬의 바인드 + 자동 시작 |
| `[daemon.<name>]` | 이름 있는 데몬 세션(자체 model/provider/host/port/mode) |
| `[channels.<type>]` | 이름 없는 데몬이 서비스하는 채널(예: `telegram`) |
| `[daemon.<name>.channels.<type>]` | 이름 있는 데몬 세션에 바인딩된 채널 |
| `[mcp.servers.<name>]` | 외부 MCP 서버(도구 소스) |

`[routing.tasks]`의 태스크 유형: `default`, `curator`, `compressor`, `insights`, `skills`, `advisor`, `vision`, `embedding`.

> `AGENTS.md`의 자연어 라우팅 힌트는 자동 생성되는 `routing.nl.toml`로 파싱됩니다. 명시적인 `[routing.tasks]` 항목이 언제나 우선합니다. 다시 파싱하려면 `veles route refresh`를 실행하세요. [태스크별 라우팅](../how-to/per-task-routing.md)을 참고하세요.

### 응답을 얼마나 기다릴지, 몇 번 재시도할지

```toml
[engine]
request_timeout_s = 180
max_retries = 1
```

둘 다 **클라이언트** 파라미터이므로 `[engine.request.<provider>]`가 아니라 `[engine]`
바로 아래에 평평하게 놓입니다. 그쪽은 요청 *본문*이고, 타임아웃은 본문으로 전달되지
않습니다.

지정하지 않으면 타임아웃은 모델 id에서 유추됩니다. 추론 계열은 900초, 그 계열의
`flash`/`mini` 변형은 450초, 나머지는 120초입니다. 이 유추는 구조적으로 약합니다.
**이름은 계열을 설명할 뿐이고, 응답 시간은 그것을 서빙하는 백엔드가 정하기
때문입니다.** 같은 id가 어떤 백엔드에서는 33 tok/s, 다른 백엔드에서는 0.8 tok/s로
돕니다. 유추된 값이 당신의 실행에 맞지 않으면 직접 지정하세요. 그 숫자가 두 번
같은 의미를 갖게 하려면 아래의 백엔드 고정도 함께 쓰십시오.

`max_retries`가 중요한 이유도 같습니다. 설정하지 않으면 SDK가 두 번 재시도하므로
450초 타임아웃은 한 턴에 최대 1350초가 되고, 넉넉해 보이던 예산을 날리기에 충분합니다.
`0`은 정당한 값이며 키를 생략한 것과 같지 않습니다.

두 값의 우선순위는 코드의 명시적 인자 → `[engine]` → 모델별 기본값입니다. 양수가
아닌 값(`max_retries`는 음이 아닌 정수가 아닌 값)은 파일 이름을 알려주는
`ConfigError`로 중단됩니다.

**적용 범위:** 현재 이 키들을 읽는 것은 OpenRouter 어댑터뿐입니다. Anthropic, OpenAI,
Gemini 클라이언트는 두 파라미터 없이 생성되며 키를 무시합니다.

### 백엔드 고정 및 기타 요청 본문 키

`[engine.request.<provider>]` 는 해당 제공자의 요청 본문에 **그대로** 전달됩니다.
Veles 는 상위 제공자의 스키마를 모델링하지 않으므로, 제공자가 받아들이는 옵션은
Veles 가 알게 될 때까지 기다릴 필요 없이 바로 동작합니다.

```toml
[engine.request.openrouter.provider]
order = ["GMICloud"]
allow_fallbacks = false

[engine.request.openrouter.reasoning]
enabled = false
```

섹션 키는 **제공자 이름**(`openrouter`, `anthropic`, `openai`, `gemini`,
`ollama`, `llamacpp`, `openai-compat`)입니다. 덕분에 하나의 프로젝트 설정이 백엔드
교체를 견딥니다. OpenRouter 의 `provider` 블록을 llama.cpp 로 보내면 400 이므로,
각 백엔드는 자기 하위 섹션만 읽습니다. 섹션을 선언하지 않으면 요청은 이전과
바이트 단위로 동일합니다.

**필요한 상황: 재현 가능한 측정.** OpenRouter 같은 중계는 하나의 모델을 서로 다른
양자화의 여러 백엔드로 분산하므로, 같은 입력에 대한 두 번의 실행이 입력과 무관한
이유로 달라질 수 있습니다. `session_id` 기반 스티키 라우팅은 하나의 대화를 하나의
백엔드에 묶어 주지만, 그것이 **어느** 백엔드인지는 알려 주지 않습니다.

`quantizations` 가 아니라 `order` 로 고정하십시오. 2026-09-18 기준
`z-ai/glm-5.3-flash` 의 엔드포인트는 29 개입니다: `fp8` 16 개, `fp4` 3 개,
`nvfp4` 1 개, **양자화를 전혀 밝히지 않는 것이 9 개**, `bf16` 은 하나도 없습니다.
따라서 `quantizations = ["fp8"]` 로도 후보가 16 개 남고 컨텍스트 길이는 262144 에서
1310720 토큰까지 제각각인 반면, 원소가 하나뿐인 `order` 와
`allow_fallbacks = false` 를 함께 쓰면 백엔드가 확정됩니다. 모델의 엔드포인트
목록:

```bash
curl -s https://openrouter.ai/api/v1/models/<author>/<slug>/endpoints \
  -H "Authorization: Bearer $OPENROUTER_API_KEY" | jq '.data.endpoints[]
  | {provider_name, quantization, context_length}'
```

고정은 측정용 프로젝트에만 두십시오. 운영에는 가용성과 폴백을 유지하는 스티키
라우팅이 맞습니다.

**고정이 유지됐는지 확인.** 모델 호출마다 의도와 결과가 모두
`.veles/traces.jsonl` 에 기록됩니다. `request_extra` 는 보낸 내용,
`upstream_provider` 는 실제로 응답한 백엔드입니다. 한 줄이면 됩니다:

```bash
jq -r 'select(.session_id=="<sid>") | .upstream_provider' .veles/traces.jsonl | sort -u
```

두 줄 이상이면 그 실행은 백엔드를 섞은 것입니다. 같은 레코드에
`reasoning_tokens`(예산 중 추론에 쓰인 양)과 `est_cost_usd`(상위 제공자가 보고하는
실제 청구 비용)도 들어 있습니다.

**오류는 의도적으로 요란합니다.** 제공자 이름 오타나 섹션 경로 오타
(`[engine.reqest.…]`)는 파일과 알려진 제공자 목록을 알려 주는 `ConfigError` 로
실행을 중단시킵니다. 전선까지 닿지 못한 고정은, 그것을 작성한 목적인 측정을 조용히
무효로 만들기 때문입니다. 제공자 하위 섹션 *안쪽* 의 키는 Veles 가 검사하지
않습니다. 상위 제공자가 검사하기 때문입니다: OpenRouter 는 모르는 키에
`400 provider: Unrecognized key: "quantization"`, 맞는 대상이 없는 값에
`404 No endpoints found …` 를 돌려줍니다.

### 대화 기록 보관 기간

**요청하지 않으면 아무것도 삭제되지 않습니다.** `turn_retention_days` 의 기본값은
`0` 이며, 모든 대화 턴을 영구히 보관합니다. `memory.db` 에 상한을 두려면 일수를
지정하십시오:

```toml
[memory]
turn_retention_days = 90   # 0(기본값)은 전부 보관
```

켜면 그보다 오래된 원본 대화 턴이 삭제됩니다. 거기서 추출된 **인사이트** 와 규칙은
설정과 무관하게 영구히 보관됩니다. 대화 기록은 원재료이고 인사이트는 그것을 읽은
목적입니다.

기록이 삭제되려면 **두** 조건이 모두 성립해야 합니다. 보관 기간보다 오래되었고,
**그리고** 큐레이터가 이미 그 세션을 처리했어야 합니다. 큐레이터가 아직 도달하지
못한 세션은 아무리 오래되었어도 삭제되지 않습니다. 그렇지 않으면 아무것도 배우기
전에 기록을 없애 버리게 됩니다.

켰을 때의 비용: `veles sessions search` 는 보관 기간 안의 텍스트만 찾습니다.
`veles sessions list` 는 오래된 실행도 계속 보여 줍니다. 세션 행(id, 제목,
타임스탬프)은 남고 메시지 본문만 사라지기 때문입니다. 정리는 `veles dream` 중
인사이트 추출 이후에 수행됩니다.

### 로그 로테이션

`traces.jsonl` 과 `events.jsonl` 은 50 MB 에서 `<이름>.<unix_ts>` 로 로테이션되며,
가장 최근 **10** 개만 보관됩니다. 그보다 오래된 것은 다음 로테이션 때 삭제됩니다.
이전에는 영구히 쌓였습니다.

일반적인 사용량에서는 설정할 것이 없습니다. 트레이스 레코드당 약 530 바이트,
에이전트 턴당 약 1.1 KB 의 이벤트이므로 첫 로테이션까지 수년이 걸립니다. 이 설정이
있는 이유는, 정책 없는 무한 증가란 결국 그 장비를 물려받는 사람이 발견하게 되는
누수이기 때문입니다.

### 이미지

채널로 전송된 사진은 턴이 시작되기 전에 설명이 생성됩니다. 사용되는 모델은
`[routing.tasks].vision` 이 가리키는 모델이며, 명시적인 라우트가 없으면 `[engine]`
모델입니다. 따라서 멀티모달 엔진이라면 별도 설정이 전혀 필요 없습니다.

`[vision] mode` 가 파이프라인을 고릅니다:

- `model`(기본값) — 비전 모델이 이미지를 설명합니다.
- `ocr` — Tesseract 만 사용. 로컬, 무료, LLM 호출 없음. 텍스트 스캔에 적합합니다.
- `ocr+model` — 먼저 그대로의 텍스트, 이어서 모델의 설명.
- `off` — 아무것도 읽지 않습니다. 파일은 그래도 저장되며, 에이전트가 원하면 직접
  `image_describe` / `image_ocr` 를 호출할 수 있습니다.

엔진이 텍스트 전용이면 `[vision] model` 을 지정하십시오. 비전을 지원하는 제공자면
무엇이든 됩니다. 로컬 서버도 포함입니다: `ollama:llava`, `llamacpp:…`,
`openai-compat:…`.

### `project.toml`

`<project>/.veles/project.toml`은 변경 불가능한 프로젝트 메타데이터(`name`, `created_at`, `schema_version`, `layout`)를 담습니다. 보통 직접 손으로 편집하지 않습니다.

---

## AGENTS.md

프로젝트 루트에 있는 프로젝트 컨텍스트 파일입니다. 시작 시 에이전트의 시스템 프롬프트에 주입되며, `CLAUDE.md`와 `GEMINI.md`로 심볼릭 링크되어 해당 디렉터리에서 실행되는 `claude`나 `gemini` CLI가 동일한 컨텍스트를 가져갑니다.

작게 유지하세요. 보조 `.md` 파일(예: `wiki/INDEX.md`)은 필요할 때 동적으로 로드됩니다. 필수 섹션은 `veles schema validate`로 검증하세요. [레이아웃 팩 & LLM-Wiki](../explanation/layout-packs-and-llm-wiki.md)를 참고하세요.

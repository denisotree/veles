# 설정 레퍼런스

> 🌐 **언어:** **English** · [Русский](../../ru/reference/configuration.md)

Veles는 두 개의 TOML 파일과 여러 상태 디렉터리로 설정됩니다. API 키, 봇 토큰 등의 시크릿은 이 파일에 **절대** 저장하지 않습니다 — OS 키체인이나 환경 변수에 보관합니다([환경 변수](environment-variables.md) 참고).

## 상태 저장 위치

| 경로 | 범위 | 내용 |
|---|---|---|
| `~/.veles/` | 사용자 전역 | `config.toml`, 신뢰 권한, 크로스 프로젝트 스킬/도구, 모델 캐시, 로케일, 레지스트리 |
| `<project>/.veles/` | 프로젝트 로컬 | `project.toml`, `config.toml`, `memory.db`, 프로젝트 스킬/도구, 플랜, 런타임 아티팩트 |
| `<project>/AGENTS.md` | 프로젝트 | 에이전트에 주입되는 컨텍스트 파일(`CLAUDE.md` / `GEMINI.md`로 심볼릭 링크) |
| `<project>/wiki/`, `sources/` | 프로젝트 | 사용자 콘텐츠(기본 LLM-Wiki 레이아웃) |

`VELES_USER_HOME`을 설정하면 `~`를 재정의합니다(사용자 상태가 `<override>/.veles/`에 저장됩니다).
전체 트리는 [프로젝트 레이아웃](project-layout.md)을 참고하세요.

---

## 사용자 설정 — `~/.veles/config.toml`

최초 실행 마법사가 작성합니다. 직접 편집해도 안전합니다.

```toml
[user]
language = "en"                  # "en" | "ru" — UI 문자열 로케일
default_provider = "openrouter"  # 새 프로젝트의 기본 프로바이더
default_model = "anthropic/claude-sonnet-4.6"
first_project_name = "myorg"     # 마법사가 기록
tui_theme = "everforest"         # everforest | dracula | gruvbox | tokyo-night | catppuccin

[permissions]                    # 선택적 도구별 정책
fetch_url  = "approval_required" # approval_required | always_confirm | always_allow
write_file = "always_confirm"

[routing.tasks]                  # 선택적 사용자 범위 라우팅(아래 참고)
compressor = "openrouter:anthropic/claude-haiku-4.5"

[mcp.servers.my-server]          # 선택적 사용자 범위 MCP 서버
transport = "stdio"
command = "python"               # 실행 파일만 — 인수는 `args`에 작성
args = ["-m", "my_mcp_server"]
```

| 키 | 타입 | 설명 |
|---|---|---|
| `[user] language` | `"en"` \| `"ru"` | UI 문자열 로케일(`VELES_LOCALE`로 재정의 가능) |
| `[user] default_provider` | string | 프로바이더를 지정하지 않을 때 사용하는 기본값 |
| `[user] default_model` | string | 모델을 지정하지 않을 때 사용하는 기본값 |
| `[user] tui_theme` | string | 기본 TUI 색상 테마 |
| `[permissions] <tool>` | policy | 도구별 권한 정책([신뢰 & 샌드박스](../explanation/trust-and-sandbox.md) 참고) |

---

## 프로젝트 설정 — `<project>/.veles/config.toml`

```toml
[provider]
default = "openrouter:anthropic/claude-sonnet-4.6"   # 메인 에이전트 + 라우팅의 기반

[routing.tasks]                  # 작업별 재정의(명시적 플래그 다음으로 높은 우선순위)
default    = "openrouter:anthropic/claude-sonnet-4.6"
compressor = "openrouter:anthropic/claude-haiku-4.5"
insights   = "openrouter:anthropic/claude-haiku-4.5"
advisor    = "openrouter:anthropic/claude-opus-4.8"
vision     = "openai:gpt-4o"
embedding  = "openai:text-embedding-3-small"

[daemon]                         # 이름 없는/"default" 데몬
enabled = true
host = "127.0.0.1"
port = 8765
autostart = false

[daemon.api]                     # 이름 있는 데몬 세션("api")
provider = "anthropic"
model = "claude-opus-4.8"
host = "127.0.0.1"
port = 8801
mode = "auto"

[channels.telegram]              # 전역 채널(이름 없는 데몬이 서비스)
enabled = true
whitelist = ["@alice", "123456789"]

[daemon.api.channels.telegram]   # 이름 있는 데몬 세션에 바인딩된 채널
enabled = true
whitelist = ["@bob"]

[mcp.servers.github]             # 외부 MCP 서버(프로젝트 범위)
transport = "stdio"             # stdio | http | sse
command = "npx"                  # 실행 파일만 — 인수는 `args`에 작성
args = ["-y", "@modelcontextprotocol/server-github"]
env = { GITHUB_TOKEN = "${GITHUB_TOKEN}" }   # ${VAR}은 환경에서 보간
```

### 섹션

| 섹션 | 설명 |
|---|---|
| `[provider]` | 메인 에이전트와 라우팅 캐스케이드의 기본 프로바이더/모델 |
| `[routing.tasks]` | 작업별 `provider:model` 재정의 — [작업별 라우팅](../how-to/per-task-routing.md) 참고 |
| `[permissions]` | 도구별 권한 정책(프로젝트 범위) |
| `[daemon]` | 이름 없는/"default" 데몬의 바인딩 + 자동 시작 설정 |
| `[daemon.<name>]` | 이름 있는 데몬 세션(고유한 모델/프로바이더/호스트/포트/모드) |
| `[channels.<type>]` | 이름 없는 데몬이 서비스하는 채널(예: `telegram`) |
| `[daemon.<name>.channels.<type>]` | 이름 있는 데몬 세션에 바인딩된 채널 |
| `[mcp.servers.<name>]` | 외부 MCP 서버(도구 소스) |

`[routing.tasks]`의 작업 유형: `default`, `curator`, `compressor`, `insights`,
`skills`, `advisor`, `vision`, `embedding`.

> `AGENTS.md`의 자연어 라우팅 힌트는 자동 생성된 `routing.nl.toml`로 파싱됩니다.
> 명시적인 `[routing.tasks]` 항목이 항상 우선합니다. `veles route refresh`로 재파싱하세요.
> [작업별 라우팅](../how-to/per-task-routing.md) 참고.

### `project.toml`

`<project>/.veles/project.toml`에는 변경 불가한 프로젝트 메타데이터(`name`,
`created_at`, `schema_version`, `layout`)가 저장됩니다. 일반적으로 직접 편집하지 않습니다.

---

## AGENTS.md

프로젝트 루트에 위치한 프로젝트 컨텍스트 파일입니다. 시작 시 에이전트의 시스템 프롬프트에 주입되며, 해당 디렉터리에서 실행된 `claude` 또는 `gemini` CLI가 같은 컨텍스트를 사용할 수 있도록 `CLAUDE.md`와 `GEMINI.md`로 심볼릭 링크됩니다.

파일을 작게 유지하세요 — 보조 `.md` 파일(예: `wiki/INDEX.md`)은 필요 시 동적으로 로드됩니다.
필수 섹션은 `veles schema validate`로 검증하세요. [레이아웃 팩 & LLM-Wiki](../explanation/layout-packs-and-llm-wiki.md) 참고.

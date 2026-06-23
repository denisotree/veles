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
[provider]
default = "openrouter"                               # provider name for the main agent + routing base
model = "anthropic/claude-sonnet-4.6"                # model id (omit to require --model or the user default_model)

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
| `[provider]` | 메인 에이전트와 라우팅 캐스케이드의 기반 프로바이더(`default` = 프로바이더 이름) + 모델(`model` = 모델 ID) |
| `[routing.tasks]` | 태스크별 `provider:model` 재정의 — [태스크별 라우팅](../how-to/per-task-routing.md) 참고 |
| `[permissions]` | 도구별 권한 정책(프로젝트 범위) |
| `[daemon]` | 이름 없는/"기본" 데몬의 바인드 + 자동 시작 |
| `[daemon.<name>]` | 이름 있는 데몬 세션(자체 model/provider/host/port/mode) |
| `[channels.<type>]` | 이름 없는 데몬이 서비스하는 채널(예: `telegram`) |
| `[daemon.<name>.channels.<type>]` | 이름 있는 데몬 세션에 바인딩된 채널 |
| `[mcp.servers.<name>]` | 외부 MCP 서버(도구 소스) |

`[routing.tasks]`의 태스크 유형: `default`, `curator`, `compressor`, `insights`, `skills`, `advisor`, `vision`, `embedding`.

> `AGENTS.md`의 자연어 라우팅 힌트는 자동 생성되는 `routing.nl.toml`로 파싱됩니다. 명시적인 `[routing.tasks]` 항목이 언제나 우선합니다. 다시 파싱하려면 `veles route refresh`를 실행하세요. [태스크별 라우팅](../how-to/per-task-routing.md)을 참고하세요.

### `project.toml`

`<project>/.veles/project.toml`은 변경 불가능한 프로젝트 메타데이터(`name`, `created_at`, `schema_version`, `layout`)를 담습니다. 보통 직접 손으로 편집하지 않습니다.

---

## AGENTS.md

프로젝트 루트에 있는 프로젝트 컨텍스트 파일입니다. 시작 시 에이전트의 시스템 프롬프트에 주입되며, `CLAUDE.md`와 `GEMINI.md`로 심볼릭 링크되어 해당 디렉터리에서 실행되는 `claude`나 `gemini` CLI가 동일한 컨텍스트를 가져갑니다.

작게 유지하세요. 보조 `.md` 파일(예: `wiki/INDEX.md`)은 필요할 때 동적으로 로드됩니다. 필수 섹션은 `veles schema validate`로 검증하세요. [레이아웃 팩 & LLM-Wiki](../explanation/layout-packs-and-llm-wiki.md)를 참고하세요.

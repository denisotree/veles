# CLI 레퍼런스

> 🌐 **언어:** **English** · [Русский](../../ru/reference/cli.md)

Veles의 모든 커맨드, 서브커맨드, 플래그를 설명합니다. 항상 최신 상태인 정확한 시그니처는 `veles <command> --help`로 확인하세요. 이 페이지는 `src/veles/cli/_parsers/`의 인수 파서를 반영합니다.

```
veles [--no-wizard] <command> [subcommand] [options]
```

- `--no-wizard` — `~/.veles/config.toml`이 없어도 최초 실행 설정 마법사를 건너뜁니다 (TTY 여부와 `VELES_NO_WIZARD=1`로도 제어됩니다).
- 인수 없이 실행하면 `veles`는 대화형 [TUI](tui.md)를 시작합니다.

대부분의 에이전트 커맨드는 하단에 나열된 [공통 에이전트 루프 플래그](#공통-에이전트-루프-플래그)와 [프로바이더 이름](#프로바이더-이름)을 지원합니다.

---

## 프로젝트 라이프사이클

### `veles init [name]`
현재 디렉터리에 새 Veles 프로젝트를 생성합니다(`.veles/` 상태 디렉터리 + `AGENTS.md` + 선택한 레이아웃 팩의 콘텐츠 스캐폴드).

| 플래그 | 기본값 | 설명 |
|---|---|---|
| `name` (위치 인수) | 현재 디렉터리 이름 | 프로젝트 이름 |
| `--layout <name>` | `llm-wiki` | 콘텐츠 스캐폴드에 사용할 레이아웃 팩(`llm-wiki`, `notes`, `bare`, 또는 `~/.veles/layouts/`의 커스텀 팩) |
| `--force` | off | `.veles/`가 이미 존재해도 재생성 |

### `veles schema {validate,edit,fix}`
`AGENTS.md`(프로젝트 컨텍스트 파일)를 검증하거나 편집합니다.

- `validate` — 필수 H2 섹션이 있는지 확인합니다.
- `edit` — `$EDITOR`(기본값 `vi`)로 `AGENTS.md`를 열고, 종료 시 검증합니다.
- `fix` — LLM 마법사를 통해 누락된 섹션을 대화형으로 추가합니다.

### `veles self-doc [refresh|show]`
프로젝트 자동 문서화(`wiki/self-doc/overview.md`)를 생성하고 표시합니다.
`veles self-doc`만 실행하면 현재 페이지를 보여주며, `refresh`는 재생성합니다.

### `veles doctor`
사용자 전역 상태와 활성 프로젝트에 대한 상태 검사를 실행합니다. 활성 프로젝트 없이도 동작합니다.

| 플래그 | 기본값 | 설명 |
|---|---|---|
| `--json` | off | JSON 형식으로 리포트 출력 |
| `--strict` | off | 경고가 있으면 비정상 종료(CI 게이팅용) |

### `veles export {full,template} <path>`
프로젝트를 `.tar.gz` 번들로 패킹합니다. [백업 및 공유](../how-to/backup-and-share.md)를 참고하세요.

- `full <path>` — 전체 프로젝트(`.veles/` + `AGENTS.md`), 런타임 임시 파일 제외.
- `template <path>` — 정제된 서브셋(스키마 + 스킬 + 모듈 + 세션 외 위키 페이지). `memory.db`, `sources/`, `sessions/`, `trust` 권한을 제거하고 텍스트에서 개인 정보를 삭제합니다.

### `veles import <path>`
`veles export`로 생성된 번들을 복원합니다.

| 플래그 | 기본값 | 설명 |
|---|---|---|
| `path` (위치 인수) | — | 번들 경로(`.tar.gz`) |
| `--into <dir>` | 현재 디렉터리 | 대상 디렉터리 |
| `--force` | off | 대상에 이미 `.veles/`가 있어도 덮어쓰기 |

---

## 에이전트 실행

### `veles run "<prompt>"`
단일 프롬프트를 메모리 저장과 큐레이터/학습 트리거와 함께 처음부터 끝까지 실행합니다. [공통 에이전트 루프 플래그](#공통-에이전트-루프-플래그) 외에 추가로 지원하는 플래그:

| 플래그 | 기본값 | 설명 |
|---|---|---|
| `--resume <session_id>` | 새 세션 | 기존 세션 이어서 실행 |
| `--manager` | off | 멀티 에이전트 매니저를 통해 분해(`VELES_MANAGER_MODE=1`도 가능) |
| `--plan` | off | 계획 모드: 읽기/검색/초안 작성만 허용, 변경 차단 |
| `--no-agents-md` | off | `AGENTS.md`를 시스템 프롬프트에 주입하지 않음 |
| `--no-index` | off | `wiki/INDEX.md`를 주입하지 않음 |
| `--no-compress` | off | 슬라이딩 윈도우 컨텍스트 압축 비활성화 |
| `--no-curator` | off | 이번 실행에서 큐레이터 트리거 비활성화 |
| `--no-insights` | off | 실행 후 인사이트 추출 비활성화 |
| `--no-proposer` | off | 서브프로젝트 제안 자동 트리거 비활성화 |
| `--no-route-refresh` | off | `AGENTS.md`에서 자연어 라우팅 갱신 비활성화 |
| `--no-suggest-promote` | off | 자동 승격 제안자 비활성화 |
| `--compressor-model <id>` | 라우팅 기본값 | 압축 모델 재정의 |
| `--compress-threshold-tokens <n>` | `50000` | 압축을 트리거하는 히스토리 크기 |

### `veles tui`
대화형 REPL을 엽니다. [TUI 레퍼런스](tui.md)를 참고하세요. 공통 에이전트 루프 플래그, `--resume`, 위의 `--no-*` 주입/압축 플래그와 함께 다음도 지원합니다:

| 플래그 | 기본값 | 설명 |
|---|---|---|
| `--theme <name>` | 설정값 또는 `everforest` | 색상 테마(everforest, dracula, gruvbox, tokyo-night, catppuccin) |

### `veles add <source>`
소스(로컬 파일 또는 `http(s)://` URL)를 읽어 위키 페이지로 합성합니다. 공통 에이전트 루프 플래그를 지원합니다.

### `veles curate`
큐레이터 패스를 한 번 실행합니다: 처리되지 않은 세션을 `wiki/sessions/` 페이지로 압축합니다.

| 플래그 | 기본값 | 설명 |
|---|---|---|
| `--limit <n>` | 소수의 기본값 | 이번 실행에서 처리할 최대 세션 수 |

공통 에이전트 루프 플래그도 지원합니다.

### `veles research "<question>"`
딥 리서치: 하위 질문으로 분해 → 웹을 병렬 탐색 → 인용이 포함된 리포트 합성.

| 플래그 | 기본값 | 설명 |
|---|---|---|
| `--max-subquestions <n>` | `4` | 병렬 리서치 각도 수 |

공통 에이전트 루프 플래그도 지원합니다.

### `veles dream`
백그라운드 메모리 통합 사이클을 한 번 실행합니다(인사이트 → 스킬 중복 제거 → 승격 제안 → 위키 린트, 선택적으로 LLM 통합).

| 플래그 | 기본값 | 설명 |
|---|---|---|
| `--include-consolidation` | off | 비용이 큰 LLM 통합 실행(API 키 필요) |
| `--dry-run` | off | 모든 단계 실행하되 `wiki/state` 쓰기는 건너뜀 |
| `--skip-insights` / `--skip-dedup` / `--skip-promote` / `--skip-lint` | off | 개별 단계 건너뜀 |
| `--consolidation-model <id>` | `anthropic/claude-haiku-4.5` | 통합 모델 재정의 |
| `--provider <name>` | `openrouter` | 통합 서브 에이전트의 프로바이더 |
| `--project-root <path>` | 자동 탐색 | 프로젝트 재정의 |

---

## 지식: 스킬, 도구, 모듈

### `veles skill {list,show,add,remove,promote,demote,dedup,suggest-promote}`

| 서브커맨드 | 설명 |
|---|---|
| `list` | 활성 프로젝트의 스킬 목록 조회(텔레메트리 포함) |
| `show <name>` | 스킬의 `SKILL.md` 출력 |
| `add <source> [--name N] [--scope project\|user] [-y]` | git URL 또는 로컬 경로에서 설치 |
| `remove <name> [--scope project\|user] [-y]` | 설치된 스킬 삭제 |
| `promote <name> [--keep-telemetry]` | 프로젝트 스킬을 사용자 범위(`~/.veles/skills/`)로 복사 |
| `demote <name> [-y]` | 사용자 스킬을 활성 프로젝트로 복사 |
| `dedup [--mode auto\|embedding\|tfidf] [--embedding-threshold f] [--tfidf-threshold f]` | 유사 중복 스킬 탐색 |
| `suggest-promote [--save] [--min-uses n] [--min-success-rate f]` | 자동 승격 기준을 충족하는 스킬 목록 조회 |

### `veles tool {list,show,promote}`

| 서브커맨드 | 설명 |
|---|---|
| `list` | 이 프로젝트의 `memory.db`에 등록된 도구 목록 조회 |
| `show <name>` | 도구의 매니페스트 + 텔레메트리 출력 |
| `promote <name> [-y]` | 프로젝트 도구를 `~/.veles/tools/`로 이동(크로스 프로젝트) |

### `veles module {list,show,add,remove}`

| 서브커맨드 | 설명 |
|---|---|
| `list` | 설치된 모듈 목록 조회 |
| `show <name>` | 모듈의 매니페스트 출력 |
| `add <source> [--name N] [-y]` | git URL 또는 로컬 경로에서 모듈 설치 |
| `remove <name> [-y]` | 설치된 모듈 삭제 |

### `veles browse {modules,skills} [query]`
큐레이팅된 레지스트리를 탐색합니다.

| 플래그 | 기본값 | 설명 |
|---|---|---|
| `query` (위치 인수) | `""` | 부분 문자열 필터 |
| `--source <url>` | 공식 레지스트리 | 레지스트리 소스 재정의 |
| `--json` | off | JSON 출력 |

---

## 세션 & 메모리

### `veles sessions {list,show,delete,search}`

| 서브커맨드 | 설명 |
|---|---|
| `list [--limit n]` | 최근 세션 목록 조회(기본값 20개) |
| `show <session_id>` | 세션의 전체 턴 히스토리 출력 |
| `delete <session_id>` | 세션과 해당 턴 삭제 |
| `search "<query>" [--limit n] [--role user\|assistant\|both\|all] [--since 7d]` | 턴 콘텐츠 전문 검색(FTS5) |

---

## 멀티 프로젝트

### `veles project {list,add,remove,switch}`

| 서브커맨드 | 설명 |
|---|---|
| `list` | 등록된 프로젝트 목록 조회(최근 순) |
| `add <path> [--slug S]` | 기존 프로젝트 디렉터리 등록 |
| `remove <slug>` | 프로젝트 등록 해제(파일은 유지) |
| `switch <slug>` | 프로젝트의 절대 경로 출력(`cd $(veles project switch <slug>)` 형태로 사용) |

### `veles subproject {init,list,switch,remove,suggest}`

| 서브커맨드 | 설명 |
|---|---|
| `init <subdir> [--name N] [--description D]` | 서브프로젝트 생성 및 등록 |
| `list` | 활성 프로젝트의 서브프로젝트 목록 조회 |
| `switch <slug>` | 서브프로젝트의 절대 경로 출력 |
| `remove <slug>` | 서브프로젝트 등록 해제 |
| `suggest [--save] [--min-pages n] [--min-similarity f]` | 주제 클러스터를 탐지하여 서브프로젝트 제안 |

---

## 라우팅 & 모델

### `veles route {show,set,reset,refresh}`
작업별 앙상블 라우팅 — 각 작업 유형(`default`, `curator`, `compressor`, `insights`, `skills`, `advisor`, `vision`, `embedding`)을 처리하는 `provider:model` 지정. [작업별 라우팅](../how-to/per-task-routing.md) 참고.

| 서브커맨드 | 설명 |
|---|---|
| `show` | 활성 프로젝트의 라우팅 테이블(해석된 값) 출력 |
| `set <task> <provider:model>` | 특정 작업을 지정 스펙에 고정 |
| `reset [task]` | 하나의 작업(또는 모든 작업)을 기본값으로 재설정 |
| `refresh [--force]` | `AGENTS.md`에서 자연어 라우팅 힌트 재파싱 |

### `veles models <provider>`
프로바이더의 모델 목록을 조회합니다. 클라우드 프로바이더(openrouter/openai/gemini)는 24시간 캐시됩니다. 로컬 프로바이더는 항상 실시간 조회합니다.

| 플래그 | 기본값 | 설명 |
|---|---|---|
| `provider` (위치 인수) | — | [프로바이더 이름](#프로바이더-이름) 중 하나 |
| `--refresh` | off | 디스크 캐시 무시(클라우드 전용) |
| `--json` | off | `{provider, source, models}`를 JSON으로 출력 |

---

## 장기 실행 작업

### `veles goal {list,show,start,checkpoint,pause,resume,done,cancel}`
예산과 체크포인트가 있는 장기 목표.

| 서브커맨드 | 설명 |
|---|---|
| `list [--status active\|paused\|completed\|blocked\|cancelled]` | 목표 목록 조회 |
| `show <id> [--json]` | 목표 하나 조회 |
| `start "<objective>" [--scope S] [--done-when D] [--max-steps n] [--max-cost-usd f] [--max-wall-time-s n] [--forbid A]… [--approve A]…` | 목표 생성 |
| `checkpoint <id> "<note>" [--evidence U] [--cost-usd f] [--no-advance]` | 진행 상황 추가 |
| `pause <id>` / `resume <id>` | 일시 중지 / 재개 |
| `done <id> [--evidence E]` / `cancel <id> [--reason R]` | 완료 / 취소 |

### `veles job {add,list,show,pause,resume,trigger,remove,history,tick}`
예약된 에이전트 작업.

| 서브커맨드 | 설명 |
|---|---|
| `add --name N --schedule S --prompt P [--repeat n] [--context-from JOB_ID] [--deliver-to TARGET]` | 작업 생성(스케줄: cron, `<N><s\|m\|h\|d>`, 또는 ISO 타임스탬프) |
| `list [--json]` / `show <id>` | 작업 검사 |
| `pause <id>` / `resume <id>` / `trigger <id>` / `remove <id>` | 라이프사이클 |
| `history <id> [--limit n]` | 최근 실행 히스토리 |
| `tick` | 예정된 작업을 동기적으로 한 번 실행(데몬 불필요; 에이전트 루프 플래그 지원) |

---

## 보안 & 접근 제어

### `veles trust {list,set,revoke,clear}`
민감한 도구(`run_shell`, `write_file`, `fetch_url` 등)에 대한 영구 권한. [보안](../how-to/security-and-permissions.md) 참고.

| 서브커맨드 | 설명 |
|---|---|
| `list` | 권한 목록 조회(사용자 + 프로젝트 범위) |
| `set <tool> [--scope project\|user]` | 도구에 권한 부여 |
| `revoke <tool> [--scope project\|user\|both]` | 권한 제거 |
| `clear [--scope project\|user\|all]` | 특정 범위의 권한 초기화 |

### `veles autopilot {enable,disable,status}`
신뢰 계층 프롬프트를 자동으로 허용하는 시간 제한 창.

| 서브커맨드 | 설명 |
|---|---|
| `enable --until <DUR>` | 창 열기(`+30m`, `+2h`, `+1d`, 또는 ISO 형식 `2026-05-12T18:00:00Z`) |
| `disable` | 즉시 창 닫기 |
| `status` | 자동 조종 활성 여부 확인 |

### `veles secret {set,get,list,delete}`
OS 키체인 기반 시크릿(API 키, 봇 토큰).

| 서브커맨드 | 설명 |
|---|---|
| `set <name> [value]` | 저장(값 생략 시 대화형 입력 또는 stdin) |
| `get <name> [--reveal] [--no-env-fallback]` | 조회(기본적으로 환경 변수 대체 사용) |
| `list` | 설정된 표준 시크릿 목록 조회 |
| `delete <name>` | 시크릿 삭제 |

---

## 데몬 & 채널

### `veles daemon [start|stop|status|list|restart|delete|session|token]`
HTTP+WS 데몬을 실행/제어합니다. `veles daemon`만 실행하면 **데몬 선택기** TUI(프로젝트 → 데몬 → 채널)가 열립니다. [데몬으로 실행하기](../how-to/run-as-daemon.md) 참고.

| 서브커맨드 | 설명 |
|---|---|
| `start [--host H] [--port P] [--foreground] [--name N]` | 데몬 시작(기본적으로 백그라운드 분리) |
| `stop [--name N]` / `status [--name N]` | 중지 / 검사 |
| `list` | 모든 프로젝트의 데몬 목록 조회 |
| `restart [target] [--name N]` | 같은 호스트/포트에서 중지 후 재시작 |
| `delete <target> [-y]` | 중지 후 레지스트리에서 제거 |
| `session create <name> [--host H] --port P [--model M] [--provider P] [--mode M]` | 이름 있는 데몬 세션 선언 |
| `session list [--all]` / `session delete <name>` | 이름 있는 세션 관리 |
| `token add <name>` / `token list` / `token remove <name>` | 베어러 토큰 CRUD |

`start`는 공통 에이전트 루프 플래그도 지원합니다. 데몬의 경우 `--model` / `--provider`는 기본적으로 프로젝트 설정을 따르며 데몬 실행 중에는 변경되지 않습니다.

### `veles channel {list,run,list-sessions,reset-session,add,remove}`
데몬에 연결되는 외부 채팅 게이트웨이(Telegram 등). [Telegram 연결하기](../how-to/connect-telegram.md) 참고.

| 서브커맨드 | 설명 |
|---|---|
| `list` | 등록된 채널 플랫폼 + 세션 수 목록 조회 |
| `run --channel telegram [--bot-token T] [--daemon-url U] [--daemon-token T]` | 포그라운드에서 게이트웨이 시작 |
| `list-sessions [--channel C]` | `chat_id → session_id` 매핑 조회 |
| `reset-session <chat_id> [--channel C]` | 매핑 삭제(다음 메시지부터 새 세션 시작) |
| `add [--channel C] [--session S]` | 데몬에 채널 연결(마법사; 자격증명 → 키체인) |
| `remove <channel> [--session S]` | 채널 바인딩 제거 |

---

## MCP (외부 도구 서버)

### `veles mcp {list,test}`
`[mcp.servers.*]`에 설정된 외부 MCP 서버를 검사합니다. [외부 MCP 서버](../how-to/external-mcp-servers.md) 참고.

| 서브커맨드 | 설명 |
|---|---|
| `list [--connect-timeout f]` | 설정된 서버, 연결 상태, 도구 수 조회 |
| `test <server>` | 서버 하나에 연결하여 도구 목록 조회 |

---

## 공통 에이전트 루프 플래그

`run`, `add`, `tui`, `curate`, `research`, `job tick`, `daemon start`에서 사용 가능:

| 플래그 | 기본값 | 설명 |
|---|---|---|
| `--model <id>` | `anthropic/claude-sonnet-4.6` (tui: 저장됨) | 모델 ID |
| `--provider <name>` | `openrouter` | 프로바이더(아래 참고) |
| `--max-tokens-total <n>` | `100000` | 누적 토큰 예산; `0`이면 제한 없음 |
| `--max-iterations <n>` | `30` | 턴당 최대 도구 호출 반복 횟수 |
| `--stream` | off | 응답을 토큰 단위로 스트리밍 |
| `--verbose` / `-v` | off | 턴별 진행 상황을 stderr에 출력 |
| `--project-root <path>` | cwd에서 자동 탐색 | 다른 위치의 프로젝트에서 작업 |

## 프로바이더 이름

`openrouter` (기본값) · `anthropic` · `openai` · `gemini` · `claude-cli` ·
`gemini-cli` · `ollama` · `llamacpp` · `openai-compat`

로컬 프로바이더(`ollama`, `llamacpp`, `openai-compat`)는 API 키가 필요 없습니다. [프로바이더 레퍼런스](providers.md)와 [프로바이더 설정하기](../how-to/configure-providers.md)를 참고하세요.

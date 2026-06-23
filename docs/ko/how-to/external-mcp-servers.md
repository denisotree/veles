# 외부 MCP 서버 연결 방법

> 🌐 **언어:** **English** · [Русский](../../ru/how-to/external-mcp-servers.md)

Veles는 [MCP](https://modelcontextprotocol.io/) **클라이언트**입니다. 외부 MCP 서버에 연결하여 해당 서버의 도구를 마치 내장 도구처럼 에이전트에 노출할 수 있습니다 (GitHub, 라이브러리 문서, 웹 검색, 직접 만든 서비스 등).

## 서버 설정

`<project>/.veles/config.toml` (또는 사용자 전역 `~/.veles/config.toml`)에 `[mcp.servers.<name>]` 블록을 추가합니다. `<name>`은 `[A-Za-z0-9][A-Za-z0-9_-]{0,31}` 패턴과 일치해야 하며, 각 도구 이름의 일부가 됩니다. 지원하는 전송 방식은 `stdio`(기본값), `http`, `sse` 세 가지입니다.

| 키 | 전송 방식 | 기본값 | 설명 |
|---|---|---|---|
| `transport` | — | `"stdio"` | `stdio` \| `http` \| `sse` |
| `command` | stdio (필수) | — | 실행할 프로그램 — **프로그램 경로만, 인수는 포함하지 않음** |
| `args` | stdio | `[]` | 인수 목록, 항목당 하나의 토큰 |
| `env` | stdio | `{}` | 서브프로세스에 추가할 환경 변수 (기존 환경에 병합) |
| `url` | http/sse (필수) | — | 서버 엔드포인트 |
| `timeout_s` | — | `120` | 단일 도구 호출에 허용되는 시간 |
| `connect_timeout_s` | — | `30` | 초기 연결에 허용되는 시간 |
| `enabled` | — | `true` | `false`로 설정하면 항목은 유지하되 연결을 건너뜀 |

`command`, `args`, `env`, `url`의 문자열 값에는 환경 변수에서 `${VAR}`를 보간합니다 (설정되지 않은 변수는 빈 문자열이 되며 경고가 출력됨) — 시크릿은 파일에 직접 넣지 마세요.

> **`command`와 `args` 구분.** Veles는 프로그램을 셸 없이 직접 실행하므로, 실행 파일과 인수는 **별도** 필드에 작성합니다. `command = "npx"`, `args = ["-y", "pkg"]`처럼 쓰세요 — `command = "npx -y pkg"`처럼 쓰면 **안 됩니다**.

### stdio (로컬 서브프로세스)

```toml
[mcp.servers.github]
transport = "stdio"
command = "npx"
args = ["-y", "@modelcontextprotocol/server-github"]
env = { GITHUB_TOKEN = "${GITHUB_TOKEN}" }
```

직접 실행하는 서버도 동일한 방식으로 동작합니다 — `command`/`args`를 해당 서버로 지정하면 됩니다:

```toml
[mcp.servers.mytools]
transport = "stdio"
command = "python"
args = ["-m", "my_mcp_server"]
```

### API 키가 필요한 서버 (context7)

[Context7](https://context7.com)은 최신 라이브러리 문서를 제공합니다. 키를 인수로 전달하여 `${VAR}`로 파일에 직접 노출되지 않도록 합니다:

```toml
[mcp.servers.context7]
transport = "stdio"
command = "npx"
args = ["-y", "@upstash/context7-mcp", "--api-key", "${CONTEXT7_API_KEY}"]
```

```bash
export CONTEXT7_API_KEY=...   # 이후 veles 시작
```

### http / sse (원격)

```toml
[mcp.servers.search]
transport = "http"            # 스트리밍 HTTP; SSE 엔드포인트에는 "sse" 사용
url = "https://mcp.example.com/mcp"
```

> **커스텀 헤더 미지원 (현재).** `http`/`sse` 전송 방식은 `url`만 전송합니다 — Veles는 `Authorization` 헤더를 추가할 수 없습니다. 키가 필요한 원격 서버의 경우, `args`/`env`에 키를 넣는 `stdio`(예: `npx`) 방식을 사용하거나, URL에 키를 포함하는 엔드포인트를 활용하세요.

## 특정 도구 숨기기

`[mcp] disabled_tools`를 설정합니다 — 각 서버와 건너뛸 도구 이름을 매핑하는 테이블입니다:

```toml
[mcp]
disabled_tools = { github = ["delete_repository"], search = ["raw_query"] }
```

## 검사 및 테스트

```bash
veles mcp list              # 설정된 모든 서버: 전송 방식, 상태, 도구 수
veles mcp test github       # 특정 서버에 연결하여 도구 목록 출력
```

`veles mcp list`는 항상 종료 코드 0으로 반환됩니다 — 검사 도구이며, 헬스 게이트가 아닙니다.
`veles mcp test`는 연결 실패 시 1, 알 수 없는 서버 이름일 때 2로 종료됩니다.

## 도구가 나타나는 방식

설정이 완료되면 서버는 다음 `veles run` / TUI / 데몬 시작 시 **자동으로** 마운트됩니다 — 별도의 "MCP 활성화" 플래그는 없으며, 설정 파일의 존재 자체가 스위치 역할을 합니다. 각 도구는 `mcp_<server>_<tool>` 형태로 일반 레지스트리에 등록되며, 에이전트가 내장 도구처럼 호출할 수 있습니다. 스키마는 (이름/길이 제한, 제어 문자 제거 등) 정제되므로 신뢰할 수 없는 서버가 프롬프트에 주입할 수 없습니다. 도구 힌트는 신뢰 단계에 매핑됩니다: 파괴적 도구는 항상 확인을 요청하고, 읽기 전용 도구는 확인 없이 실행되며, 나머지는 일반적인 [신뢰](security-and-permissions.md) 흐름을 따릅니다 — 매번 묻지 않으려면 `veles trust set`으로 상시 승인을 부여하세요.

## 오류 처리

연결에 실패한 서버 — `command` 누락, 잘못된 `url`, 또는 기타 잘못된 설정 — 는 경고로 기록되고 건너뜁니다. 시작이나 에이전트 실행을 막지 않습니다. `veles mcp list`를 다시 실행하여 상태와 오류를 확인하세요.

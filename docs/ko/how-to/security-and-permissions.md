# 보안 관리 방법: 신뢰, 자동 조종, 시크릿

> 🌐 **언어:** [English](../../en/how-to/security-and-permissions.md) · [简体中文](../../zh-CN/how-to/security-and-permissions.md) · [繁體中文](../../zh-TW/how-to/security-and-permissions.md) · [日本語](../../ja/how-to/security-and-permissions.md) · **한국어** · [Español](../../es/how-to/security-and-permissions.md) · [Français](../../fr/how-to/security-and-permissions.md) · [Italiano](../../it/how-to/security-and-permissions.md) · [Português (BR)](../../pt-BR/how-to/security-and-permissions.md) · [Português (PT)](../../pt-PT/how-to/security-and-permissions.md) · [Русский](../../ru/how-to/security-and-permissions.md) · [العربية](../../ar/how-to/security-and-permissions.md) · [हिन्दी](../../hi/how-to/security-and-permissions.md) · [বাংলা](../../bn/how-to/security-and-permissions.md) · [Tiếng Việt](../../vi/how-to/security-and-permissions.md)

Veles는 위험한 작업을 **신뢰 계층**으로 제어하고, 파일 접근을 샌드박스로 격리하며, 시크릿을 OS 키체인에 안전하게 보관합니다. 설계 근거는 [신뢰와 샌드박스](../explanation/trust-and-sandbox.md)를 참고하세요.

## 신뢰 계층

민감한 도구(`run_shell`, `write_file`, `fetch_url` 등)는 실행 전에 확인을 요청합니다. 사용자는 **이번 한 번**, **이 프로젝트에 항상**, **모든 곳에서 항상**, 또는 **거부** 중 하나를 선택할 수 있습니다. 부여된 권한은 유지되어 같은 질문이 반복되지 않습니다.

프롬프트를 기다리지 않고 권한을 미리 관리하려면:

```bash
veles trust list                          # 현재 권한 목록 (사용자 + 프로젝트 범위)
veles trust set run_shell --scope project # 이 프로젝트에 사전 권한 부여
veles trust set write_file --scope user   # 모든 곳에 사전 권한 부여
veles trust revoke run_shell              # 권한 제거
veles trust clear --scope all             # 모든 권한 초기화
```

권한을 부여하더라도 **항상 확인이 필요한 작업**이 있습니다. 파일 삭제, URL 요청, 새 스킬/도구/모듈 설치, 채널 연결, 프로젝트 외부 파일 쓰기가 이에 해당합니다.

## 자동 조종 — 시간 제한 우회

야간 배치 처리처럼 무인 실행이 필요할 때, 신뢰 계층 프롬프트를 자동으로 허용하는 시간 창을 열 수 있습니다:

```bash
veles autopilot enable --until +2h
veles autopilot enable --until 2026-12-31T23:00:00Z
veles autopilot status
veles autopilot disable
```

자동 조종 중 실행된 모든 작업은 나중에 검토할 수 있도록 로그에 기록됩니다. 비대화형 컨텍스트(데몬, 배치)에서는 자동 조종이 활성화되어 있지 않으면 기본적으로 거부됩니다.

## 시크릿

API 키와 봇 토큰은 설정 파일이 아닌 OS 키체인에 보관됩니다:

```bash
veles secret set OPENROUTER_API_KEY       # 입력 프롬프트 표시 (또는 stdin으로 파이프 가능)
veles secret list                         # 설정된 시크릿 목록
veles secret get OPENROUTER_API_KEY --reveal
veles secret delete OPENROUTER_API_KEY
veles secret set OPENROUTER_API_KEY --project myproj   # 한 프로젝트 전용 키
```

조회 시 `--no-env-fallback`을 전달하지 않으면, 키체인에 값이 없을 때 해당 [환경 변수](../reference/environment-variables.md)로 자동 대체됩니다.

## 샌드박스

도구는 활성 프로젝트, `~/.veles/skills/`, `~/.veles/locales/` 내부에서만 읽을 수 있으며, 쓰기는 프로젝트 내부로 제한됩니다. 레이아웃이 쓰기 가능 영역을 선언한 경우에는 그 영역으로만 제한됩니다. 고급 설정에서 루트를 변경하려면 `VELES_SANDBOX_ROOTS`(`:`로 구분)를 사용하세요. URL 요청에는 SSRF 차단 목록이 적용됩니다. `VELES_FETCH_ALLOW_PRIVATE=1`을 설정하면 사설 네트워크 차단이 해제됩니다.

프로젝트의 `.veles/` 안에서 에이전트의 파일 도구가 쓸 수 있는 곳은 `skills/`, `tools/`, `tmp/`, `plans/`, `memory/`, `artifacts/`뿐입니다. 그 밖의 모든 것 — `trust.json`, `config.toml`, `project.toml`, `modules/`, `wiki.toml`, `memory.db` — 은 `veles` 명령과 Veles 자체 도구를 통해서만 변경됩니다. 파일 도구는 프로젝트 내 다른 `.veles/` 디렉터리(서브프로젝트의 것이나 에이전트가 `wiki/`에 심으려는 것)도 어떤 깊이에서든 거부합니다. 따라서 에이전트는 파일 도구로 스스로 신뢰를 부여하거나 Veles가 실행할 코드를 추가할 수 없습니다(`.veles/tools/`에 작성한 도구는 사용자가 그 파일을 승인한 뒤에야 로드됩니다). 같은 파일을 가리키는 다른 표기(대소문자, `..`, 심볼릭 링크)도 거부됩니다.

명시적인 명령 없이 실행되거나 에이전트 CLI를 조종하는 파일 — `.git/`, `.githooks/`, `.claude/`, `.gemini/`, `.agents/`, `.codex/`, `.vscode/`, `.devcontainer/`, `.husky/` 아래의 모든 것, 그리고 `.envrc`, `.mcp.json`, `.pre-commit-config.yaml`, `lefthook.yml`(모두 어떤 깊이든), 그에 더해 저장소의 `core.hooksPath` 디렉터리와 심볼릭 링크된 `.git`이 가리키는 곳 — 에는 에이전트의 파일 도구가 사용자가 그 쓰기를 확인한 뒤에만 씁니다. 신뢰 부여와 자동 조종은 이를 포괄하지 않습니다. 데몬은 채널에서 묻고, 물어볼 사람이 없는 배치 실행은 거부합니다.

`claude-cli`와 `antigravity-cli` 제공자는 Veles 도구만 가진 모델로 실행됩니다. 이들 자체의 셸, 파일 편집·웹 도구, 프로젝트의 `.claude/` 설정과 훅, 다른 MCP 서버는 적용되지 않으며, 이들이 호출하는 모든 Veles 도구는 위의 신뢰 계층을 거칩니다(그곳에서는 프롬프트에 답할 사람이 없으므로 아직 부여되지 않은 것은 모두 거부됩니다). 이들의 MCP 설정은 실행 중인 프로세스마다 하나씩 `.veles/tmp/delegate-<pid>/`에 있으며, 에이전트의 파일 도구는 이곳에 쓸 수 없습니다. `agy`는 프로젝트 밖, `~/.veles/tmp/` 아래의 스크래치 워크스페이스에서 실행되므로 프로젝트 자체의 `.agents/` 훅과 MCP 서버가 닿지 않습니다. Veles 도구가 있을 때는 `--dangerously-skip-permissions`로 실행됩니다 — 그렇지 않으면 agy가 헤드리스 상태에서 MCP 호출을 거부하기 때문입니다. 그 워크스페이스의 훅이 agy 자체의 모든 도구를 거부하며, 실패하는 훅도 거부합니다. Veles의 파일 도구는 프로젝트 밖에 쓸 수 없으므로, agy는 이를 통해 그 훅을 다시 쓸 수 없습니다.

알려진 제한:

- `run_shell`은 셸입니다. 이를 부여하면(또는 자동 조종 중에는) 파일별 확인 없이 위의 어떤 파일에도 쓸 수 있습니다.
- MCP 승인은 서버의 명령줄을 고정할 뿐, 서버가 프로젝트에서 실행하는 파일(`args`에 지정된 스크립트)은 고정하지 않습니다. 그 파일들도 검토하세요.
- CLI 제공자를 쓸 때, 자기 자신에게만 도구를 미리 승인하는 실행(데몬 백그라운드 작업, `veles research`)은 그 승인을 위임된 CLI에 넘기지 않습니다. 사전 승인은 Veles 프로세스 안에 있고 CLI가 시작하는 MCP 서버는 별개의 프로세스이므로, 해당 CLI의 Veles 도구에는 상시 `veles trust set` 부여나 자동 조종 구간이 필요합니다. 부모 실행의 계획 모드도 마찬가지로 전달되지 않습니다.
- `antigravity-cli`는 agy가 워크스페이스의 `.agents/hooks.json`을 따른다는 점에 의존합니다. 워크스페이스 훅 읽기를 중단한 agy 릴리스에서는 `--dangerously-skip-permissions` 아래에서 agy 자체의 도구가 열려 있게 됩니다.

제어 문자(터미널 이스케이프, bidi 오버라이드)가 포함된 경로는 거부되며, 확인 창, 신뢰 프롬프트, diff 미리보기에서는 그런 문자가 이스케이프되어 표시됩니다. 도구 호출이 사용자가 승인하는 텍스트를 위조할 수는 없습니다.

설정에 있는 MCP 서버는 사용자가 승인한 뒤에만 시작됩니다. [외부 MCP 서버](external-mcp-servers.md)를 참고하세요.

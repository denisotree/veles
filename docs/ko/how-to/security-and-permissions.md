# 보안 관리 방법: 신뢰, 자동 조종, 시크릿

> 🌐 **언어:** **English** · [Русский](../../ru/how-to/security-and-permissions.md)

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
```

조회 시 `--no-env-fallback`을 전달하지 않으면, 키체인에 값이 없을 때 해당 [환경 변수](../reference/environment-variables.md)로 자동 대체됩니다.

## 샌드박스

도구는 활성 프로젝트와 `~/.veles/` 내부에서만 읽을 수 있으며, 쓰기는 레이아웃의 쓰기 가능 영역(기본값: `wiki/`, `.veles/`)으로 제한됩니다. 고급 설정에서 루트를 변경하려면 `VELES_SANDBOX_ROOTS`(`:`로 구분)를 사용하세요. URL 요청에는 SSRF 차단 목록이 적용됩니다. `VELES_FETCH_ALLOW_PRIVATE=1`을 설정하면 사설 네트워크 차단이 해제됩니다.

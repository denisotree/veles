# TUI 키 바인딩 및 슬래시 명령

> 🌐 **언어:** [English](../../en/reference/tui.md) · [简体中文](../../zh-CN/reference/tui.md) · [繁體中文](../../zh-TW/reference/tui.md) · [日本語](../../ja/reference/tui.md) · **한국어** · [Español](../../es/reference/tui.md) · [Français](../../fr/reference/tui.md) · [Italiano](../../it/reference/tui.md) · [Português (BR)](../../pt-BR/reference/tui.md) · [Português (PT)](../../pt-PT/reference/tui.md) · [Русский](../../ru/reference/tui.md) · [العربية](../../ar/reference/tui.md) · [हिन्दी](../../hi/reference/tui.md) · [বাংলা](../../bn/reference/tui.md) · [Tiếng Việt](../../vi/reference/tui.md)

`veles tui`(또는 단순히 `veles`)는 인터랙티브 REPL을 엽니다. 멀티라인 컴포저, 상태 표시줄, 접을 수 있는 인스펙터를 갖춘 스크롤백 채팅 인터페이스입니다.

## 키 바인딩

| 키 | 동작 |
|---|---|
| `Ctrl+D` | 종료 |
| `Ctrl+C` | 마지막 어시스턴트 응답 복사; 1.5초 이내에 두 번 누르면 종료 |
| `Ctrl+V` | 클립보드에서 붙여넣기 |
| `Ctrl+Shift+C` / `⌘C` | 현재 선택 내용 복사 (OSC52). macOS Terminal.app에서는 네이티브 드래그 선택 후 ⌘C로 직접 복사 가능 |
| `Ctrl+I` | 인스펙터 토글 (추론, 도구 활동, 토큰/오류 로그) |
| `Ctrl+R` | 세션 선택기 열기 (이전 세션 재개) |
| `Ctrl+T` | 테마 선택기 열기 |
| `Shift+Tab` | 실행 모드 순환: `auto → planning → writing → goal` |
| `Tab` | 슬래시 명령 자동완성 순환 |
| `Up` / `Down` | 기록 탐색 (및 대기 중인 프롬프트 꺼내기) |

실행 모드에 대한 설명은 [실행 모드](../explanation/modes.md)를 참조하세요.

## 슬래시 명령

컴포저에서 `/`를 입력하고 `Tab`으로 자동완성합니다. 등록된 명령 목록:

| 명령 | 목적 |
|---|---|
| `/help` | 사용 가능한 명령 목록 표시 |
| `/quit`, `/q`, `/exit` | REPL 종료 |
| `/clear` | 채팅 로그 지우기 |
| `/model` | 모델 선택기 열기 |
| `/mode` | 실행 모드 전환 (auto/planning/writing/goal) |
| `/session` | 세션 선택기 열기 (재개) |
| `/save` | 현재 세션 저장 / 이름 지정 |
| `/history` | 세션 기록 표시 |
| `/tokens` | 토큰 사용량 (입력/출력/턴당/세션당) |
| `/context` | 현재 컨텍스트 크기 대비 한도 |
| `/status` | 스냅샷: 모델, 프로바이더, 모드, 세션, 처리 중, 대기열 |
| `/insights` | 프로젝트의 학습된 인사이트 표시 |
| `/rules` | 프로젝트의 규칙 다이제스트 표시 |
| `/schema` | `AGENTS.md` 검증 / 수정 |
| `/wiki` | 활성 레이아웃의 위키 작업 |
| `/daemon` | 데몬 제어판 열기 (프로젝트 → 데몬 → 채널) |

> 슬래시 명령 세트는 TUI를 직접 실행하든 다른 화면에서 푸시하든 동일합니다. 채널(예: Telegram)은 별도의 자체 명령 세트를 노출합니다.

## 테마

내장 테마: `everforest` (기본값), `dracula`, `gruvbox`, `tokyo-night`, `catppuccin`. `Ctrl+T`, `veles tui --theme <name>`, 또는 `~/.veles/config.toml`의 `[user] tui_theme`으로 선택합니다.

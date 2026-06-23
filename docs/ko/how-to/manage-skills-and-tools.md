# 스킬, 도구, 모듈 관리 방법

> 🌐 **언어:** **English** · [Русский](../../ru/how-to/manage-skills-and-tools.md)

Veles는 시간이 지남에 따라 역량을 축적합니다. **스킬**은 재사용 가능한 워크플로우이고, **도구**는 실행 가능한 액션이며, **모듈**은 선택적 플러그인입니다. 각각은 프로젝트 로컬(`<project>/.veles/`)과 사용자 전역(`~/.veles/`) 두 가지 범위에 존재합니다. 개념에 대한 자세한 내용은 [스킬 & 도구](../explanation/skills-and-tools.md)를 참고하세요.

## 스킬

스킬은 에이전트가 도구처럼 호출할 수 있는 `SKILL.md` 파일(프론트매터 + 프롬프트 본문)입니다.

```bash
veles skill list                          # 설치된 스킬 + 텔레메트리
veles skill show <name>                   # SKILL.md 출력
veles skill add https://github.com/org/skill.git
veles skill add ./local-skill --scope user   # 사용자 전역으로 설치
veles skill remove <name>
```

### 범위 간 프로모션 / 데모션

한 프로젝트에서 유용하게 사용된 스킬을 사용자 범위로 이동하여 모든 프로젝트에서 사용하거나, 반대로 이동할 수 있습니다:

```bash
veles skill promote <name>     # 프로젝트 → ~/.veles/skills/
veles skill demote  <name>     # 사용자 → 현재 프로젝트
```

### 중복 및 프로모션 후보 찾기

```bash
veles skill dedup                         # 거의 중복된 스킬 (임베딩/TF-IDF)
veles skill suggest-promote --save        # 자동 프로모션 기준을 충족하는 스킬
```

## 도구

도구는 사용 텔레메트리와 함께 프로젝트의 `memory.db`에 카탈로그화됩니다. Veles는 작업 중에 자체 도구를 직접 작성할 수 있으며, 다음 명령으로 관리합니다:

```bash
veles tool list                # 이 프로젝트의 도구
veles tool show <name>         # 매니페스트 + 텔레메트리
veles tool promote <name>      # ~/.veles/tools/로 이동 (프로젝트 간 공유)
```

민감한 도구(`run_shell`, `write_file`, `fetch_url` 등)는 [신뢰 단계](security-and-permissions.md)에 의해 제어됩니다.

## 모듈

모듈은 코어를 비대하게 만들지 않으면서 선택적 기능(임베딩, 비전, STT)을 추가합니다. 설치 시 기본적으로 확인을 요청합니다.

```bash
veles module list
veles module add https://github.com/org/module.git
veles module remove <name>
```

## 더 찾아보기

큐레이션된 레지스트리를 탐색합니다:

```bash
veles browse skills [query]
veles browse modules [query]
```

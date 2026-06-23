# 멀티 프로젝트 및 서브프로젝트 사용 방법

> 🌐 **언어:** [English](../../en/how-to/multi-project-and-subprojects.md) · [简体中文](../../zh-CN/how-to/multi-project-and-subprojects.md) · [繁體中文](../../zh-TW/how-to/multi-project-and-subprojects.md) · [日本語](../../ja/how-to/multi-project-and-subprojects.md) · **한국어** · [Español](../../es/how-to/multi-project-and-subprojects.md) · [Français](../../fr/how-to/multi-project-and-subprojects.md) · [Italiano](../../it/how-to/multi-project-and-subprojects.md) · [Português (BR)](../../pt-BR/how-to/multi-project-and-subprojects.md) · [Português (PT)](../../pt-PT/how-to/multi-project-and-subprojects.md) · [Русский](../../ru/how-to/multi-project-and-subprojects.md) · [العربية](../../ar/how-to/multi-project-and-subprojects.md) · [हिन्दी](../../hi/how-to/multi-project-and-subprojects.md) · [বাংলা](../../bn/how-to/multi-project-and-subprojects.md) · [Tiếng Việt](../../vi/how-to/multi-project-and-subprojects.md)

Veles는 하나의 에이전트 루프에서 여러 프로젝트를 실행합니다. 각 프로젝트는 자체 메모리, 스킬, 도구를 가집니다. **서브프로젝트**는 부모 아래에 중첩된 프로젝트로, 대규모 모노레포나 지식 베이스를 범위가 지정된 메모리로 분해할 때 유용합니다.

## 프로젝트

Veles는 현재 작업 디렉터리에서 `.veles/` 디렉터리가 있는 곳까지 위로 탐색하여 활성 프로젝트를 찾습니다(`git`과 유사). 레지스트리 관리:

```bash
veles project list                  # 등록된 프로젝트, 최근 순
veles project add /path/to/project  # 기존 프로젝트 등록
veles project add /path --slug web  # 커스텀 슬러그로 등록
veles project remove <slug>         # 등록 해제 (파일은 유지)
```

`switch`는 경로를 출력하므로 프로젝트로 `cd`할 수 있습니다:

```bash
cd "$(veles project switch web)"
```

`cd` 없이 다른 위치의 프로젝트에 명령을 실행합니다:

```bash
veles run --project-root /path/to/project "..."
```

## 서브프로젝트

서브프로젝트는 부모 내부에 있는 자식 Veles 프로젝트입니다. 생성 방법:

```bash
veles subproject init frontend --description "the web client"
veles subproject list
cd "$(veles subproject switch frontend)"
veles subproject remove frontend    # 등록 해제 (파일은 유지)
```

### Veles가 분할을 제안하게 하기

프로젝트 위키가 커지면, Veles가 주제 클러스터를 감지하여 서브프로젝트로 제안할 수 있습니다:

```bash
veles subproject suggest            # 후보 출력
veles subproject suggest --save     # 각 후보를 .veles/memory/proposals/에 저장
```

## 언제 무엇을 사용할까

- **별도 프로젝트** — 서로 무관한 지식 베이스 / 코드베이스.
- **서브프로젝트** — 하나의 큰 것을 구성하는 부분으로, 범위가 지정된 메모리가 필요하지만 부모 컨텍스트를 공유하는 경우.

멀티 프로젝트 컨텍스트가 단일 모놀리식 덤프 대신 필요에 따라 어떻게 로드되는지는 [아키텍처](../explanation/architecture.md)를 참고하세요.

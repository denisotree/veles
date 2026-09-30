# 스킬, 도구, 모듈 관리 방법

> 🌐 **언어:** [English](../../en/how-to/manage-skills-and-tools.md) · [简体中文](../../zh-CN/how-to/manage-skills-and-tools.md) · [繁體中文](../../zh-TW/how-to/manage-skills-and-tools.md) · [日本語](../../ja/how-to/manage-skills-and-tools.md) · **한국어** · [Español](../../es/how-to/manage-skills-and-tools.md) · [Français](../../fr/how-to/manage-skills-and-tools.md) · [Italiano](../../it/how-to/manage-skills-and-tools.md) · [Português (BR)](../../pt-BR/how-to/manage-skills-and-tools.md) · [Português (PT)](../../pt-PT/how-to/manage-skills-and-tools.md) · [Русский](../../ru/how-to/manage-skills-and-tools.md) · [العربية](../../ar/how-to/manage-skills-and-tools.md) · [हिन्दी](../../hi/how-to/manage-skills-and-tools.md) · [বাংলা](../../bn/how-to/manage-skills-and-tools.md) · [Tiếng Việt](../../vi/how-to/manage-skills-and-tools.md)

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

모듈은 Veles 내부에서 실행되는 Python 코드(`module.toml` + 진입점)로, 코어를 비대하게 만들지 않으면서 선택적 기능(메모리 제공자, 임베딩, 비전, STT)을 추가합니다. 설치 시 기본적으로 확인을 요청하며, 파일이 승인했을 때와 일치하는 동안에만 매 실행마다 로드됩니다([설치 상태를 신뢰할 수 있게 유지하기](../../en/how-to/extension-registries.md#keep-installs-honest) 참고).

```bash
veles module list                              # 두 범위 모두, `scope` 열 포함
veles module add https://github.com/org/module.git
veles module add ./local-module --user          # ~/.veles/modules/에 설치, 모든 프로젝트에서 사용
veles module show <name> [--user]
veles module remove <name> [--user]
veles module approve <name> [--user]
```

모듈은 스킬, 도구와 마찬가지로 두 범위에 존재합니다. 프로젝트 로컬(`<project>/.veles/modules/`)과 모든 프로젝트에서 로드되는 사용자 전역(`~/.veles/modules/`)입니다. 사용자 수준 모듈도 프로젝트 모듈과 같은 승인 게이트를 거치며, 게이트는 이름을 비교하기 전에 실행됩니다. 프로젝트 모듈과 사용자 모듈의 이름이 같으면 승인된 프로젝트 모듈이 로드되고 Veles는 사용자 수준 모듈이 가려진다고 경고합니다. 승인되지 않은 프로젝트 모듈은 건너뛰고(경고에 해당 디렉터리가 표시됨) 사용자 모듈이 로드됩니다. 같은 범위에서 승인된 두 모듈의 이름이 같으면 (디렉터리 순으로) 첫 번째가 로드되고 나머지는 경고와 함께 건너뜁니다. `veles module {show,approve,remove}`는 매니페스트 이름(`list`가 보여 주는 것)을 받으며, 범위 내 둘 이상의 디렉터리가 선언한 이름은 해당 디렉터리를 나열하고 거부합니다. `veles module add`는 범위 내 다른 디렉터리가 이미 선언한 이름의 모듈 설치를 거부합니다.

### 메모리 제공자를 추가하는 모듈 작성하기

모듈의 `register(api)` 진입점은 `api.add_memory_provider(name, factory)`를 호출하여 외부 메모리 소스를 리콜에 연결할 수 있습니다. `name`은 `~/.veles/config.toml`의 `[memory.external.<name>]` 섹션과 일치해야 합니다. `factory`는 그 섹션(`dict`)을 받아 호출되며, Veles의 `MemoryProvider` 프로토콜(`veles.core.memory.provider`)을 구현한 객체를 반환하거나, 제공자를 건너뛰려면 `None`을 반환해야 합니다.

```toml
# module.toml
[module]
name = "my-provider"
description = "Recalls memories from my external store."
entrypoint = "my_provider.py:register"
version = "0.1.0"
```

```python
# my_provider.py
from veles.core.memory.provider import RecallHit


class MyProvider:
    name = "my-provider"

    def recall(self, query: str, *, limit: int) -> list[RecallHit]:
        ...  # query the external store, return RecallHit objects


def _build(cfg: dict) -> MyProvider | None:
    api_key = cfg.get("api_key")
    return MyProvider() if api_key else None


def register(api) -> None:
    api.add_memory_provider("my-provider", _build)
```

```toml
# ~/.veles/config.toml
[memory.external.my-provider]
api_key = "..."
```

`ingest(title, body, *, insight_id) -> bool`(`IngestingMemoryProvider` 프로토콜)도 구현한 제공자는 읽기뿐 아니라 Veles의 쓰기도 받습니다. 두 모듈이 같은 제공자 이름을 등록하면 두 번째 모듈의 로드가 실패하며, 경고와 함께 건너뛰고 부분적으로 등록된 것은 남지 않습니다. `config.toml`에 설정된 섹션의 모듈이 설치되어 있지 않으면 설치 명령과 함께 경고가 한 번 출력되며, 리콜은 그 없이도 계속 동작합니다.

레지스트리는 Honcho, Mem0, Supermemory를 바로 쓸 수 있는 제공자 모듈로 제공합니다. `veles registry install --user {honcho,mem0,supermemory}`로 설치한 뒤, 설치가 출력하는 `uv tool install veles-ai --with '<package>'` 명령을 실행하고(각 모듈은 SDK — `mem0ai>=2.0`, `honcho-ai>=2.5`, `supermemory>=3.62` — 를 선언하며, Veles가 대신 설치하지는 않습니다), 해당 `[memory.external.<name>]` 섹션을 채우세요.

- **mem0**: `api_key`, `user_id`, 선택적 `agent_id`(해당 에이전트의 메모리도 리콜)와 `host`. SDK 텔레메트리는 기본적으로 꺼져 있으며, 리콜할 때마다 추가로 `GET /v1/ping/` 요청을 한 번 보냅니다.
- **supermemory**: `api_key`, 선택적 `user_id`(검색의 `container_tag`로 전송)와 `base_url`.
- **honcho**: `api_key`, `workspace_id`, 선택적 `peer_id`(해당 피어의 메시지만 검색)와 `base_url`. 리콜할 때마다 워크스페이스 get-or-create를 수행하므로, `workspace_id`가 없으면 생성합니다.

## 더 찾아보기

연결된 레지스트리를 검색합니다:

```bash
veles registry search [query] [--kind module|skill|layout|mcp]
```

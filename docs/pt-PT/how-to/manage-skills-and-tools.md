# Como gerir skills, ferramentas e módulos

> 🌐 **Idiomas:** [English](../../en/how-to/manage-skills-and-tools.md) · [简体中文](../../zh-CN/how-to/manage-skills-and-tools.md) · [繁體中文](../../zh-TW/how-to/manage-skills-and-tools.md) · [日本語](../../ja/how-to/manage-skills-and-tools.md) · [한국어](../../ko/how-to/manage-skills-and-tools.md) · [Español](../../es/how-to/manage-skills-and-tools.md) · [Français](../../fr/how-to/manage-skills-and-tools.md) · [Italiano](../../it/how-to/manage-skills-and-tools.md) · [Português (BR)](../../pt-BR/how-to/manage-skills-and-tools.md) · **Português (PT)** · [Русский](../../ru/how-to/manage-skills-and-tools.md) · [العربية](../../ar/how-to/manage-skills-and-tools.md) · [हिन्दी](../../hi/how-to/manage-skills-and-tools.md) · [বাংলা](../../bn/how-to/manage-skills-and-tools.md) · [Tiếng Việt](../../vi/how-to/manage-skills-and-tools.md)

O Veles acumula capacidade ao longo do tempo. As **skills** são fluxos de trabalho
reutilizáveis, as **ferramentas** são ações executáveis, os **módulos** são
plug-ins opcionais. Cada um vive em dois âmbitos: local ao projeto
(`<project>/.veles/`) e global ao utilizador (`~/.veles/`). Para os conceitos, ver
[skills & ferramentas](../explanation/skills-and-tools.md).

## Skills

Uma skill é um `SKILL.md` (frontmatter + corpo do prompt) que o agente pode invocar
como uma ferramenta.

```bash
veles skill list                          # installed skills + telemetry
veles skill show <name>                   # print its SKILL.md
veles skill add https://github.com/org/skill.git
veles skill add ./local-skill --scope user   # install user-global
veles skill remove <name>
```

### Promover / despromover entre âmbitos

Uma skill que se revele útil num projeto pode passar para o âmbito do utilizador
para que todos os projetos a vejam (ou o inverso):

```bash
veles skill promote <name>     # project → ~/.veles/skills/
veles skill demote  <name>     # user → this project
```

### Encontrar duplicados e candidatos a promoção

```bash
veles skill dedup                         # near-duplicate skills (embedding/TF-IDF)
veles skill suggest-promote --save        # skills that meet the auto-promote bar
```

## Ferramentas

As ferramentas estão catalogadas no `memory.db` do projeto com telemetria de
utilização. O Veles pode escrever as suas próprias ferramentas à medida que
trabalha; geri-las com:

```bash
veles tool list                # tools in this project
veles tool show <name>         # manifest + telemetry
veles tool promote <name>      # move to ~/.veles/tools/ (cross-project)
```

As ferramentas sensíveis (`run_shell`, `write_file`, `fetch_url`, …) são
controladas pela [escada de confiança](security-and-permissions.md).

## Módulos

Um módulo é código Python (`module.toml` + um ponto de entrada) que corre dentro do
Veles — adiciona capacidades opcionais (fornecedores de memória, embeddings, visão,
STT) sem inchar o núcleo. A instalação de um requer confirmação por omissão, e ele
só é carregado em cada execução enquanto os seus ficheiros continuarem iguais ao que
aprovou (veja [manter as instalações
honestas](../../en/how-to/extension-registries.md#keep-installs-honest)).

```bash
veles module list                              # ambos os âmbitos, com uma coluna `scope`
veles module add https://github.com/org/module.git
veles module add ./local-module --user          # instala em ~/.veles/modules/, para todos os projetos
veles module show <name> [--user]             # manifesto + sha256 dos ficheiros
veles module remove <name> [--user]
veles module approve <name> [--user]          # escrever `yes` num terminal
veles module approve <name> --sha256 <hash>   # sem terminal: o hash revisto
```

Os módulos vivem em dois âmbitos, tal como as skills e as ferramentas: locais do
projeto (`<project>/.veles/modules/`) e globais do utilizador (`~/.veles/modules/`,
carregados em todos os projetos). Um módulo de utilizador passa pelo mesmo portão de
aprovação que um de projeto, e o portão corre antes de os nomes serem comparados. Se
um módulo de projeto e um de utilizador partilharem o nome, um módulo de projeto
aprovado é carregado e o Veles avisa que o de utilizador ficou sombreado; um módulo
de projeto não aprovado é ignorado (o aviso indica o seu diretório) e o módulo de
utilizador é carregado. Dois módulos aprovados no mesmo âmbito com o mesmo nome — o
primeiro (por ordem de diretório) é carregado, os restantes avisam e são ignorados.
`veles module {show,approve,remove}` aceitam o nome do manifesto (o que `list`
mostra) e recusam um nome declarado por mais de um diretório no âmbito, listando-os;
`veles module add` recusa instalar um módulo cujo nome outro diretório do âmbito já
declare.

### Escrever um módulo que adiciona um fornecedor de memória

O ponto de entrada `register(api)` de um módulo pode chamar
`api.add_memory_provider(name, factory)` para ligar uma fonte de memória externa ao
recall. `name` tem de corresponder a uma secção `[memory.external.<name>]` em
`~/.veles/config.toml`; `factory` é chamada com essa secção (um `dict`) e tem de
devolver um objeto que implemente o protocolo `MemoryProvider` do Veles
(`veles.core.memory.provider`), ou `None` para ignorar o fornecedor:

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

Um fornecedor que implemente também `ingest(title, body, *, insight_id) ->
bool` (o protocolo `IngestingMemoryProvider`) recebe também as escritas do Veles, e
não apenas leituras. Se dois módulos registarem o mesmo nome de fornecedor, o
carregamento do segundo falha — é ignorado com um aviso, sem deixar nada registado
a meio. Uma secção configurada em `config.toml` cujo módulo não está instalado
imprime um aviso com o comando de instalação; o recall continua a funcionar sem ela.

O registo inclui Honcho, Mem0 e Supermemory como módulos de fornecedor prontos a
usar — instale com `veles registry install --user {honcho,mem0,supermemory}`, depois
execute o comando `uv tool install veles-ai --with '<package>'` que a instalação
imprime (cada um declara um SDK — `mem0ai>=2.0`, `honcho-ai>=2.5`,
`supermemory>=3.62` — que o Veles nunca instala por si), e preencha a secção
`[memory.external.<name>]` correspondente:

- **mem0**: `api_key`, `user_id`, `agent_id` opcional (recorda também as memórias
  desse agente) e `host`. A telemetria do SDK está desligada por omissão; cada recall
  faz um pedido extra `GET /v1/ping/`.
- **supermemory**: `api_key`, `user_id` opcional (enviado como `container_tag` da
  pesquisa) e `base_url`.
- **honcho**: `api_key`, `workspace_id`, `peer_id` opcional (pesquisa apenas as
  mensagens desse peer) e `base_url`. Cada recall faz um get-or-create do workspace
  — cria `workspace_id` se ainda não existir.

## Descobrir mais

Pesquise nos registos ligados:

```bash
veles registry search [query] [--kind module|skill|layout|mcp]
```

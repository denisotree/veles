# Como gerenciar skills, tools e módulos

> 🌐 **Idiomas:** [English](../../en/how-to/manage-skills-and-tools.md) · [简体中文](../../zh-CN/how-to/manage-skills-and-tools.md) · [繁體中文](../../zh-TW/how-to/manage-skills-and-tools.md) · [日本語](../../ja/how-to/manage-skills-and-tools.md) · [한국어](../../ko/how-to/manage-skills-and-tools.md) · [Español](../../es/how-to/manage-skills-and-tools.md) · [Français](../../fr/how-to/manage-skills-and-tools.md) · [Italiano](../../it/how-to/manage-skills-and-tools.md) · **Português (BR)** · [Português (PT)](../../pt-PT/how-to/manage-skills-and-tools.md) · [Русский](../../ru/how-to/manage-skills-and-tools.md) · [العربية](../../ar/how-to/manage-skills-and-tools.md) · [हिन्दी](../../hi/how-to/manage-skills-and-tools.md) · [বাংলা](../../bn/how-to/manage-skills-and-tools.md) · [Tiếng Việt](../../vi/how-to/manage-skills-and-tools.md)

O Veles acumula capacidades ao longo do tempo. **Skills** são fluxos de trabalho
reutilizáveis, **tools** são ações executáveis e **módulos** são plug-ins opcionais.
Cada um existe em dois escopos: local do projeto (`<project>/.veles/`) e global do
usuário (`~/.veles/`). Para entender os conceitos, veja
[skills & tools](../explanation/skills-and-tools.md).

## Skills

Uma skill é um `SKILL.md` (frontmatter + corpo do prompt) que o agente pode invocar
como uma tool.

```bash
veles skill list                          # installed skills + telemetry
veles skill show <name>                   # print its SKILL.md
veles skill add https://github.com/org/skill.git
veles skill add ./local-skill --scope user   # install user-global
veles skill remove <name>
```

### Promover / rebaixar entre escopos

Uma skill que se mostra útil em um projeto pode ser movida para o escopo do usuário,
de modo que todos os projetos a vejam (ou o contrário):

```bash
veles skill promote <name>     # project → ~/.veles/skills/
veles skill demote  <name>     # user → this project
```

### Encontrar duplicatas e candidatas a promoção

```bash
veles skill dedup                         # near-duplicate skills (embedding/TF-IDF)
veles skill suggest-promote --save        # skills that meet the auto-promote bar
```

## Tools

As tools são catalogadas no `memory.db` do projeto com telemetria de uso. O Veles pode
escrever suas próprias tools enquanto trabalha; você as gerencia com:

```bash
veles tool list                # tools in this project
veles tool show <name>         # manifest + telemetry
veles tool promote <name>      # move to ~/.veles/tools/ (cross-project)
```

Tools sensíveis (`run_shell`, `write_file`, `fetch_url`, …) são protegidas pela
[escada de confiança](security-and-permissions.md).

## Módulos

Um módulo é código Python (`module.toml` + um entrypoint) que roda dentro do Veles —
adiciona capacidades opcionais (provedores de memória, embeddings, visão, STT) sem
inchar o núcleo. Instalar um requer confirmação por padrão, e ele carrega a cada
execução apenas enquanto seus arquivos ainda coincidirem com o que você aprovou (veja
[mantenha as instalações confiáveis](../../en/how-to/extension-registries.md#keep-installs-honest)).

```bash
veles module list                              # ambos os escopos, com uma coluna `scope`
veles module add https://github.com/org/module.git
veles module add ./local-module --user          # instala em ~/.veles/modules/, para todos os projetos
veles module show <name> [--user]             # manifesto + sha256 dos arquivos
veles module remove <name> [--user]
veles module approve <name> [--user]          # digite `yes` em um terminal
veles module approve <name> --sha256 <hash>   # sem terminal: o hash que você revisou
```

Módulos vivem em dois escopos, como skills e tools: locais ao projeto
(`<project>/.veles/modules/`) e globais do usuário (`~/.veles/modules/`, carregados em
todo projeto). Um módulo de usuário passa pelo mesmo portão de aprovação que um de
projeto, e o portão roda antes de os nomes serem comparados. Se um módulo de projeto e
um de usuário têm o mesmo nome, um módulo de projeto aprovado carrega e o Veles avisa
que o de usuário ficou sombreado; um módulo de projeto não aprovado é ignorado (o aviso
cita o diretório dele) e o de usuário carrega. Dois módulos aprovados no mesmo escopo
com o mesmo nome — o primeiro (ordenado por diretório) carrega, os demais avisam e são
ignorados. `veles module {show,approve,remove}` recebem o nome do manifesto (o que
`list` mostra) e recusam um nome que mais de um diretório do escopo declara, listando-os;
`veles module add` recusa instalar um módulo cujo nome outro diretório do escopo já
declara.

### Escrever um módulo que adiciona um provedor de memória

O entrypoint `register(api)` de um módulo pode chamar
`api.add_memory_provider(name, factory)` para conectar uma fonte de memória externa ao
recall. `name` deve corresponder a uma seção `[memory.external.<name>]` em
`~/.veles/config.toml`; `factory` recebe essa seção (um `dict`) e deve retornar um
objeto que implemente o protocolo `MemoryProvider` do Veles
(`veles.core.memory.provider`), ou `None` para ignorar o provedor:

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

Um provedor que também implemente `ingest(title, body, *, insight_id) -> bool` (o
protocolo `IngestingMemoryProvider`) recebe também as escritas do Veles, não só as
leituras. Se dois módulos registram o mesmo nome de provedor, o carregamento do segundo
falha — ele é ignorado com um aviso, nada fica registrado pela metade. Uma seção
configurada em `config.toml` cujo módulo não está instalado imprime um único aviso com o
comando de instalação; o recall continua funcionando sem ele.

O registry traz Honcho, Mem0 e Supermemory como módulos de provedor prontos — instale
com `veles registry install --user {honcho,mem0,supermemory}`, depois rode o comando
`uv tool install veles-ai --with '<package>'` que a instalação imprime (cada um declara
um SDK — `mem0ai>=2.0`, `honcho-ai>=2.5`, `supermemory>=3.62` — que o Veles nunca
instala por você) e preencha a seção `[memory.external.<name>]` correspondente:

- **mem0**: `api_key`, `user_id`, `agent_id` opcional (recupera também as memórias
  desse agente) e `host`. A telemetria do SDK vem desativada por padrão; cada recall
  faz uma requisição `GET /v1/ping/` extra.
- **supermemory**: `api_key`, `user_id` opcional (enviado como o `container_tag` da
  busca) e `base_url`.
- **honcho**: `api_key`, `workspace_id`, `peer_id` opcional (busca apenas nas mensagens
  desse peer) e `base_url`. Cada recall faz um get-or-create do workspace — cria
  `workspace_id` se ele ainda não existir.

## Descobrir mais

Pesquise nos registries conectados:

```bash
veles registry search [query] [--kind module|skill|layout|mcp]
```

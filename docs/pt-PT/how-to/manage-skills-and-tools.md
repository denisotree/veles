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

Os módulos adicionam capacidades opcionais (embeddings, visão, STT) sem inchar o
núcleo. A instalação de um requer confirmação por omissão.

```bash
veles module list
veles module add https://github.com/org/module.git
veles module remove <name>
```

## Descobrir mais

Navegue pelos registos curados:

```bash
veles browse skills [query]
veles browse modules [query]
```

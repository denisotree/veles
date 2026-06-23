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

Módulos adicionam capacidades opcionais (embeddings, visão, STT) sem inchar o núcleo.
Instalar um requer confirmação por padrão.

```bash
veles module list
veles module add https://github.com/org/module.git
veles module remove <name>
```

## Descobrir mais

Navegue pelos registries curados:

```bash
veles browse skills [query]
veles browse modules [query]
```

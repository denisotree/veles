# Como trabalhar com vários projetos e subprojetos

> 🌐 **Idiomas:** [English](../../en/how-to/multi-project-and-subprojects.md) · [简体中文](../../zh-CN/how-to/multi-project-and-subprojects.md) · [繁體中文](../../zh-TW/how-to/multi-project-and-subprojects.md) · [日本語](../../ja/how-to/multi-project-and-subprojects.md) · [한국어](../../ko/how-to/multi-project-and-subprojects.md) · [Español](../../es/how-to/multi-project-and-subprojects.md) · [Français](../../fr/how-to/multi-project-and-subprojects.md) · [Italiano](../../it/how-to/multi-project-and-subprojects.md) · [Português (BR)](../../pt-BR/how-to/multi-project-and-subprojects.md) · **Português (PT)** · [Русский](../../ru/how-to/multi-project-and-subprojects.md) · [العربية](../../ar/how-to/multi-project-and-subprojects.md) · [हिन्दी](../../hi/how-to/multi-project-and-subprojects.md) · [বাংলা](../../bn/how-to/multi-project-and-subprojects.md) · [Tiếng Việt](../../vi/how-to/multi-project-and-subprojects.md)

O Veles corre muitos projetos num único ciclo de agente. Cada projeto tem a sua
própria memória, skills e ferramentas. Os **subprojetos** são projetos aninhados
sob um pai — úteis para decompor um grande monorepo ou base de conhecimento em
memórias delimitadas.

## Projetos

O Veles descobre o projeto ativo subindo a partir da sua cwd até a um diretório
`.veles/` (tal como o `git`). Gira o registo:

```bash
veles project list                  # registered projects, most-recent first
veles project add /path/to/project  # register an existing project
veles project add /path --slug web  # with a custom slug
veles project remove <slug>         # unregister (files untouched)
```

O `switch` imprime um caminho, para que possa fazer `cd` para dentro de um projeto:

```bash
cd "$(veles project switch web)"
```

Execute um comando contra um projeto noutro local sem `cd`:

```bash
veles run --project-root /path/to/project "..."
```

## Subprojetos

Um subprojeto é um projeto Veles filho dentro de um pai. Crie um:

```bash
veles subproject init frontend --description "the web client"
veles subproject list
cd "$(veles subproject switch frontend)"
veles subproject remove frontend    # unregister (files untouched)
```

### Deixe o Veles sugerir uma divisão

Quando a wiki de um projeto cresce, o Veles consegue detetar agrupamentos temáticos
e propô-los como subprojetos:

```bash
veles subproject suggest            # print candidates
veles subproject suggest --save     # save each to .veles/memory/proposals/ for recall
```

## Quando usar cada um

- **Projetos separados** — bases de conhecimento / bases de código não relacionadas.
- **Subprojetos** — partes de uma coisa maior que beneficiam de memória delimitada
  mas partilham um contexto pai.

Ver [arquitetura](../explanation/architecture.md) para perceber como o contexto
multiprojeto carrega a pedido em vez de ser um despejo monolítico único.

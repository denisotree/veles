# Como trabalhar com múltiplos projetos e subprojetos

> 🌐 **Idiomas:** **English** · [Русский](../../ru/how-to/multi-project-and-subprojects.md)

O Veles roda muitos projetos em um único loop de agente. Cada projeto tem sua própria
memória, skills e tools. **Subprojetos** são projetos aninhados sob um projeto pai —
úteis para decompor um monorepo grande ou uma base de conhecimento em memórias com
escopo delimitado.

## Projetos

O Veles descobre o projeto ativo subindo a partir do seu diretório atual (cwd) até
encontrar um diretório `.veles/` (como o `git` faz). Gerencie o registro:

```bash
veles project list                  # registered projects, most-recent first
veles project add /path/to/project  # register an existing project
veles project add /path --slug web  # with a custom slug
veles project remove <slug>         # unregister (files untouched)
```

O `switch` imprime um caminho, então você pode fazer `cd` para dentro de um projeto:

```bash
cd "$(veles project switch web)"
```

Execute um comando contra um projeto em outro lugar sem usar `cd`:

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

Quando a wiki de um projeto cresce, o Veles pode detectar clusters temáticos e
propô-los como subprojetos:

```bash
veles subproject suggest            # print candidates
veles subproject suggest --save     # save each to .veles/memory/proposals/ for recall
```

## Quando usar cada um

- **Projetos separados** — bases de conhecimento / bases de código sem relação entre si.
- **Subprojetos** — partes de uma coisa maior que se beneficiam de uma memória com
  escopo próprio, mas compartilham um contexto pai.

Veja a [arquitetura](../explanation/architecture.md) para entender como o contexto
multiprojeto é carregado sob demanda, em vez de como um despejo monolítico único.

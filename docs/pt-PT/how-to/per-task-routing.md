# Como encaminhar tarefas para diferentes modelos

> 🌐 **Languages:** **English** · [Русский](../../ru/how-to/per-task-routing.md)

O Veles não está fixado a um único modelo. Cada **tarefa** interna pode usar um
`provider:model` diferente — um modelo barato para a compressão de contexto, um forte para
o agente principal, um modelo de visão para imagens. É o sistema de *encaminhamento de
ensemble*.

## Tipos de tarefa

| Tarefa | Usada para |
|---|---|
| `default` | O ciclo do agente principal |
| `curator` | Consolidação sessão → wiki |
| `compressor` | Compressão de contexto por janela deslizante |
| `insights` | Extracção de insights pós-execução |
| `skills` | Execução de skills |
| `advisor` | A auto-verificação `advisor_review` |
| `vision` | `image_describe` (quando um adaptador de visão está ligado) |
| `embedding` | Similaridade do `veles skill dedup` |

## Ver o encaminhamento actual

```bash
veles route show
```

Isto imprime o `provider:model` resolvido para cada tarefa e uma etiqueta `source` a
indicar que camada o decidiu.

## Fixar uma tarefa a um modelo

```bash
veles route set compressor openrouter:anthropic/claude-haiku-4.5
veles route set advisor    openrouter:anthropic/claude-opus-4.8
veles route set vision     openai:gpt-4o
```

Isto escreve `[routing.tasks]` em `<project>/.veles/config.toml`:

```toml
[routing.tasks]
compressor = "openrouter:anthropic/claude-haiku-4.5"
advisor    = "openrouter:anthropic/claude-opus-4.8"
vision     = "openai:gpt-4o"
```

## Repor

```bash
veles route reset compressor   # one task back to default
veles route reset              # all tasks back to default
```

## Pistas em linguagem natural no AGENTS.md

Pode exprimir o encaminhamento em prosa no `AGENTS.md` (p. ex. "usar um modelo barato para
a compressão"). O Veles analisa-as para um `routing.nl.toml` gerado automaticamente:

```bash
veles route refresh            # re-parse AGENTS.md hints
veles route refresh --force    # even if AGENTS.md hasn't changed
```

As entradas explícitas em `[routing.tasks]` ganham sempre sobre as pistas em LN.

## Ordem de resolução

Para cada tarefa, ganha a primeira camada que produz uma especificação:

1. `[routing.tasks][task]` do projecto
2. `[routing.tasks].default` do projecto
3. pista em LN do projecto (`routing.nl.toml`)
4. base `[provider]` do projecto
5. `[routing.tasks][task]` / `.default` do utilizador
6. `[user] default_provider` + `default_model` do utilizador

Se nenhuma destas resolver, **não existe um recurso de reserva rígido** — a tarefa fica por
definir e quem a invoca degrada (ignora a funcionalidade) ou falha com clareza, em vez de
recorrer silenciosamente a um modelo na nuvem.

(`embedding` ignora os apanha-tudo — um modelo de chat não é um modelo de embeddings — pelo
que só um `[routing.tasks].embedding` explícito a resolve.)

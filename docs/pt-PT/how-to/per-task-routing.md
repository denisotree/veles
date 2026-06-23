# Como encaminhar tarefas para diferentes modelos

> 🌐 **Languages:** **English** · [Русский](../../ru/how-to/per-task-routing.md)

O Veles não está vinculado a um único modelo. Cada **tarefa** interna pode usar
um `provider:model` diferente — um modelo barato para a compressão de contexto,
um modelo forte para o agente principal, um modelo de visão para imagens. É o
sistema de *encaminhamento por ensemble* (ensemble routing).

## Tipos de tarefa

| Tarefa | Utilizada para |
|---|---|
| `default` | O ciclo principal do agente |
| `curator` | Consolidação de sessão → wiki |
| `compressor` | Compressão de contexto por janela deslizante |
| `insights` | Extração de insights após a execução |
| `skills` | Execução de skills |
| `advisor` | A auto-verificação `advisor_review` |
| `vision` | `image_describe` (quando há um adaptador de visão ligado) |
| `embedding` | Similaridade de `veles skill dedup` |

## Ver o encaminhamento atual

```bash
veles route show
```

Isto imprime o `provider:model` resolvido para cada tarefa e uma etiqueta
`source` que indica qual a camada que o decidiu.

## Fixar uma tarefa a um modelo

```bash
veles route set compressor openrouter:anthropic/claude-haiku-4.5
veles route set advisor    openrouter:anthropic/claude-opus-4.8
veles route set vision     openai:gpt-4o
```

Estes comandos escrevem `[routing.tasks]` em `<project>/.veles/config.toml`:

```toml
[routing.tasks]
compressor = "openrouter:anthropic/claude-haiku-4.5"
advisor    = "openrouter:anthropic/claude-opus-4.8"
vision     = "openai:gpt-4o"
```

## Repor

```bash
veles route reset compressor   # uma tarefa de volta à predefinição
veles route reset              # todas as tarefas de volta à predefinição
```

## Sugestões em linguagem natural no AGENTS.md

Pode exprimir o encaminhamento em prosa no `AGENTS.md` (por exemplo, "usar um
modelo barato para a compressão"). O Veles interpreta-as e gera automaticamente
um `routing.nl.toml`:

```bash
veles route refresh            # reinterpretar as sugestões do AGENTS.md
veles route refresh --force    # mesmo que o AGENTS.md não tenha mudado
```

As entradas explícitas em `[routing.tasks]` prevalecem sempre sobre as sugestões
em linguagem natural.

## Ordem de resolução

Para cada tarefa, vence a primeira camada que produza uma especificação:

1. projeto `[routing.tasks][task]`
2. projeto `[routing.tasks].default`
3. sugestão em linguagem natural do projeto (`routing.nl.toml`)
4. base `[provider]` do projeto
5. utilizador `[routing.tasks][task]` / `.default`
6. utilizador `[user] default_provider` + `default_model`
7. predefinição interna para essa tarefa

(`embedding` ignora as camadas genéricas — um modelo de chat não é um modelo de
embedding.)

# Como rotear tarefas para diferentes modelos

> 🌐 **Idiomas:** **English** · [Русский](../../ru/how-to/per-task-routing.md)

O Veles não está preso a um único modelo. Cada **tarefa** interna pode usar um
`provider:model` diferente — um modelo barato para compressão de contexto, um forte
para o agente principal, um modelo de visão para imagens. Esse é o sistema de
*roteamento de ensemble*.

## Tipos de tarefa

| Tarefa | Usada para |
|---|---|
| `default` | O loop principal do agente |
| `curator` | Consolidação de sessão → wiki |
| `compressor` | Compressão de contexto por janela deslizante |
| `insights` | Extração de insights após a execução |
| `skills` | Execução de skills |
| `advisor` | A autoverificação `advisor_review` |
| `vision` | `image_describe` (quando um adaptador de visão está configurado) |
| `embedding` | Similaridade do `veles skill dedup` |

## Ver o roteamento atual

```bash
veles route show
```

Isso imprime o `provider:model` resolvido para cada tarefa e um rótulo `source`
indicando qual camada o decidiu.

## Fixar uma tarefa em um modelo

```bash
veles route set compressor openrouter:anthropic/claude-haiku-4.5
veles route set advisor    openrouter:anthropic/claude-opus-4.8
veles route set vision     openai:gpt-4o
```

Esses comandos escrevem `[routing.tasks]` em `<project>/.veles/config.toml`:

```toml
[routing.tasks]
compressor = "openrouter:anthropic/claude-haiku-4.5"
advisor    = "openrouter:anthropic/claude-opus-4.8"
vision     = "openai:gpt-4o"
```

## Resetar

```bash
veles route reset compressor   # one task back to default
veles route reset              # all tasks back to default
```

## Dicas em linguagem natural no AGENTS.md

Você pode expressar o roteamento em prosa no `AGENTS.md` (por exemplo, "use um modelo
barato para compressão"). O Veles interpreta essas dicas e as transforma em um
`routing.nl.toml` gerado automaticamente:

```bash
veles route refresh            # re-parse AGENTS.md hints
veles route refresh --force    # even if AGENTS.md hasn't changed
```

Entradas explícitas em `[routing.tasks]` sempre prevalecem sobre dicas em linguagem
natural.

## Ordem de resolução

Para cada tarefa, vence a primeira camada que produzir uma especificação:

1. `[routing.tasks][task]` do projeto
2. `[routing.tasks].default` do projeto
3. dica em linguagem natural do projeto (`routing.nl.toml`)
4. base `[provider]` do projeto
5. `[routing.tasks][task]` / `.default` do usuário
6. `[user] default_provider` + `default_model` do usuário
7. padrão embutido para aquela tarefa

(O `embedding` ignora os fallbacks genéricos — um modelo de chat não é um modelo de
embedding.)

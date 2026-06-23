# Como rotear tarefas para diferentes modelos

> 🌐 **Idiomas:** [English](../../en/how-to/per-task-routing.md) · [简体中文](../../zh-CN/how-to/per-task-routing.md) · [繁體中文](../../zh-TW/how-to/per-task-routing.md) · [日本語](../../ja/how-to/per-task-routing.md) · [한국어](../../ko/how-to/per-task-routing.md) · [Español](../../es/how-to/per-task-routing.md) · [Français](../../fr/how-to/per-task-routing.md) · [Italiano](../../it/how-to/per-task-routing.md) · **Português (BR)** · [Português (PT)](../../pt-PT/how-to/per-task-routing.md) · [Русский](../../ru/how-to/per-task-routing.md) · [العربية](../../ar/how-to/per-task-routing.md) · [हिन्दी](../../hi/how-to/per-task-routing.md) · [বাংলা](../../bn/how-to/per-task-routing.md) · [Tiếng Việt](../../vi/how-to/per-task-routing.md)

O Veles não está preso a um único modelo. Cada **tarefa** interna pode usar um
`provider:model` diferente — um modelo barato para a compressão de contexto, um
forte para o agente principal, um modelo de visão para imagens. Este é o sistema de
*roteamento de ensemble*.

## Tipos de tarefa

| Tarefa | Usada para |
|---|---|
| `default` | O loop do agente principal |
| `curator` | Consolidação de sessão → wiki |
| `compressor` | Compressão de contexto por janela deslizante |
| `insights` | Extração de insights após a execução |
| `skills` | Execução de skills |
| `advisor` | A autoverificação `advisor_review` |
| `vision` | `image_describe` (quando um adaptador de visão está conectado) |
| `embedding` | Similaridade do `veles skill dedup` |

## Veja o roteamento atual

```bash
veles route show
```

Isso imprime o `provider:model` resolvido para cada tarefa e um rótulo `source`
indicando qual camada o decidiu.

## Fixe uma tarefa em um modelo

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

## Reset

```bash
veles route reset compressor   # one task back to default
veles route reset              # all tasks back to default
```

## Dicas em linguagem natural no AGENTS.md

Você pode expressar o roteamento em prosa no `AGENTS.md` (ex.: "use um modelo
barato para a compressão"). O Veles analisa essas dicas e gera automaticamente um
`routing.nl.toml`:

```bash
veles route refresh            # re-parse AGENTS.md hints
veles route refresh --force    # even if AGENTS.md hasn't changed
```

Entradas explícitas em `[routing.tasks]` sempre prevalecem sobre as dicas em NL.

## Ordem de resolução

Para cada tarefa, vence a primeira camada que produzir uma especificação:

1. `[routing.tasks][task]` do projeto
2. `[routing.tasks].default` do projeto
3. dica em NL do projeto (`routing.nl.toml`)
4. base `[provider]` do projeto
5. `[routing.tasks][task]` / `.default` do usuário
6. `[user] default_provider` + `default_model` do usuário

Se nada disso resolver, **não há fallback fixo no código** — a tarefa fica sem
definição e quem a chama degrada (pula a funcionalidade) ou falha de forma clara,
em vez de recorrer silenciosamente a um modelo de nuvem.

(`embedding` pula os catch-alls — um modelo de chat não é um modelo de embedding —
então apenas um `[routing.tasks].embedding` explícito o resolve.)

# Orquestração multiagente

> 🌐 **Idiomas:** [English](../../en/explanation/multi-agent-orchestration.md) · [简体中文](../../zh-CN/explanation/multi-agent-orchestration.md) · [繁體中文](../../zh-TW/explanation/multi-agent-orchestration.md) · [日本語](../../ja/explanation/multi-agent-orchestration.md) · [한국어](../../ko/explanation/multi-agent-orchestration.md) · [Español](../../es/explanation/multi-agent-orchestration.md) · [Français](../../fr/explanation/multi-agent-orchestration.md) · [Italiano](../../it/explanation/multi-agent-orchestration.md) · **Português (BR)** · [Português (PT)](../../pt-PT/explanation/multi-agent-orchestration.md) · [Русский](../../ru/explanation/multi-agent-orchestration.md) · [العربية](../../ar/explanation/multi-agent-orchestration.md) · [हिन्दी](../../hi/explanation/multi-agent-orchestration.md) · [বাংলা](../../bn/explanation/multi-agent-orchestration.md) · [Tiếng Việt](../../vi/explanation/multi-agent-orchestration.md)

Para trabalhos complexos, o Veles pode dividir uma tarefa entre um **gerente** e
subagentes **trabalhadores** especializados, em vez de fazer tudo em um único
contexto. Esta página explica o modelo; para ativá-lo, veja
[modo gerente](../how-to/long-running-tasks.md#manager-mode--decompose-any-prompt).

## O formato

```
            manager  (decomposes the task, never writes the final answer)
           /    |    \
    explorer  writer  advisor   (specialised workers, run in parallel)
```

- O **gerente** planeja a decomposição e coordena — mas **não** escreve o
  entregável final ele mesmo.
- Os **trabalhadores** têm prompts de sistema específicos por papel: `explorer`
  reúne informações, `writer` produz a resposta, `advisor` revisa. O conjunto é
  extensível.
- No final, o gerente escreve um relatório curto na memória.

## Sem telefone sem fio

Uma regra fundamental: os artefatos intermediários chegam ao sintetizador
**literalmente**, não como uma paráfrase do gerente. As descobertas de um explorer
são entregues diretamente ao writer, de modo que os detalhes não se percam por uma
cadeia de resumos. É isso que faz a decomposição agregar qualidade em vez de diluí-la.

## Por que "o gerente nunca escreve"

Se o coordenador também escrevesse a resposta, ele ficaria tentado a encurtar
caminho ignorando os trabalhadores e perderia o benefício da especialização.
Manter a síntese em um `writer` dedicado (alimentado com entradas literais) impõe
a divisão de trabalho. O Veles transforma isso em uma garantia de tempo de execução.

## Quando ajuda — e quando não

A decomposição compensa para tarefas amplas ou multifacetadas (audite este
código-base, pesquise esta questão sob vários ângulos). Para uma solicitação
rápida e de contexto único, ela só adiciona overhead — e é por isso que o modo
gerente é de **adesão explícita**, desativado por padrão (`veles run --manager` ou
`VELES_MANAGER_MODE=1`).

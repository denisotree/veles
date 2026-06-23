# Orquestração multi-agente

> 🌐 **Languages:** **English** · [Русский](../../ru/explanation/multi-agent-orchestration.md)

Para trabalho complexo, o Veles pode dividir uma tarefa entre um **gestor** e
subagentes **worker** especializados, em vez de fazer tudo num único contexto. Esta página
explica o modelo; para o ativar, consulte
[modo gestor](../how-to/long-running-tasks.md#manager-mode--decompose-any-prompt).

## A forma

```
            gestor  (decompõe a tarefa, nunca escreve a resposta final)
           /    |    \
    explorer  writer  advisor   (workers especializados, executados em paralelo)
```

- O **gestor** planeia a decomposição e coordena — mas **não** escreve, ele próprio, o
  resultado final.
- Os **workers** têm prompts de sistema específicos do papel: `explorer` recolhe, `writer`
  produz a resposta, `advisor` revê. O conjunto é extensível.
- No final, o gestor escreve um breve relatório na memória.

## Sem jogo do telefone

Uma regra fundamental: os artefactos intermédios chegam ao sintetizador **verbatim**, e
não como paráfrase do gestor. Os achados de um explorer são entregues diretamente ao
writer, para que o detalhe não se perca através de uma cadeia de resumos. É isto que faz
com que a decomposição acrescente qualidade em vez de a diluir.

## Porquê "o gestor nunca escreve"

Se o coordenador também escrevesse a resposta, sentir-se-ia tentado a atalhar os workers e
perderia o benefício da especialização. Manter a síntese num `writer` dedicado (alimentado
com entradas verbatim) impõe a divisão do trabalho. O Veles torna isto uma garantia em
tempo de execução.

## Quando ajuda — e quando não ajuda

A decomposição compensa em tarefas amplas ou multifacetadas (auditar este código,
investigar esta questão sob vários ângulos). Para um pedido rápido de contexto único,
apenas acrescenta sobrecarga — razão pela qual o modo gestor é **opt-in explícito**,
desligado por omissão (`veles run --manager` ou `VELES_MANAGER_MODE=1`).

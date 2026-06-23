# Modos de execução

> 🌐 **Idiomas:** **English** · [Русский](../../ru/explanation/modes.md)

Na TUI, cada prompt é tratado por um **modo de execução** — uma estratégia que
decide quanta autonomia e quais ferramentas o turno recebe. Alterne os modos com
`Shift+Tab`; a ordem é `auto → planning → writing → goal`.

## Os quatro modos

### `writing` — chat direto
O modo mais direto: seu prompt vai para o agente com todo o conjunto de
ferramentas disponível, e ele responde. Use-o para trabalho comum em que você
quer que o agente aja.

### `planning` — pesquisa somente leitura + um plano
As mutações ficam bloqueadas (sem `write_file`, sem `run_shell`). O agente usa
ferramentas de leitura/busca para reunir contexto e, em seguida, produz um
artefato de plano estruturado. Use-o para pensar antes de tocar em qualquer coisa
— ou passe `--plan` para o `veles run` para obter o mesmo efeito na CLI.

### `auto` — roteamento inteligente (padrão)
Uma classificação rápida decide se seu prompt é uma solicitação direta ou exige
planejamento e, então, despacha para `writing` ou `planning` conforme o caso. É o
fallback mais inteligente quando você não expressou intenção, e por isso é a
primeira parada padrão no ciclo.

### `goal` — objetivo de longo prazo
Conduz uma máquina de estados finitos para um objetivo de várias etapas: ele
entrevista você para esclarecer, confirma um plano, executa as etapas (com
verificações de advisor) e valida a condição de conclusão — tudo sob orçamentos
explícitos. O equivalente na CLI é a família de comandos
[`veles goal`](../how-to/long-running-tasks.md#goals--objectives-with-budgets-and-checkpoints).

## Por que os modos existem

Solicitações diferentes pedem quantidades diferentes de cautela. Uma pergunta
rápida não deveria exigir cerimônia; uma mudança arriscada se beneficia de uma
passagem de planejamento somente leitura primeiro; um grande objetivo precisa de
orçamentos e checkpoints. Os modos tornam essa escolha explícita e alternável por
turno, em vez de fixar um único comportamento na sessão inteira.

Quando você troca de modo no meio da sessão, o agente é informado das novas regras,
de modo que seu comportamento muda imediatamente.

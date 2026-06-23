# Modos de execução

> 🌐 **Idiomas:** [English](../../en/explanation/modes.md) · [简体中文](../../zh-CN/explanation/modes.md) · [繁體中文](../../zh-TW/explanation/modes.md) · [日本語](../../ja/explanation/modes.md) · [한국어](../../ko/explanation/modes.md) · [Español](../../es/explanation/modes.md) · [Français](../../fr/explanation/modes.md) · [Italiano](../../it/explanation/modes.md) · [Português (BR)](../../pt-BR/explanation/modes.md) · **Português (PT)** · [Русский](../../ru/explanation/modes.md) · [العربية](../../ar/explanation/modes.md) · [हिन्दी](../../hi/explanation/modes.md) · [বাংলা](../../bn/explanation/modes.md) · [Tiếng Việt](../../vi/explanation/modes.md)

Na TUI, cada prompt é tratado por um **modo de execução** — uma estratégia que decide
quanta autonomia e que ferramentas o turno recebe. Alterne entre modos com `Shift+Tab`; a
ordem é `auto → planning → writing → goal`.

## Os quatro modos

### `writing` — conversa direta
O modo direto: o seu prompt vai para o agente com todo o conjunto de ferramentas
disponível, e ele responde. Use-o para trabalho corrente em que pretende que o agente aja.

### `planning` — investigação só de leitura + um plano
As mutações são bloqueadas (sem `write_file`, sem `run_shell`). O agente usa ferramentas de
leitura/pesquisa para reunir contexto e depois produz um artefacto de plano estruturado.
Use-o para pensar antes de tocar em algo — ou passe `--plan` ao `veles run` para o mesmo
efeito na CLI.

### `auto` — encaminhamento inteligente (predefinição)
Uma classificação rápida decide se o seu prompt é um pedido direto ou se exige
planeamento, despachando depois para `writing` ou `planning` conforme o caso. É a opção de
recurso mais inteligente quando não exprimiu a sua intenção, razão pela qual é a primeira
paragem predefinida no ciclo.

### `goal` — objetivo de longo horizonte
Aciona uma máquina de estados finitos para um objetivo de vários passos: entrevista-o para
clarificar, confirma um plano, executa passos (com verificações do advisor) e verifica a
condição de conclusão — tudo sob orçamentos explícitos. O equivalente na CLI é a família de
comandos [`veles goal`](../how-to/long-running-tasks.md#goals--objectives-with-budgets-and-checkpoints).

## Porque existem os modos

Pedidos diferentes querem quantidades diferentes de cautela. Uma pergunta rápida não devia
exigir cerimónia; uma alteração arriscada beneficia de uma passagem de planeamento só de
leitura primeiro; um grande objetivo precisa de orçamentos e pontos de controlo. Os modos
tornam essa escolha explícita e comutável por turno, em vez de fixar um único comportamento
para toda a sessão.

Quando alterna a meio de uma sessão, o agente é informado das novas regras para que o seu
comportamento mude de imediato.

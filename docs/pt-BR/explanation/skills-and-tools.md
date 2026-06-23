# Skills e ferramentas como capacidade acumulada

> 🌐 **Idiomas:** **English** · [Русский](../../ru/explanation/skills-and-tools.md)

O Veles começa com um conjunto mínimo de ferramentas e skills e o **expande** à
medida que trabalha. Esta página explica a diferença entre os dois e como eles se
acumulam. Para os comandos, veja [gerenciar skills e ferramentas](../how-to/manage-skills-and-tools.md).

## Ferramentas vs skills

- Uma **ferramenta** é uma única ação executável — ler um arquivo, rodar um
  comando de shell, buscar uma URL, pesquisar na web, escrever uma página de wiki.
  As ferramentas são o que o modelo chama.
- Uma **skill** é um *processo* formalizado — um `SKILL.md` com um corpo de prompt
  e uma lista de ferramentas permitidas que roda como um subagente focado. As
  skills compõem ferramentas em um fluxo de trabalho repetível (por exemplo, as
  skills `ingest`/`query`/`lint` do LLM-Wiki).

## Início mínimo, expansão sob demanda

O Veles inicializa com apenas o suficiente para ser útil, mais um lugar conhecido
de onde puxar mais. Instalar extras (uma skill, uma ferramenta, um módulo) pede
aprovação por padrão; você pode conceder autonomia permanente. Isso mantém um
projeto novo enxuto, ao mesmo tempo que permite que a capacidade cresça onde for
necessária.

## Como a capacidade se acumula

1. **O Veles escreve suas próprias ferramentas.** Quando percebe uma tarefa
   recorrente, ele pode criar uma ferramenta Python limpa, tipada e reutilizável
   em `<project>/.veles/tools/` (com uma passagem de revisão de código por advisor).
   A ferramenta entra no registro com telemetria.
2. **Processos recorrentes viram skills.** Um detector de padrões identifica
   sequências de ferramentas recorrentes e propõe formalizá-las como uma skill;
   skills podem usar `extends:` em outra skill para herdar seu corpo e ferramentas.
3. **A telemetria orienta o ranqueamento.** Cada ferramenta/skill carrega contagens
   de uso/sucesso/erro. Elas alimentam a dedup (`veles skill dedup`) e as sugestões
   de promoção.

## Dois escopos, com promoção

Tanto ferramentas quanto skills existem em dois níveis:

- **Local do projeto** (`<project>/.veles/`) — visível apenas aqui.
- **Global do usuário** (`~/.veles/`) — disponível em todos os projetos.

Uma capacidade que se prova em um projeto pode ser **promovida** ao escopo de
usuário para que todos os projetos se beneficiem (`veles skill promote`,
`veles tool promote`), ou **rebaixada** de volta. É assim que o Veles leva
fluxos de trabalho conquistados a duras penas entre projetos.

## Por que um registro, e não apenas arquivos

Armazenar skills/ferramentas como arquivos simples os mantém inspecionáveis e
editáveis; armazenar sua *telemetria* em `memory.db` permite que o Veles raciocine
sobre quais delas realmente funcionam. A combinação é o que transforma "uma pasta
de scripts" em capacidade acumulada e autocurada.

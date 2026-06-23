# Skills e ferramentas como capacidade acumulada

> 🌐 **Idiomas:** [English](../../en/explanation/skills-and-tools.md) · [简体中文](../../zh-CN/explanation/skills-and-tools.md) · [繁體中文](../../zh-TW/explanation/skills-and-tools.md) · [日本語](../../ja/explanation/skills-and-tools.md) · [한국어](../../ko/explanation/skills-and-tools.md) · [Español](../../es/explanation/skills-and-tools.md) · [Français](../../fr/explanation/skills-and-tools.md) · [Italiano](../../it/explanation/skills-and-tools.md) · [Português (BR)](../../pt-BR/explanation/skills-and-tools.md) · **Português (PT)** · [Русский](../../ru/explanation/skills-and-tools.md) · [العربية](../../ar/explanation/skills-and-tools.md) · [हिन्दी](../../hi/explanation/skills-and-tools.md) · [বাংলা](../../bn/explanation/skills-and-tools.md) · [Tiếng Việt](../../vi/explanation/skills-and-tools.md)

O Veles começa com um conjunto mínimo de ferramentas e skills e fá-lo **crescer** à medida
que trabalha. Esta página explica a diferença entre os dois e como se acumulam. Para os
comandos, consulte [gerir skills e ferramentas](../how-to/manage-skills-and-tools.md).

## Ferramentas vs skills

- Uma **ferramenta** é uma única ação executável — ler um ficheiro, executar um comando de
  shell, obter um URL, pesquisar na web, escrever uma página de wiki. As ferramentas são o
  que o modelo invoca.
- Uma **skill** é um *processo* formalizado — um `SKILL.md` com um corpo de prompt e uma
  lista de ferramentas permitidas que corre como um subagente focado. As skills compõem
  ferramentas num fluxo de trabalho repetível (por exemplo, os `ingest`/`query`/`lint` da
  LLM-Wiki).

## Arranque mínimo, expansão a pedido

O Veles arranca apenas com o necessário para ser útil, mais um local conhecido de onde
puxar mais. Instalar extras (uma skill, uma ferramenta, um módulo) pede aprovação por
omissão; pode conceder autonomia permanente. Isto mantém um projeto novo enxuto, deixando a
capacidade crescer onde é precisa.

## Como se acumula a capacidade

1. **O Veles escreve as suas próprias ferramentas.** Quando deteta uma tarefa repetida,
   pode criar uma ferramenta Python limpa, tipada e reutilizável em
   `<project>/.veles/tools/` (com uma passagem de revisão de código pelo advisor). A
   ferramenta junta-se ao registo com telemetria.
2. **Processos repetidos tornam-se skills.** Um detetor de padrões identifica sequências de
   ferramentas recorrentes e propõe formalizá-las como uma skill; as skills podem usar
   `extends:` sobre outra skill para herdar o seu corpo e ferramentas.
3. **A telemetria orienta a ordenação.** Cada ferramenta/skill carrega contagens de
   uso/sucesso/erro. Estas alimentam a deduplicação (`veles skill dedup`) e as sugestões de
   promoção.

## Dois âmbitos, com promoção

Tanto as ferramentas como as skills existem a dois níveis:

- **Local ao projeto** (`<project>/.veles/`) — visível apenas aqui.
- **Global do utilizador** (`~/.veles/`) — disponível em todos os projetos.

Uma capacidade que se prova num projeto pode ser **promovida** ao âmbito do utilizador para
que todos os projetos beneficiem (`veles skill promote`, `veles tool promote`), ou
**despromovida** de volta. É assim que o Veles transporta fluxos de trabalho conquistados a
custo entre projetos.

## Porquê um registo, e não só ficheiros

Guardar skills/ferramentas como ficheiros simples mantém-nos inspecionáveis e editáveis;
guardar a sua *telemetria* em `memory.db` permite ao Veles raciocinar sobre quais é que
realmente funcionam. A combinação é o que transforma "uma pasta de scripts" em capacidade
acumulada e auto-curada.

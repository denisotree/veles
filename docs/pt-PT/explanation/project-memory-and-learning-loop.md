# Memória do projeto e o ciclo de aprendizagem

> 🌐 **Languages:** **English** · [Русский](../../ru/explanation/project-memory-and-learning-loop.md)

A característica que define o Veles é que ele **lembra-se** e **aprende** por projeto. Esta
página explica o que é essa memória e como o ciclo de aprendizagem a mantém útil.

## A memória é um artefacto estruturado

A memória do projeto vive em `<project>/.veles/` — `memory.db` (SQLite, a fonte da
verdade) mais uma árvore `.veles/memory/` legível por humanos (vistas renderizadas de
insights, resumos de sessões, propostas, um registo de operações do sistema). É **separada
do seu conteúdo** e funciona de forma idêntica sob qualquer layout (wiki, notes ou bare).
Não é um despejo da transcrição da conversa — é um conjunto de camadas estruturadas:

- **Registo de sessões** — cada conversa, uma linha por turno, indexada em texto completo.
- **Regras** — imperativos curtos que o agente deve seguir (`format`, `do`, `don't`,
  `preference`), injetados no prompt de sistema estável.
- **Insights** — lições destiladas das sessões. A linha SQL é canónica (o recall, o
  envelhecimento e a deduplicação operam sobre ela); uma vista em markdown é renderizada
  para `.veles/memory/insights/` para humanos e exportações.
- **Mapa da árvore do projeto** — um mapa de ficheiros em cache, etiquetado
  semanticamente, para que o agente leia os 3 a 5 ficheiros relevantes, e não a árvore
  inteira.
- **Registos de skills e ferramentas** — com telemetria (contagens de uso/sucesso/erro)
  que a ordenação e a deduplicação usam.

Consulte a lista de tabelas em [layout do projeto](../reference/project-layout.md#project-memory-velesmemorydb).

## Recall: contexto pequeno, trazido a pedido

O `AGENTS.md` é deliberadamente pequeno. Quando pergunta algo, o Veles traz apenas o que é
relevante: turnos passados correspondentes (texto completo + reordenação vetorial
opcional), regras e insights aplicáveis e os ficheiros que o mapa da árvore do projeto
pontua mais alto. Isto mantém cada chamada ao modelo focada e barata, em vez de despejar
tudo.

## O ciclo de aprendizagem

A experiência torna-se conhecimento duradouro através de três mecanismos:

### Insights — captar lições
Após uma execução, um extrator procura coisas que valha a pena recordar: feedback
explícito do tipo "lembra-te de X" / "nunca Y" e padrões erro-de-ferramenta→recuperação
(uma falha seguida de uma correção). Destila-os em insights e regras para que o mesmo erro
não se repita.

### Curador — consolidar sessões
O curador destila sessões mais antigas em memória duradoura: insights e regras em SQL
sempre; adicionalmente uma página `wiki/sessions/` quando o layout do projeto ativa a
engine de wiki. Corre em temporizadores de inatividade/pós-turno, ou a pedido com
`veles curate`.

### Dreaming — manutenção em segundo plano
O `veles dream` (e o daemon quando está inativo) extrai insights, deduplica skills e
insights, sugere promoções e (sob um layout de wiki) faz lint à wiki — mantendo a memória
atualizada sem o bloquear. Acrescente `--include-consolidation` para uma passagem de LLM
mais profunda.

## Compressão de contexto

As conversas longas são mantidas abaixo do limite de contexto do modelo por um compressor
de janela deslizante: quando o histórico em memória ultrapassa um limiar de tokens, o meio
é resumido (por um modelo barato encaminhado) e substituído por um apontador para o resumo
gravado em `.veles/memory/sessions/`. O histórico completo permanece sempre em `memory.db`
— apenas a janela em memória é comprimida, pelo que é sem perdas em disco.

## Porque é que isto importa

Como a memória é estruturada e o ciclo corre continuamente, um projeto Veles torna-se
**mais útil quanto mais o usa** — aprende as suas convenções, evita erros repetidos e
fundamenta as respostas naquilo que realmente viu.

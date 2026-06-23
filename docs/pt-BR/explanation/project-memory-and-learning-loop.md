# Memória de projeto e o loop de aprendizado

> 🌐 **Idiomas:** [English](../../en/explanation/project-memory-and-learning-loop.md) · [简体中文](../../zh-CN/explanation/project-memory-and-learning-loop.md) · [繁體中文](../../zh-TW/explanation/project-memory-and-learning-loop.md) · [日本語](../../ja/explanation/project-memory-and-learning-loop.md) · [한국어](../../ko/explanation/project-memory-and-learning-loop.md) · [Español](../../es/explanation/project-memory-and-learning-loop.md) · [Français](../../fr/explanation/project-memory-and-learning-loop.md) · [Italiano](../../it/explanation/project-memory-and-learning-loop.md) · **Português (BR)** · [Português (PT)](../../pt-PT/explanation/project-memory-and-learning-loop.md) · [Русский](../../ru/explanation/project-memory-and-learning-loop.md) · [العربية](../../ar/explanation/project-memory-and-learning-loop.md) · [हिन्दी](../../hi/explanation/project-memory-and-learning-loop.md) · [বাংলা](../../bn/explanation/project-memory-and-learning-loop.md) · [Tiếng Việt](../../vi/explanation/project-memory-and-learning-loop.md)

A característica que define o Veles é que ele **lembra** e **aprende** por projeto.
Esta página explica o que é essa memória e como o loop de aprendizado a mantém útil.

## A memória é um artefato estruturado

A memória de projeto fica em `<project>/.veles/` — `memory.db` (SQLite, a fonte
da verdade) mais uma árvore legível por humanos em `.veles/memory/` (visualizações
de insights renderizadas, resumos de sessão, propostas, um diário de operações do
sistema). Ela é **separada do seu conteúdo** e funciona de forma idêntica sob
qualquer layout (wiki, notes ou bare). Não é um despejo de transcrição de chat —
é um conjunto de camadas estruturadas:

- **Log de sessão** — cada conversa, uma linha por turno, com índice de texto
  completo.
- **Regras** — imperativos curtos que o agente deve seguir (`format`, `do`, `don't`,
  `preference`), injetados no prompt de sistema estável.
- **Insights** — lições destiladas das sessões. A linha SQL é canônica
  (recall, envelhecimento e dedup operam sobre ela); uma visualização em markdown
  é renderizada para `.veles/memory/insights/` para humanos e exportações.
- **Mapa da árvore do projeto** — um mapa de arquivos em cache, com tags
  semânticas, para que o agente leia os 3–5 arquivos relevantes, não a árvore
  inteira.
- **Registros de skills e ferramentas** — com telemetria (contagens de uso/sucesso/erro)
  que o ranqueamento e a dedup utilizam.

Veja a lista em tabela em [layout do projeto](../reference/project-layout.md#project-memory-velesmemorydb).

## Recall: contexto pequeno, puxado sob demanda

O `AGENTS.md` é deliberadamente pequeno. Quando você pergunta algo, o Veles puxa
apenas o que é relevante: turnos passados que coincidem (texto completo + reranking
vetorial opcional), regras e insights aplicáveis e os arquivos que o mapa da árvore
do projeto pontua mais alto. Isso mantém cada chamada ao modelo focada e barata,
em vez de despejar tudo.

## O loop de aprendizado

A experiência se torna conhecimento durável por meio de três mecanismos:

### Insights — capturando lições
Após uma execução, um extrator procura coisas que vale a pena lembrar: feedback
explícito de "lembre X" / "nunca Y" e padrões de erro de ferramenta→recuperação
(uma falha seguida de uma correção). Ele destila isso em insights e regras para
que o mesmo erro não se repita.

### Curador — consolidando sessões
O curador destila sessões mais antigas em memória durável: insights e regras SQL
sempre; adicionalmente uma página `wiki/sessions/` quando o layout do projeto
ativa o engine de wiki. Ele roda em temporizadores de ociosidade/pós-turno, ou
sob demanda com `veles curate`.

### Sonho — manutenção em segundo plano
`veles dream` (e o daemon quando ocioso) extrai insights, deduplica skills e
insights, sugere promoções e (sob um layout de wiki) faz o lint da wiki —
mantendo a memória atualizada sem bloquear você. Adicione `--include-consolidation`
para uma passagem mais profunda com LLM.

## Compressão de contexto

Conversas longas são mantidas abaixo do limite de contexto do modelo por um
compressor de janela deslizante: quando o histórico em memória cruza um limiar de
tokens, o meio é resumido (por um modelo barato roteado) e substituído por um
ponteiro para o resumo salvo em `.veles/memory/sessions/`. O histórico completo
sempre permanece em `memory.db` — apenas a janela em memória é comprimida, então é
sem perdas em disco.

## Por que isso importa

Como a memória é estruturada e o loop roda continuamente, um projeto Veles fica
**mais útil quanto mais você o usa** — ele aprende suas convenções, evita erros
repetidos e fundamenta as respostas no que realmente viu.

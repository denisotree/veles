# Referência da CLI

> 🌐 **Idiomas:** [English](../../en/reference/cli.md) · [简体中文](../../zh-CN/reference/cli.md) · [繁體中文](../../zh-TW/reference/cli.md) · [日本語](../../ja/reference/cli.md) · [한국어](../../ko/reference/cli.md) · [Español](../../es/reference/cli.md) · [Français](../../fr/reference/cli.md) · [Italiano](../../it/reference/cli.md) · [Português (BR)](../../pt-BR/reference/cli.md) · **Português (PT)** · [Русский](../../ru/reference/cli.md) · [العربية](../../ar/reference/cli.md) · [हिन्दी](../../hi/reference/cli.md) · [বাংলা](../../bn/reference/cli.md) · [Tiếng Việt](../../vi/reference/cli.md)

Todos os comandos, subcomandos e opções do Veles. Execute `veles <command> --help`
para obter a assinatura autoritativa e sempre actualizada — esta página espelha os
analisadores de argumentos em `src/veles/cli/_parsers/`.

```
veles [--no-wizard] <command> [subcommand] [options]
```

- `--no-wizard` — ignora o assistente de configuração do primeiro arranque mesmo que
  `~/.veles/config.toml` esteja em falta (condicionado também a um TTY e a
  `VELES_NO_WIZARD=1`). O assistente só antecede comandos que iniciam um agente
  (`veles` simples, `run`, `daemon`, `channel`, …); verbos administrativos como
  `module`, `tool` e `doctor` nunca o abrem.
- Sem argumentos, `veles` lança a [TUI](tui.md) interactiva.

A maioria dos comandos do agente aceita as [opções partilhadas do ciclo do agente](#shared-agent-loop-flags)
e os [nomes de fornecedores](#provider-names) listados no fim.

---

## Ciclo de vida do projecto

### `veles init [name]`
Cria um novo projecto Veles no directório actual (um directório de estado `.veles/`
+ `AGENTS.md` + o scaffold de conteúdo do pack de layout escolhido).

| Opção | Predefinição | Finalidade |
|---|---|---|
| `name` (posicional) | nome base do cwd | Nome do projecto |
| `--layout <name>` | `bare` (perguntado num terminal) | Pack de layout para o scaffold de conteúdo (`bare`, um pack instalado de um registo como `llm-wiki` ou `notes`, ou um pack personalizado de `~/.veles/layouts/`). Um pack não instalado é oferecido para instalação; recusar não cria nada |
| `--force` | desligado | Recria `.veles/` mesmo que já exista |

### `veles schema {validate,edit,fix}`
Valida ou edita o `AGENTS.md` (o ficheiro de contexto do projecto).

- `validate` — verifica as secções H2 obrigatórias.
- `edit` — abre o `AGENTS.md` em `$EDITOR` (predefinição `vi`), valida ao sair.
- `fix` — adiciona interactivamente as secções em falta através de um assistente LLM.

### `veles self-doc [refresh|show]`
Gera e mostra a auto-documentação do projecto — no armazenamento de páginas do layout
quando este tem um (a wiki: `wiki/self-doc/overview.md`), caso contrário em
`.veles/memory/self-doc.md`.
`veles self-doc` simples mostra a página actual; `refresh` regenera-a.

### `veles doctor`
Executa verificações de saúde sobre o estado global do utilizador e o projecto activo.
Funciona com ou sem um projecto activo.

| Opção | Predefinição | Finalidade |
|---|---|---|
| `--json` | desligado | Emite um relatório JSON |
| `--strict` | desligado | Termina com código diferente de zero perante qualquer aviso (bloqueio em CI) |
| `--fix` | desligado | Tenta reparações seguras antes de verificar — actualmente reconstrói um índice de recuperação de memória (FTS) corrompido |

O `doctor` também valida as secções de `config.toml` relevantes para a segurança
(`[channels.*]`, `[daemon.*]`, `[mcp.servers.*]`) e reporta chaves desconhecidas como
um erro — uma gralha como `whitlist` em vez de `whitelist` desactiva silenciosamente um
controlo de acesso, por isso falha de forma ruidosa aqui.

### `veles export {full,template} <path>`
Empacota o projecto num bundle `.tar.gz`. Ver [Salvaguardar e partilhar](../how-to/backup-and-share.md).

- `full <path>` — projecto inteiro (`.veles/` + `AGENTS.md`), menos os efémeros de runtime.
- `template <path>` — subconjunto higienizado (esquema + skills + módulos + páginas de
  wiki que não sejam sessões); remove `memory.db`, `sources/`, `sessions/`, concessões de
  `trust`, e redige os dados pessoais (PII) do texto.

### `veles import <path>`
Restaura um bundle criado por `veles export`.

| Opção | Predefinição | Finalidade |
|---|---|---|
| `path` (posicional) | — | Caminho do bundle (`.tar.gz`) |
| `--into <dir>` | cwd | Directório de destino |
| `--force` | desligado | Sobrescreve um `.veles/` existente no destino |

---

## Executar o agente

### `veles run "<prompt>"`
Executa um único prompt de ponta a ponta com persistência de memória e os gatilhos de
curador/aprendizagem. Aceita todas as [opções partilhadas do ciclo do agente](#shared-agent-loop-flags)
mais:

| Opção | Predefinição | Finalidade |
|---|---|---|
| `--resume <session_id>` | sessão nova | Continua uma sessão existente |
| `--output {text,json}` | `text` | `json`: imprime um único objecto (estado, código de saída, sessão, resposta, turnos, tokens, orçamento, avisos) em vez da resposta |
| `--manager` | desligado | Decompõe através do gestor multi-agente (também `VELES_MANAGER_MODE=1`) |
| `--verify` | desligado | Após a execução, o advisor encaminhado avalia a resposta; perante uma falha confiante, reexecuta no modelo mais forte (também `VELES_VERIFY_MODE=1`) |
| `--plan` | desligado | Modo de planeamento: ler/pesquisar/rascunhar permitido, mutações bloqueadas |
| `--no-agents-md` | desligado | Não injecta o `AGENTS.md` no prompt de sistema |
| `--no-index` | desligado | Não injecta o `wiki/INDEX.md` |
| `--no-compress` | desligado | Desactiva a compressão de contexto por janela deslizante |
| `--no-curator` | desligado | Desactiva os gatilhos do curador para esta execução |
| `--no-insights` | desligado | Desactiva a extracção de insights pós-execução |
| `--no-proposer` | desligado | Desactiva o auto-gatilho do propositor de subprojectos |
| `--no-route-refresh` | desligado | Desactiva o refresh de encaminhamento em LN a partir do `AGENTS.md` |
| `--no-suggest-promote` | desligado | Desactiva o sugeridor de auto-promoção |
| `--compressor-model <id>` | encaminhado | Sobrepõe o modelo de compressão |
| `--compress-threshold-tokens <n>` | `50000` | Tamanho do histórico que despoleta a compressão |

### `veles tui`
Abre o REPL interactivo. Ver [referência da TUI](tui.md). Aceita as opções partilhadas
do ciclo do agente, `--resume`, as opções `--no-*` de injecção/compressão acima, e:

| Opção | Predefinição | Finalidade |
|---|---|---|
| `--theme <name>` | config ou `everforest` | Tema de cores (everforest, dracula, gruvbox, tokyo-night, catppuccin) |

### `veles add <source>`
*(do módulo `wiki` — `veles registry install llm-wiki` ou `… install wiki`)*
Lê uma fonte (um ficheiro local ou URL `http(s)://`) e sintetiza-a numa página de wiki.
Sem o módulo, `veles add` é um comando desconhecido e o erro indica a instalação.
Aceita as opções partilhadas do ciclo do agente.

### `veles curate`
Executa uma passagem do curador: compacta as sessões não processadas em insights de memória (e em páginas
`wiki/sessions/` quando a engine de wiki está ativa).

| Opção | Predefinição | Finalidade |
|---|---|---|
| `--limit <n>` | uma pequena predefinição | Máximo de sessões a processar nesta execução |

Mais as opções partilhadas do ciclo do agente.

### `veles research "<question>"`
Investigação profunda: decompõe em subperguntas → explora a web em paralelo →
sintetiza um relatório com citações.

| Opção | Predefinição | Finalidade |
|---|---|---|
| `--max-subquestions <n>` | `4` | Ângulos de investigação em paralelo |

Mais as opções partilhadas do ciclo do agente.

### `veles dream`
Executa um ciclo de consolidação de memória em segundo plano (insights → dedup de
skills → sugestões de promoção → lint da wiki, opcionalmente consolidação por LLM).

| Opção | Predefinição | Finalidade |
|---|---|---|
| `--include-consolidation` | desligado | Executa a dispendiosa consolidação por LLM (necessita de uma chave de API) |
| `--dry-run` | desligado | Executa todos os passos mas ignora as escritas em `wiki/state` |
| `--skip-insights` / `--skip-dedup` / `--skip-promote` / `--skip-lint` | desligado | Ignora passos individuais |
| `--consolidation-model <id>` | encaminhado (recorre a `anthropic/claude-haiku-4.5`) | Sobrepõe o modelo de consolidação |
| `--provider <name>` | encaminhado | Fornecedor para o subagente de consolidação (omitir para usar o fornecedor encaminhado do projecto) |
| `--project-root <path>` | descobrir | Sobreposição do projecto |

---

## Conhecimento: skills, ferramentas, módulos

### `veles skill {list,show,add,remove,promote,demote,dedup,suggest-promote}`

| Subcomando | Finalidade |
|---|---|
| `list` | Lista as skills no projecto activo (com telemetria) |
| `show <name>` | Imprime o `SKILL.md` de uma skill |
| `add <source> [--name N] [--scope project\|user] [-y]` | Instala a partir de um URL git ou caminho local |
| `remove <name> [--scope project\|user] [-y]` | Apaga uma skill instalada |
| `promote <name> [--keep-telemetry]` | Copia uma skill de projecto para o âmbito do utilizador (`~/.veles/skills/`) |
| `demote <name> [-y]` | Copia uma skill de utilizador para o projecto activo |
| `dedup [--mode auto\|embedding\|tfidf] [--embedding-threshold f] [--tfidf-threshold f]` | Encontra skills quase duplicadas |
| `suggest-promote [--save] [--min-uses n] [--min-success-rate f]` | Lista skills que cumprem o limiar de auto-promoção |

### `veles tool {list,show,promote,approve}`

| Subcomando | Finalidade |
|---|---|
| `list` | Lista as ferramentas catalogadas no `memory.db` deste projecto |
| `show <name>` | Imprime o manifesto + telemetria de uma ferramenta |
| `promote <name> [-y]` | Move uma ferramenta de projecto para `~/.veles/tools/` (transversal a projectos) |
| `approve [<name>] [--all] [-y] [--sha256 H]` | Revê + aprova um ficheiro de ferramenta auto-escrito para que o carregador o execute |

As ferramentas auto-escritas (`.veles/tools/*.py`) executam o seu código ao nível do
módulo quando o carregador as importa, por isso um ficheiro novo ou editado **não é
carregado enquanto não o aprovares** — `veles tool approve` mostra o código e regista o
seu hash. `veles tool approve` simples lista o que está pendente, com o sha256 de cada
ficheiro. É por isto que uma ferramenta escrita pelo agente precisa de um passo de
revisão antes de se tornar invocável.

Sem um terminal (um script de implementação), aprova um ficheiro pelo hash revisto:
`veles tool approve <name> --sha256 <hash>` — falha se o ficheiro mudou entretanto.
`-y` salta a confirmação apenas num terminal.

### `veles module {list,show,add,remove,approve}`

| Subcomando | Finalidade |
|---|---|
| `list [--user]` | Lista os módulos instalados (ambos os âmbitos, com uma coluna `scope`, a não ser com `--user`) |
| `show <name> [--user]` | Imprime o manifesto de um módulo e o sha256 dos seus ficheiros |
| `add <source> [--name N] [--user] [-y]` | Instala um módulo a partir de um URL git ou caminho local |
| `remove <name> [--user] [-y]` | Apaga um módulo instalado |
| `approve <name> [--user] [--sha256 H]` | Aprova um módulo depois de o rever |
| `approve --all [--user]` | Todos os módulos desse âmbito à espera de aprovação, uma confirmação para cada |

`--user` aponta para `~/.veles/modules/` em vez do directório do projecto, pelo que o
módulo carrega em todos os projectos. Um módulo de projecto com o mesmo nome
sobrepõe-se a um de nível de utilizador.
A aprovação pede-te que escrevas `yes` num terminal; sem um, passa o hash dos ficheiros
revistos (o `show` imprime-o) como `--sha256` — falha se os ficheiros mudaram
entretanto. `veles doctor` indica todos os módulos em disco que não carregam.

### `veles registry search [query] [--kind K]`
Pesquisa nos registos ligados (módulos, skills, pacotes de layout, receitas
MCP).

| Opção | Predefinição | Finalidade |
|---|---|---|
| `query` (posicional) | `""` | Filtro por substring |
| `--kind <module\|skill\|layout\|mcp>` | — | Filtra por kind |
| `--json` | desligado | Emite JSON |

---

## Sessões e memória

### `veles sessions {list,show,delete,search}`

| Subcomando | Finalidade |
|---|---|
| `list [--limit n]` | Lista as sessões recentes (predefinição 20) |
| `show <session_id>` | Imprime o histórico completo de turnos de uma sessão |
| `delete <session_id>` | Apaga uma sessão e os seus turnos |
| `search "<query>" [--limit n] [--role user\|assistant\|both\|all] [--since 7d]` | Pesquisa de texto integral (FTS5) sobre o conteúdo dos turnos |

---

## Multi-projecto

### `veles project {list,add,remove,switch}`

| Subcomando | Finalidade |
|---|---|
| `list` | Lista os projectos registados, mais recente primeiro |
| `add <path> [--slug S]` | Regista um directório de projecto existente |
| `remove <slug>` | Cancela o registo de um projecto (ficheiros intactos) |
| `switch <slug>` | Imprime o caminho absoluto do projecto (usar `cd $(veles project switch <slug>)`) |

### `veles subproject {init,list,switch,remove,suggest}`

| Subcomando | Finalidade |
|---|---|
| `init <subdir> [--name N] [--description D]` | Cria + regista um subprojecto |
| `list` | Lista os subprojectos do projecto activo |
| `switch <slug>` | Imprime o caminho absoluto de um subprojecto |
| `remove <slug>` | Cancela o registo de um subprojecto |
| `suggest [--save] [--min-pages n] [--min-similarity f]` | Detecta clusters temáticos e propõe subprojectos |

---

## Encaminhamento e modelos

### `veles route {show,set,reset,refresh}`
Encaminhamento de ensemble por tarefa — que `provider:model` trata cada tipo de tarefa
(`default`, `curator`, `compressor`, `insights`, `skills`, `advisor`, `vision`,
`embedding`). Ver [encaminhamento por tarefa](../how-to/per-task-routing.md).

| Subcomando | Finalidade |
|---|---|
| `show` | Imprime a tabela de encaminhamento resolvida para o projecto activo |
| `set <task> <provider:model>` | Fixa uma tarefa a uma especificação |
| `reset [task]` | Repõe uma tarefa (ou todas) nas predefinições |
| `refresh [--force]` | Reanalisa as pistas de encaminhamento em linguagem natural do `AGENTS.md` |

### `veles models <provider>`
Lista os modelos de um fornecedor. Os fornecedores na nuvem (openrouter/openai/gemini)
ficam em cache 24h; os fornecedores locais, o `codex` e o `antigravity-cli` são sempre ao vivo. Um
fornecedor desconhecido é um erro de uma linha que lista o que existe (saída `2`).

| Opção | Predefinição | Finalidade |
|---|---|---|
| `provider` (posicional) | — | Um id de fornecedor do [catálogo](#provider-names) |
| `--refresh` | desligado | Ignora a cache em disco (apenas nuvem) |
| `--json` | desligado | Emite `{provider, source, models}` como JSON |

---

## Tarefas de longa duração

### `veles goal {list,show,start,pause,resume,cancel}`
Objectivos de horizonte longo com orçamentos e checkpoints.

| Subcomando | Finalidade |
|---|---|
| `list [--status active\|paused\|completed\|blocked\|cancelled]` | Lista objectivos |
| `show <id> [--json]` | Mostra um objectivo |
| `start "<objective>" --done-when D [--scope S] [--max-steps n] [--max-cost-usd f] [--max-wall-time-s n]` | Executa um objectivo até à condição de conclusão (em primeiro plano) |
| `pause <id>` | Pausa; um `start`/`resume` em curso pára no turno seguinte |
| `resume <id>` | Retoma um objectivo em pausa ou interrompido onde parou |
| `cancel <id> [--reason R]` | Cancelar |

### `veles job {add,list,show,pause,resume,trigger,remove,history,tick}`
Tarefas de agente agendadas.

| Subcomando | Finalidade |
|---|---|
| `add --name N --schedule S --prompt P [--repeat n] [--context-from JOB_ID] [--deliver-to TARGET]` | Cria uma tarefa (schedule = cron, `<N><s\|m\|h\|d>`, ou timestamp ISO) |
| `list [--json]` / `show <id>` | Inspecciona tarefas |
| `pause <id>` / `resume <id>` / `trigger <id>` / `remove <id>` | Ciclo de vida |
| `history <id> [--limit n]` | Execuções recentes |
| `tick` | Executa sincronamente todas as tarefas vencidas uma vez (não precisa de daemon; aceita opções do ciclo do agente) |

---

## Segurança e controlo de acesso

### `veles trust {list,set,revoke,clear}`
Concessões persistidas para ferramentas sensíveis (`run_shell`, `write_file`,
`fetch_url`, …). Ver [segurança](../how-to/security-and-permissions.md).

| Subcomando | Finalidade |
|---|---|
| `list` | Mostra as concessões (âmbito de utilizador + projecto) |
| `set <tool> [--scope project\|user]` | Concede uma ferramenta |
| `revoke <tool> [--scope project\|user\|both]` | Remove uma concessão |
| `clear [--scope project\|user\|all]` | Limpa as concessões num âmbito |

### `veles autopilot {enable,disable,status}`
Uma janela limitada no tempo em que os prompts da escada de confiança são auto-permitidos.

| Subcomando | Finalidade |
|---|---|
| `enable --until <DUR>` | Abre uma janela (`+30m`, `+2h`, `+1d`, ou ISO `2026-05-12T18:00:00Z`) |
| `disable` | Fecha a janela agora |
| `status` | Indica se o autopilot está activo |

### `veles secret {set,get,list,delete}`
Segredos suportados pelo chaveiro do SO (chaves de API, tokens de bot).

| Subcomando | Finalidade |
|---|---|
| `set <name> [value]` | Armazena (omitir o valor para interactivo / stdin) |
| `get <name> [--reveal] [--no-env-fallback]` | Consulta (recurso a env por predefinição) |
| `list` | Mostra que segredos canónicos estão configurados |
| `delete <name>` | Remove um segredo |

---

## Daemon e canais

### `veles daemon [start|stop|status|list|restart|delete|session|token]`
Executa/controla o daemon HTTP+WS. `veles daemon` simples abre a TUI do **selector de
daemons** (projecto → daemons → canais). Ver [executar como daemon](../how-to/run-as-daemon.md).

| Subcomando | Finalidade |
|---|---|
| `start [--host H] [--port P] [--foreground] [--name N]` | Arranca um daemon (destaca-se por predefinição) |
| `stop [--name N]` / `status [--name N]` | Pára / inspecciona |
| `list` | Lista os daemons de todos os projectos |
| `restart [target] [--name N]` | Pára + ressuscita no mesmo host/porta |
| `delete <target> [-y]` | Pára + remove do registo |
| `session create <name> [--host H] --port P [--model M] [--provider P] [--mode M]` | Declara uma sessão de daemon nomeada |
| `session list [--all]` / `session delete <name>` | Gere sessões nomeadas |
| `token add <name>` / `token list` / `token remove <name>` | CRUD de bearer-token |

`start` também aceita as opções partilhadas do ciclo do agente; para o daemon, `--model` /
`--provider` recorrem por predefinição à configuração do projecto e são fixos durante o
tempo de vida do daemon.

### `veles channel {list,run,list-sessions,reset-session,add,remove}`
Gateways de chat externos (Telegram, …) que falam com um daemon. Uma plataforma é um módulo
do registo de extensões; `run` e `add` instalam-no quando está em falta. Ver
[ligar o Telegram](../how-to/connect-telegram.md).

| Subcomando | Finalidade |
|---|---|
| `list` | Lista as plataformas de canal instaladas + contagens de sessões, e os canais declarados cujo módulo está em falta |
| `run [--channel P] [--secret S] [--daemon-url U] [--daemon-token T]` | Arranca um gateway em primeiro plano; `--secret` é o segredo principal da plataforma (senão o keychain ou a sua variável de ambiente) |
| `list-sessions [--channel C]` | Mostra os mapeamentos `chat_id → session_id` |
| `reset-session <chat_id> [--channel C]` | Esquece um mapeamento (a próxima mensagem começa do zero) |
| `add [--channel C] [--session S]` | Liga um canal a um daemon (assistente; credenciais → chaveiro) |
| `remove <channel> [--session S]` | Remove uma ligação de canal |

---

## MCP (servidores de ferramentas externos)

### `veles mcp {list,test}`
Inspecciona os servidores MCP externos configurados em `[mcp.servers.*]`. Ver
[servidores MCP externos](../how-to/external-mcp-servers.md).

| Subcomando | Finalidade |
|---|---|
| `list [--connect-timeout f]` | Mostra os servidores configurados, estado da ligação, contagens de ferramentas |
| `test <server>` | Liga-se a um servidor e lista as suas ferramentas |

---

## Opções partilhadas do ciclo do agente

Aceites por `run`, `add`, `tui`, `curate`, `research`, `job tick`, e `daemon start`:

| Opção | Predefinição | Finalidade |
|---|---|---|
| `--model <id>` | resolvido a partir do modelo `[engine]` do projecto → `default_model` do utilizador (sem predefinição rígida) | ID do modelo |
| `--provider <name>` | `openrouter` | Fornecedor (ver abaixo) |
| `--max-tokens <n>` | `[engine] max_tokens`, caso contrário deduzido (32000 para um modelo de raciocínio, 4096 para os restantes) | Limite de saída de cada resposta do modelo |
| `--max-tokens-total <n>` | `100000` | Orçamento cumulativo de tokens; `0` desactiva |
| `--max-iterations <n>` | `1000` | Máximo de iterações de chamada a ferramentas por turno |
| `--stream` | desligado | Transmite a resposta token a token |
| `--verbose` / `-v` | desligado | Progresso por turno para stderr |
| `--project-root <path>` | descobrir a partir do cwd | Operar sobre um projecto noutro local |

## Nomes de fornecedores

`--provider` e `veles models` aceitam qualquer id do catálogo de fornecedores — os
incorporados, o seu `~/.veles/providers.toml` e os fornecedores de módulos instalados:

`openrouter` (predefinição) · `anthropic` · `openai` · `gemini` · `claude-cli` · `codex` ·
`ollama` · `llamacpp` · `openai-compat` (incorporados)

Um fornecedor oferecido apenas por um módulo do registo (`antigravity-cli`) instala-se
sozinho quando o nomeia. Os fornecedores locais (`ollama`, `llamacpp`, `openai-compat`)
não precisam de chave de API. Ver a [referência de fornecedores](providers.md) e [configurar fornecedores](../how-to/configure-providers.md).

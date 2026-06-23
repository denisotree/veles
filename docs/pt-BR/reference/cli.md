# Referência da CLI

> 🌐 **Idiomas:** **English** · [Русский](../../ru/reference/cli.md)

Todos os comandos, subcomandos e flags do Veles. Execute `veles <command> --help` para
obter a assinatura autoritativa e sempre atualizada — esta página espelha os parsers de argumentos
em `src/veles/cli/_parsers/`.

```
veles [--no-wizard] <command> [subcommand] [options]
```

- `--no-wizard` — pula o assistente de configuração da primeira execução mesmo que `~/.veles/config.toml`
  esteja ausente (também condicionado a um TTY e a `VELES_NO_WIZARD=1`).
- Sem argumentos, `veles` abre a [TUI](tui.md) interativa.

A maioria dos comandos do agente aceita as [flags compartilhadas do loop do agente](#shared-agent-loop-flags)
e os [nomes de provedores](#provider-names) listados ao final.

---

## Ciclo de vida do projeto

### `veles init [name]`
Cria um novo projeto Veles no diretório atual (um diretório de estado `.veles/`
+ `AGENTS.md` + o scaffold de conteúdo do pacote de layout escolhido).

| Flag | Padrão | Finalidade |
|---|---|---|
| `name` (posicional) | basename do cwd | Nome do projeto |
| `--layout <name>` | `llm-wiki` | Pacote de layout para o scaffold de conteúdo (`llm-wiki`, `notes`, `bare` ou um pacote personalizado de `~/.veles/layouts/`) |
| `--force` | desligado | Recria `.veles/` mesmo que já exista |

### `veles schema {validate,edit,fix}`
Valida ou edita o `AGENTS.md` (o arquivo de contexto do projeto).

- `validate` — verifica as seções H2 obrigatórias.
- `edit` — abre `AGENTS.md` no `$EDITOR` (padrão `vi`), validando ao sair.
- `fix` — adiciona interativamente as seções ausentes por meio de um assistente de LLM.

### `veles self-doc [refresh|show]`
Gera e exibe a autodocumentação do projeto (`wiki/self-doc/overview.md`).
`veles self-doc` puro mostra a página atual; `refresh` a regenera.

### `veles doctor`
Executa verificações de saúde sobre o estado global do usuário e o projeto ativo. Funciona com ou
sem um projeto ativo.

| Flag | Padrão | Finalidade |
|---|---|---|
| `--json` | desligado | Emite um relatório em JSON |
| `--strict` | desligado | Sai com código diferente de zero diante de qualquer aviso (gating de CI) |

### `veles export {full,template} <path>`
Empacota o projeto em um bundle `.tar.gz`. Veja [Fazer backup e compartilhar](../how-to/backup-and-share.md).

- `full <path>` — projeto inteiro (`.veles/` + `AGENTS.md`), menos os arquivos efêmeros de runtime.
- `template <path>` — subconjunto sanitizado (schema + skills + módulos + páginas de wiki
  que não sejam de sessão); remove `memory.db`, `sources/`, `sessions/`, concessões de `trust` e
  censura PII no texto.

### `veles import <path>`
Restaura um bundle criado por `veles export`.

| Flag | Padrão | Finalidade |
|---|---|---|
| `path` (posicional) | — | Caminho do bundle (`.tar.gz`) |
| `--into <dir>` | cwd | Diretório de destino |
| `--force` | desligado | Sobrescreve um `.veles/` existente no destino |

---

## Executando o agente

### `veles run "<prompt>"`
Executa um único prompt de ponta a ponta com persistência de memória e os gatilhos
do curador/aprendizado. Aceita todas as [flags compartilhadas do loop do agente](#shared-agent-loop-flags) mais:

| Flag | Padrão | Finalidade |
|---|---|---|
| `--resume <session_id>` | nova sessão | Continua uma sessão existente |
| `--manager` | desligado | Decompõe via gerenciador multiagente (também `VELES_MANAGER_MODE=1`) |
| `--plan` | desligado | Modo de planejamento: leitura/busca/rascunho permitidos, mutações bloqueadas |
| `--no-agents-md` | desligado | Não injeta `AGENTS.md` no prompt do sistema |
| `--no-index` | desligado | Não injeta `wiki/INDEX.md` |
| `--no-compress` | desligado | Desabilita a compressão de contexto por janela deslizante |
| `--no-curator` | desligado | Desabilita os gatilhos do curador nesta execução |
| `--no-insights` | desligado | Desabilita a extração de insights após a execução |
| `--no-proposer` | desligado | Desabilita o gatilho automático do propositor de subprojetos |
| `--no-route-refresh` | desligado | Desabilita a atualização de roteamento em NL a partir do `AGENTS.md` |
| `--no-suggest-promote` | desligado | Desabilita o sugeridor de promoção automática |
| `--compressor-model <id>` | roteado | Sobrescreve o modelo de compressão |
| `--compress-threshold-tokens <n>` | `50000` | Tamanho do histórico que dispara a compressão |

### `veles tui`
Abre o REPL interativo. Veja a [referência da TUI](tui.md). Aceita as flags
compartilhadas do loop do agente, `--resume`, as flags `--no-*` de injeção/compressão acima, e:

| Flag | Padrão | Finalidade |
|---|---|---|
| `--theme <name>` | config ou `everforest` | Tema de cores (everforest, dracula, gruvbox, tokyo-night, catppuccin) |

### `veles add <source>`
Lê uma fonte (um arquivo local ou URL `http(s)://`) e a sintetiza em uma página
de wiki. Aceita as flags compartilhadas do loop do agente.

### `veles curate`
Executa uma passagem do curador: compacta sessões não processadas em páginas `wiki/sessions/`.

| Flag | Padrão | Finalidade |
|---|---|---|
| `--limit <n>` | um pequeno padrão | Máximo de sessões a processar nesta execução |

Mais as flags compartilhadas do loop do agente.

### `veles research "<question>"`
Pesquisa profunda: decompõe em subperguntas → explora a web em paralelo →
sintetiza um relatório com citações.

| Flag | Padrão | Finalidade |
|---|---|---|
| `--max-subquestions <n>` | `4` | Ângulos de pesquisa paralelos |

Mais as flags compartilhadas do loop do agente.

### `veles dream`
Executa um ciclo de consolidação de memória em segundo plano (insights → deduplicação de skills → sugestões
de promoção → lint da wiki, opcionalmente consolidação por LLM).

| Flag | Padrão | Finalidade |
|---|---|---|
| `--include-consolidation` | desligado | Executa a consolidação por LLM (cara; requer uma chave de API) |
| `--dry-run` | desligado | Executa todas as etapas, mas pula as gravações em `wiki/state` |
| `--skip-insights` / `--skip-dedup` / `--skip-promote` / `--skip-lint` | desligado | Pula etapas individuais |
| `--consolidation-model <id>` | `anthropic/claude-haiku-4.5` | Sobrescreve o modelo de consolidação |
| `--provider <name>` | `openrouter` | Provedor para o subagente de consolidação |
| `--project-root <path>` | descobrir | Sobrescreve o projeto |

---

## Conhecimento: skills, ferramentas, módulos

### `veles skill {list,show,add,remove,promote,demote,dedup,suggest-promote}`

| Subcomando | Finalidade |
|---|---|
| `list` | Lista as skills do projeto ativo (com telemetria) |
| `show <name>` | Imprime o `SKILL.md` de uma skill |
| `add <source> [--name N] [--scope project\|user] [-y]` | Instala a partir de uma URL git ou caminho local |
| `remove <name> [--scope project\|user] [-y]` | Remove uma skill instalada |
| `promote <name> [--keep-telemetry]` | Copia uma skill de projeto para o escopo de usuário (`~/.veles/skills/`) |
| `demote <name> [-y]` | Copia uma skill de usuário para o projeto ativo |
| `dedup [--mode auto\|embedding\|tfidf] [--embedding-threshold f] [--tfidf-threshold f]` | Encontra skills quase duplicadas |
| `suggest-promote [--save] [--min-uses n] [--min-success-rate f]` | Lista skills que atingem o critério de promoção automática |

### `veles tool {list,show,promote}`

| Subcomando | Finalidade |
|---|---|
| `list` | Lista as ferramentas catalogadas no `memory.db` deste projeto |
| `show <name>` | Imprime o manifesto + a telemetria de uma ferramenta |
| `promote <name> [-y]` | Move uma ferramenta de projeto para `~/.veles/tools/` (entre projetos) |

### `veles module {list,show,add,remove}`

| Subcomando | Finalidade |
|---|---|
| `list` | Lista os módulos instalados |
| `show <name>` | Imprime o manifesto de um módulo |
| `add <source> [--name N] [-y]` | Instala um módulo a partir de uma URL git ou caminho local |
| `remove <name> [-y]` | Remove um módulo instalado |

### `veles browse {modules,skills} [query]`
Navega pelos registries curados.

| Flag | Padrão | Finalidade |
|---|---|---|
| `query` (posicional) | `""` | Filtro por substring |
| `--source <url>` | canônico | Sobrescreve a fonte do registry |
| `--json` | desligado | Emite JSON |

---

## Sessões e memória

### `veles sessions {list,show,delete,search}`

| Subcomando | Finalidade |
|---|---|
| `list [--limit n]` | Lista as sessões recentes (padrão 20) |
| `show <session_id>` | Imprime o histórico completo de turnos de uma sessão |
| `delete <session_id>` | Remove uma sessão e seus turnos |
| `search "<query>" [--limit n] [--role user\|assistant\|both\|all] [--since 7d]` | Busca de texto completo (FTS5) no conteúdo dos turnos |

---

## Multiprojeto

### `veles project {list,add,remove,switch}`

| Subcomando | Finalidade |
|---|---|
| `list` | Lista os projetos registrados, do mais recente ao mais antigo |
| `add <path> [--slug S]` | Registra um diretório de projeto existente |
| `remove <slug>` | Cancela o registro de um projeto (os arquivos não são tocados) |
| `switch <slug>` | Imprime o caminho absoluto do projeto (use `cd $(veles project switch <slug>)`) |

### `veles subproject {init,list,switch,remove,suggest}`

| Subcomando | Finalidade |
|---|---|
| `init <subdir> [--name N] [--description D]` | Cria + registra um subprojeto |
| `list` | Lista os subprojetos do projeto ativo |
| `switch <slug>` | Imprime o caminho absoluto de um subprojeto |
| `remove <slug>` | Cancela o registro de um subprojeto |
| `suggest [--save] [--min-pages n] [--min-similarity f]` | Detecta clusters temáticos e propõe subprojetos |

---

## Roteamento e modelos

### `veles route {show,set,reset,refresh}`
Roteamento de ensemble por tarefa — qual `provider:model` cuida de cada tipo de tarefa
(`default`, `curator`, `compressor`, `insights`, `skills`, `advisor`, `vision`,
`embedding`). Veja [roteamento por tarefa](../how-to/per-task-routing.md).

| Subcomando | Finalidade |
|---|---|
| `show` | Imprime a tabela de roteamento resolvida para o projeto ativo |
| `set <task> <provider:model>` | Fixa uma tarefa a uma especificação |
| `reset [task]` | Restaura uma tarefa (ou todas) aos padrões |
| `refresh [--force]` | Re-analisa as dicas de roteamento em linguagem natural do `AGENTS.md` |

### `veles models <provider>`
Lista os modelos de um provedor. Provedores de nuvem (openrouter/openai/gemini) ficam em cache
por 24h; provedores locais são sempre ao vivo.

| Flag | Padrão | Finalidade |
|---|---|---|
| `provider` (posicional) | — | Um dos [nomes de provedores](#provider-names) |
| `--refresh` | desligado | Ignora o cache em disco (somente nuvem) |
| `--json` | desligado | Emite `{provider, source, models}` como JSON |

---

## Tarefas de longa duração

### `veles goal {list,show,start,checkpoint,pause,resume,done,cancel}`
Objetivos de longo horizonte com orçamentos e checkpoints.

| Subcomando | Finalidade |
|---|---|
| `list [--status active\|paused\|completed\|blocked\|cancelled]` | Lista os objetivos |
| `show <id> [--json]` | Mostra um objetivo |
| `start "<objective>" [--scope S] [--done-when D] [--max-steps n] [--max-cost-usd f] [--max-wall-time-s n] [--forbid A]… [--approve A]…` | Cria um objetivo |
| `checkpoint <id> "<note>" [--evidence U] [--cost-usd f] [--no-advance]` | Adiciona progresso |
| `pause <id>` / `resume <id>` | Pausa / retoma |
| `done <id> [--evidence E]` / `cancel <id> [--reason R]` | Conclui / cancela |

### `veles job {add,list,show,pause,resume,trigger,remove,history,tick}`
Tarefas de agente agendadas.

| Subcomando | Finalidade |
|---|---|
| `add --name N --schedule S --prompt P [--repeat n] [--context-from JOB_ID] [--deliver-to TARGET]` | Cria uma tarefa (schedule = cron, `<N><s\|m\|h\|d>` ou timestamp ISO) |
| `list [--json]` / `show <id>` | Inspeciona as tarefas |
| `pause <id>` / `resume <id>` / `trigger <id>` / `remove <id>` | Ciclo de vida |
| `history <id> [--limit n]` | Execuções recentes |
| `tick` | Executa sincronamente todas as tarefas vencidas uma vez (sem precisar de daemon; aceita as flags do loop do agente) |

---

## Segurança e controle de acesso

### `veles trust {list,set,revoke,clear}`
Concessões persistidas para ferramentas sensíveis (`run_shell`, `write_file`, `fetch_url`, …).
Veja [segurança](../how-to/security-and-permissions.md).

| Subcomando | Finalidade |
|---|---|
| `list` | Mostra as concessões (escopo de usuário + projeto) |
| `set <tool> [--scope project\|user]` | Concede uma ferramenta |
| `revoke <tool> [--scope project\|user\|both]` | Remove uma concessão |
| `clear [--scope project\|user\|all]` | Apaga as concessões de um escopo |

### `veles autopilot {enable,disable,status}`
Uma janela com tempo limitado em que os prompts da escada de confiança liberam automaticamente.

| Subcomando | Finalidade |
|---|---|
| `enable --until <DUR>` | Abre uma janela (`+30m`, `+2h`, `+1d` ou ISO `2026-05-12T18:00:00Z`) |
| `disable` | Fecha a janela agora |
| `status` | Informa se o autopilot está ativo |

### `veles secret {set,get,list,delete}`
Segredos respaldados pelo keychain do SO (chaves de API, tokens de bot).

| Subcomando | Finalidade |
|---|---|
| `set <name> [value]` | Armazena (omita o valor para entrada interativa / stdin) |
| `get <name> [--reveal] [--no-env-fallback]` | Consulta (fallback para env por padrão) |
| `list` | Mostra quais segredos canônicos estão configurados |
| `delete <name>` | Remove um segredo |

---

## Daemon e canais

### `veles daemon [start|stop|status|list|restart|delete|session|token]`
Executa/controla o daemon HTTP+WS. `veles daemon` puro abre a **TUI seletora de daemon**
(projeto → daemons → canais). Veja [executar como daemon](../how-to/run-as-daemon.md).

| Subcomando | Finalidade |
|---|---|
| `start [--host H] [--port P] [--foreground] [--name N]` | Inicia um daemon (desanexa por padrão) |
| `stop [--name N]` / `status [--name N]` | Para / inspeciona |
| `list` | Lista os daemons em todos os projetos |
| `restart [target] [--name N]` | Para + reinicia no mesmo host/porta |
| `delete <target> [-y]` | Para + remove do registry |
| `session create <name> [--host H] --port P [--model M] [--provider P] [--mode M]` | Declara uma sessão de daemon nomeada |
| `session list [--all]` / `session delete <name>` | Gerencia sessões nomeadas |
| `token add <name>` / `token list` / `token remove <name>` | CRUD de bearer token |

`start` também aceita as flags compartilhadas do loop do agente; no daemon, `--model` /
`--provider` assumem como padrão a configuração do projeto e ficam fixos durante toda a vida do daemon.

### `veles channel {list,run,list-sessions,reset-session,add,remove}`
Gateways de chat externos (Telegram, …) que conversam com um daemon. Veja
[conectar o Telegram](../how-to/connect-telegram.md).

| Subcomando | Finalidade |
|---|---|
| `list` | Lista as plataformas de canal registradas + contagem de sessões |
| `run --channel telegram [--bot-token T] [--daemon-url U] [--daemon-token T]` | Inicia um gateway em primeiro plano |
| `list-sessions [--channel C]` | Mostra os mapeamentos `chat_id → session_id` |
| `reset-session <chat_id> [--channel C]` | Esquece um mapeamento (a próxima mensagem começa do zero) |
| `add [--channel C] [--session S]` | Vincula um canal a um daemon (assistente; credenciais → keychain) |
| `remove <channel> [--session S]` | Remove um vínculo de canal |

---

## MCP (servidores de ferramentas externos)

### `veles mcp {list,test}`
Inspeciona servidores MCP externos configurados em `[mcp.servers.*]`. Veja
[servidores MCP externos](../how-to/external-mcp-servers.md).

| Subcomando | Finalidade |
|---|---|
| `list [--connect-timeout f]` | Mostra os servidores configurados, o status de conexão e a contagem de ferramentas |
| `test <server>` | Conecta a um servidor e lista suas ferramentas |

---

## Flags compartilhadas do loop do agente

Aceitas por `run`, `add`, `tui`, `curate`, `research`, `job tick` e `daemon
start`:

| Flag | Padrão | Finalidade |
|---|---|---|
| `--model <id>` | `anthropic/claude-sonnet-4.6` (tui: persistido) | ID do modelo |
| `--provider <name>` | `openrouter` | Provedor (veja abaixo) |
| `--max-tokens-total <n>` | `100000` | Orçamento cumulativo de tokens; `0` desabilita |
| `--max-iterations <n>` | `30` | Máximo de iterações de chamada de ferramenta por turno |
| `--stream` | desligado | Transmite a resposta token a token |
| `--verbose` / `-v` | desligado | Progresso por turno no stderr |
| `--project-root <path>` | descobrir a partir do cwd | Opera sobre um projeto em outro lugar |

## Nomes de provedores

`openrouter` (padrão) · `anthropic` · `openai` · `gemini` · `claude-cli` ·
`gemini-cli` · `ollama` · `llamacpp` · `openai-compat`

Provedores locais (`ollama`, `llamacpp`, `openai-compat`) não precisam de chave de API. Veja a
[referência de provedores](providers.md) e [configurar provedores](../how-to/configure-providers.md).

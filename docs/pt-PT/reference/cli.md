# Referência da CLI

> 🌐 **Languages:** **English** · [Русский](../../ru/reference/cli.md)

Todos os comandos, subcomandos e opções do Veles. Execute `veles <command> --help`
para a assinatura autoritativa e sempre atualizada — esta página espelha os
analisadores de argumentos em `src/veles/cli/_parsers/`.

```
veles [--no-wizard] <command> [subcommand] [options]
```

- `--no-wizard` — ignora o assistente de configuração da primeira execução mesmo
  que `~/.veles/config.toml` esteja em falta (também condicionado a um TTY e a
  `VELES_NO_WIZARD=1`).
- Sem argumentos, `veles` inicia a [TUI](tui.md) interativa.

A maioria dos comandos do agente aceita as [opções partilhadas do ciclo do
agente](#shared-agent-loop-flags) e os [nomes de fornecedores](#provider-names)
listados no fundo.

---

## Ciclo de vida do projeto

### `veles init [name]`
Cria um novo projeto Veles no diretório atual (um diretório de estado `.veles/`
+ `AGENTS.md` + o scaffold de conteúdo do pacote de layout escolhido).

| Opção | Predefinição | Finalidade |
|---|---|---|
| `name` (posicional) | nome base da cwd | Nome do projeto |
| `--layout <name>` | `llm-wiki` | Pacote de layout para o scaffold de conteúdo (`llm-wiki`, `notes`, `bare` ou um pacote personalizado de `~/.veles/layouts/`) |
| `--force` | desligado | Recriar `.veles/` mesmo que já exista |

### `veles schema {validate,edit,fix}`
Valida ou edita o `AGENTS.md` (o ficheiro de contexto do projeto).

- `validate` — verifica as secções H2 obrigatórias.
- `edit` — abre o `AGENTS.md` em `$EDITOR` (predefinição `vi`), valida ao sair.
- `fix` — adiciona interativamente as secções em falta através de um assistente LLM.

### `veles self-doc [refresh|show]`
Gera e apresenta a autodocumentação do projeto (`wiki/self-doc/overview.md`).
`veles self-doc` sozinho mostra a página atual; `refresh` regenera-a.

### `veles doctor`
Executa verificações de saúde sobre o estado global do utilizador e o projeto
ativo. Funciona com ou sem um projeto ativo.

| Opção | Predefinição | Finalidade |
|---|---|---|
| `--json` | desligado | Emite um relatório JSON |
| `--strict` | desligado | Sai com código diferente de zero em qualquer aviso (controlo de CI) |

### `veles export {full,template} <path>`
Empacota o projeto num pacote `.tar.gz`. Consulte [Cópia de segurança e partilha](../how-to/backup-and-share.md).

- `full <path>` — projeto inteiro (`.veles/` + `AGENTS.md`), sem os efémeros de execução.
- `template <path>` — subconjunto higienizado (schema + skills + módulos + páginas
  de wiki que não sejam de sessão); remove `memory.db`, `sources/`, `sessions/`,
  autorizações de `trust`, e remove dados pessoais (PII) do texto.

### `veles import <path>`
Restaura um pacote criado por `veles export`.

| Opção | Predefinição | Finalidade |
|---|---|---|
| `path` (posicional) | — | Caminho do pacote (`.tar.gz`) |
| `--into <dir>` | cwd | Diretório de destino |
| `--force` | desligado | Substitui um `.veles/` existente no destino |

---

## Executar o agente

### `veles run "<prompt>"`
Executa um único prompt de ponta a ponta com persistência de memória e os
acionadores do curador/aprendizagem. Aceita todas as [opções partilhadas do
ciclo do agente](#shared-agent-loop-flags) mais:

| Opção | Predefinição | Finalidade |
|---|---|---|
| `--resume <session_id>` | nova sessão | Continuar uma sessão existente |
| `--manager` | desligado | Decompor através do gestor multi-agente (também `VELES_MANAGER_MODE=1`) |
| `--plan` | desligado | Modo de planeamento: leitura/pesquisa/rascunho permitidos, mutações bloqueadas |
| `--no-agents-md` | desligado | Não injetar o `AGENTS.md` no system prompt |
| `--no-index` | desligado | Não injetar o `wiki/INDEX.md` |
| `--no-compress` | desligado | Desativar a compressão de contexto por janela deslizante |
| `--no-curator` | desligado | Desativar os acionadores do curador nesta execução |
| `--no-insights` | desligado | Desativar a extração de insights após a execução |
| `--no-proposer` | desligado | Desativar o acionador automático do propositor de subprojetos |
| `--no-route-refresh` | desligado | Desativar a atualização do encaminhamento em linguagem natural a partir do `AGENTS.md` |
| `--no-suggest-promote` | desligado | Desativar o sugeridor de promoção automática |
| `--compressor-model <id>` | encaminhado | Substituir o modelo de compressão |
| `--compress-threshold-tokens <n>` | `50000` | Tamanho do histórico que aciona a compressão |

### `veles tui`
Abre a REPL interativa. Consulte a [referência da TUI](tui.md). Aceita as opções
partilhadas do ciclo do agente, `--resume`, as opções `--no-*` de injeção/compressão
acima, e:

| Opção | Predefinição | Finalidade |
|---|---|---|
| `--theme <name>` | config ou `everforest` | Tema de cores (everforest, dracula, gruvbox, tokyo-night, catppuccin) |

### `veles add <source>`
Lê uma fonte (um ficheiro local ou URL `http(s)://`) e sintetiza-a numa página
de wiki. Aceita as opções partilhadas do ciclo do agente.

### `veles curate`
Executa uma passagem do curador: compacta as sessões não processadas em páginas
de `wiki/sessions/`.

| Opção | Predefinição | Finalidade |
|---|---|---|
| `--limit <n>` | um valor pequeno por omissão | Máximo de sessões a processar nesta execução |

Mais as opções partilhadas do ciclo do agente.

### `veles research "<question>"`
Investigação profunda: decompõe em subquestões → explora a web em paralelo →
sintetiza um relatório com citações.

| Opção | Predefinição | Finalidade |
|---|---|---|
| `--max-subquestions <n>` | `4` | Ângulos de investigação em paralelo |

Mais as opções partilhadas do ciclo do agente.

### `veles dream`
Executa um ciclo de consolidação de memória em segundo plano (insights →
deduplicação de skills → sugestões de promoção → lint da wiki, opcionalmente
consolidação por LLM).

| Opção | Predefinição | Finalidade |
|---|---|---|
| `--include-consolidation` | desligado | Executa a consolidação dispendiosa por LLM (requer uma chave de API) |
| `--dry-run` | desligado | Executa todos os passos mas ignora as escritas em `wiki/state` |
| `--skip-insights` / `--skip-dedup` / `--skip-promote` / `--skip-lint` | desligado | Ignorar passos individuais |
| `--consolidation-model <id>` | `anthropic/claude-haiku-4.5` | Substituir o modelo de consolidação |
| `--provider <name>` | `openrouter` | Fornecedor para o subagente de consolidação |
| `--project-root <path>` | descobrir | Substituição do projeto |

---

## Conhecimento: skills, ferramentas, módulos

### `veles skill {list,show,add,remove,promote,demote,dedup,suggest-promote}`

| Subcomando | Finalidade |
|---|---|
| `list` | Lista as skills no projeto ativo (com telemetria) |
| `show <name>` | Imprime o `SKILL.md` de uma skill |
| `add <source> [--name N] [--scope project\|user] [-y]` | Instala a partir de um URL git ou caminho local |
| `remove <name> [--scope project\|user] [-y]` | Elimina uma skill instalada |
| `promote <name> [--keep-telemetry]` | Copia uma skill de projeto para o âmbito de utilizador (`~/.veles/skills/`) |
| `demote <name> [-y]` | Copia uma skill de utilizador para o projeto ativo |
| `dedup [--mode auto\|embedding\|tfidf] [--embedding-threshold f] [--tfidf-threshold f]` | Encontra skills quase duplicadas |
| `suggest-promote [--save] [--min-uses n] [--min-success-rate f]` | Lista as skills que cumprem o limiar de promoção automática |

### `veles tool {list,show,promote}`

| Subcomando | Finalidade |
|---|---|
| `list` | Lista as ferramentas catalogadas na `memory.db` deste projeto |
| `show <name>` | Imprime o manifesto + telemetria de uma ferramenta |
| `promote <name> [-y]` | Move uma ferramenta de projeto para `~/.veles/tools/` (entre projetos) |

### `veles module {list,show,add,remove}`

| Subcomando | Finalidade |
|---|---|
| `list` | Lista os módulos instalados |
| `show <name>` | Imprime o manifesto de um módulo |
| `add <source> [--name N] [-y]` | Instala um módulo a partir de um URL git ou caminho local |
| `remove <name> [-y]` | Elimina um módulo instalado |

### `veles browse {modules,skills} [query]`
Explora os registos curados.

| Opção | Predefinição | Finalidade |
|---|---|---|
| `query` (posicional) | `""` | Filtro por subcadeia |
| `--source <url>` | canónico | Substituir a fonte do registo |
| `--json` | desligado | Emite JSON |

---

## Sessões e memória

### `veles sessions {list,show,delete,search}`

| Subcomando | Finalidade |
|---|---|
| `list [--limit n]` | Lista as sessões recentes (predefinição 20) |
| `show <session_id>` | Imprime o histórico completo de turnos de uma sessão |
| `delete <session_id>` | Elimina uma sessão e os seus turnos |
| `search "<query>" [--limit n] [--role user\|assistant\|both\|all] [--since 7d]` | Pesquisa de texto completo (FTS5) sobre o conteúdo dos turnos |

---

## Multiprojeto

### `veles project {list,add,remove,switch}`

| Subcomando | Finalidade |
|---|---|
| `list` | Lista os projetos registados, do mais recente para o mais antigo |
| `add <path> [--slug S]` | Regista um diretório de projeto existente |
| `remove <slug>` | Cancela o registo de um projeto (os ficheiros ficam intactos) |
| `switch <slug>` | Imprime o caminho absoluto do projeto (use `cd $(veles project switch <slug>)`) |

### `veles subproject {init,list,switch,remove,suggest}`

| Subcomando | Finalidade |
|---|---|
| `init <subdir> [--name N] [--description D]` | Cria + regista um subprojeto |
| `list` | Lista os subprojetos do projeto ativo |
| `switch <slug>` | Imprime o caminho absoluto de um subprojeto |
| `remove <slug>` | Cancela o registo de um subprojeto |
| `suggest [--save] [--min-pages n] [--min-similarity f]` | Deteta agrupamentos temáticos e propõe subprojetos |

---

## Encaminhamento e modelos

### `veles route {show,set,reset,refresh}`
Encaminhamento por ensemble por tarefa — qual o `provider:model` que trata cada
tipo de tarefa (`default`, `curator`, `compressor`, `insights`, `skills`,
`advisor`, `vision`, `embedding`). Consulte [encaminhamento por tarefa](../how-to/per-task-routing.md).

| Subcomando | Finalidade |
|---|---|
| `show` | Imprime a tabela de encaminhamento resolvida para o projeto ativo |
| `set <task> <provider:model>` | Fixa uma tarefa a uma especificação |
| `reset [task]` | Repõe uma tarefa (ou todas) para as predefinições |
| `refresh [--force]` | Reinterpreta as sugestões de encaminhamento em linguagem natural do `AGENTS.md` |

### `veles models <provider>`
Lista os modelos de um fornecedor. Os fornecedores na nuvem (openrouter/openai/gemini)
ficam em cache 24h; os fornecedores locais estão sempre em direto.

| Opção | Predefinição | Finalidade |
|---|---|---|
| `provider` (posicional) | — | Um dos [nomes de fornecedores](#provider-names) |
| `--refresh` | desligado | Ignora a cache em disco (apenas na nuvem) |
| `--json` | desligado | Emite `{provider, source, models}` como JSON |

---

## Tarefas de longa duração

### `veles goal {list,show,start,checkpoint,pause,resume,done,cancel}`
Objetivos de longo prazo com orçamentos e checkpoints.

| Subcomando | Finalidade |
|---|---|
| `list [--status active\|paused\|completed\|blocked\|cancelled]` | Lista os objetivos |
| `show <id> [--json]` | Mostra um objetivo |
| `start "<objective>" [--scope S] [--done-when D] [--max-steps n] [--max-cost-usd f] [--max-wall-time-s n] [--forbid A]… [--approve A]…` | Cria um objetivo |
| `checkpoint <id> "<note>" [--evidence U] [--cost-usd f] [--no-advance]` | Acrescenta progresso |
| `pause <id>` / `resume <id>` | Pausar / retomar |
| `done <id> [--evidence E]` / `cancel <id> [--reason R]` | Concluir / cancelar |

### `veles job {add,list,show,pause,resume,trigger,remove,history,tick}`
Trabalhos agendados do agente.

| Subcomando | Finalidade |
|---|---|
| `add --name N --schedule S --prompt P [--repeat n] [--context-from JOB_ID] [--deliver-to TARGET]` | Cria um trabalho (schedule = cron, `<N><s\|m\|h\|d>`, ou timestamp ISO) |
| `list [--json]` / `show <id>` | Inspecionar trabalhos |
| `pause <id>` / `resume <id>` / `trigger <id>` / `remove <id>` | Ciclo de vida |
| `history <id> [--limit n]` | Execuções recentes |
| `tick` | Executa de forma síncrona todos os trabalhos vencidos uma vez (sem daemon; aceita as opções do ciclo do agente) |

---

## Segurança e controlo de acesso

### `veles trust {list,set,revoke,clear}`
Autorizações persistidas para ferramentas sensíveis (`run_shell`, `write_file`,
`fetch_url`, …). Consulte [segurança](../how-to/security-and-permissions.md).

| Subcomando | Finalidade |
|---|---|
| `list` | Mostra as autorizações (âmbito de utilizador + projeto) |
| `set <tool> [--scope project\|user]` | Autoriza uma ferramenta |
| `revoke <tool> [--scope project\|user\|both]` | Remove uma autorização |
| `clear [--scope project\|user\|all]` | Apaga as autorizações de um âmbito |

### `veles autopilot {enable,disable,status}`
Uma janela com limite temporal em que os pedidos da escada de confiança são
permitidos automaticamente.

| Subcomando | Finalidade |
|---|---|
| `enable --until <DUR>` | Abre uma janela (`+30m`, `+2h`, `+1d`, ou ISO `2026-05-12T18:00:00Z`) |
| `disable` | Fecha a janela agora |
| `status` | Indica se o autopilot está ativo |

### `veles secret {set,get,list,delete}`
Segredos suportados pelo porta-chaves do SO (chaves de API, tokens de bots).

| Subcomando | Finalidade |
|---|---|
| `set <name> [value]` | Armazena (omita o valor para modo interativo / stdin) |
| `get <name> [--reveal] [--no-env-fallback]` | Pesquisa (recurso a env por omissão) |
| `list` | Mostra que segredos canónicos estão configurados |
| `delete <name>` | Remove um segredo |

---

## Daemon e canais

### `veles daemon [start|stop|status|list|restart|delete|session|token]`
Executa/controla o daemon HTTP+WS. `veles daemon` sozinho abre a TUI do
**seletor de daemons** (projeto → daemons → canais). Consulte [executar como daemon](../how-to/run-as-daemon.md).

| Subcomando | Finalidade |
|---|---|
| `start [--host H] [--port P] [--foreground] [--name N]` | Inicia um daemon (desanexa por omissão) |
| `stop [--name N]` / `status [--name N]` | Parar / inspecionar |
| `list` | Lista os daemons de todos os projetos |
| `restart [target] [--name N]` | Para + reinicia no mesmo host/porta |
| `delete <target> [-y]` | Para + remove do registo |
| `session create <name> [--host H] --port P [--model M] [--provider P] [--mode M]` | Declara uma sessão de daemon nomeada |
| `session list [--all]` / `session delete <name>` | Gerir sessões nomeadas |
| `token add <name>` / `token list` / `token remove <name>` | CRUD de tokens de portador |

O `start` também aceita as opções partilhadas do ciclo do agente; para o daemon,
`--model` / `--provider` assumem por omissão a configuração do projeto e são fixos
durante todo o tempo de vida do daemon.

### `veles channel {list,run,list-sessions,reset-session,add,remove}`
Gateways de chat externos (Telegram, …) que comunicam com um daemon. Consulte
[ligar o Telegram](../how-to/connect-telegram.md).

| Subcomando | Finalidade |
|---|---|
| `list` | Lista as plataformas de canais registadas + contagem de sessões |
| `run --channel telegram [--bot-token T] [--daemon-url U] [--daemon-token T]` | Inicia um gateway em primeiro plano |
| `list-sessions [--channel C]` | Mostra os mapeamentos `chat_id → session_id` |
| `reset-session <chat_id> [--channel C]` | Esquece um mapeamento (a próxima mensagem começa do zero) |
| `add [--channel C] [--session S]` | Liga um canal a um daemon (assistente; credenciais → porta-chaves) |
| `remove <channel> [--session S]` | Remove a ligação de um canal |

---

## MCP (servidores de ferramentas externos)

### `veles mcp {list,test}`
Inspeciona os servidores MCP externos configurados em `[mcp.servers.*]`. Consulte
[servidores MCP externos](../how-to/external-mcp-servers.md).

| Subcomando | Finalidade |
|---|---|
| `list [--connect-timeout f]` | Mostra os servidores configurados, o estado da ligação, a contagem de ferramentas |
| `test <server>` | Liga-se a um servidor e lista as suas ferramentas |

---

## Opções partilhadas do ciclo do agente

Aceites por `run`, `add`, `tui`, `curate`, `research`, `job tick` e `daemon
start`:

| Opção | Predefinição | Finalidade |
|---|---|---|
| `--model <id>` | `anthropic/claude-sonnet-4.6` (tui: persistido) | ID do modelo |
| `--provider <name>` | `openrouter` | Fornecedor (ver abaixo) |
| `--max-tokens-total <n>` | `100000` | Orçamento cumulativo de tokens; `0` desativa |
| `--max-iterations <n>` | `30` | Máximo de iterações de chamada de ferramentas por turno |
| `--stream` | desligado | Transmite a resposta token a token |
| `--verbose` / `-v` | desligado | Progresso por turno para stderr |
| `--project-root <path>` | descobre a partir da cwd | Operar sobre um projeto noutro local |

## Nomes de fornecedores

`openrouter` (predefinição) · `anthropic` · `openai` · `gemini` · `claude-cli` ·
`gemini-cli` · `ollama` · `llamacpp` · `openai-compat`

Os fornecedores locais (`ollama`, `llamacpp`, `openai-compat`) não precisam de
chave de API. Consulte a [referência de fornecedores](providers.md) e
[configurar fornecedores](../how-to/configure-providers.md).

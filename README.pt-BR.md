# Veles

[![CI](https://github.com/denisotree/veles/actions/workflows/ci.yml/badge.svg)](https://github.com/denisotree/veles/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/veles-ai.svg)](https://pypi.org/project/veles-ai/)
[![License: Apache-2.0](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)
[![Python 3.13+](https://img.shields.io/badge/python-3.13%2B-blue.svg)](pyproject.toml)

<p align="center">
  <a href="README.md">English</a> ·
  <a href="README.zh-CN.md">简体中文</a> ·
  <a href="README.zh-TW.md">繁體中文</a> ·
  <a href="README.ja.md">日本語</a> ·
  <a href="README.ko.md">한국어</a> ·
  <a href="README.es.md">Español</a> ·
  <a href="README.fr.md">Français</a> ·
  <a href="README.it.md">Italiano</a> ·
  <b>Português (BR)</b> ·
  <a href="README.pt-PT.md">Português (PT)</a> ·
  <a href="README.ru.md">Русский</a> ·
  <a href="README.ar.md">العربية</a> ·
  <a href="README.hi.md">हिन्दी</a> ·
  <a href="README.bn.md">বাংলা</a> ·
  <a href="README.vi.md">Tiếng Việt</a>
</p>

**Um framework de agente de CLI minimalista que fica mais inteligente a cada sessão.**

<p align="center">
  <img src="docs/assets/tui-hero.gif" alt="TUI do Veles — faça uma pergunta e obtenha uma resposta fundamentada na memória do próprio projeto" width="800">
</p>

Diferentemente das ferramentas de chat que começam do zero toda vez, o Veles mantém uma **memória estruturada do projeto** — insights, regras e conhecimento curado que se acumulam ao longo das sessões e tornam o agente mais útil quanto mais você o usa. A forma como o seu *conteúdo* é organizado é plugável: um wiki LLM no estilo Karpathy por padrão, notas planas ou nenhuma estrutura, no caso de repositórios de código. Construído de forma limpa: sem arquivos monstruosos, sem dependência de fornecedor, sem sincronização com a nuvem.

```bash
uv tool install veles-ai          # installs the `veles` command
veles init && veles run "Summarize the project architecture."
veles        # interactive REPL (bare `veles` == `veles tui`)
```

---

## Por que o Veles?

**Memória que se acumula** — Toda sessão é destilada pelo Curador em memória por projeto (insights, regras de comportamento, resumos de sessões em `.veles/`). O agente recorda automaticamente fatos relevantes e decisões passadas — você para de reexplicar o mesmo contexto. A memória funciona sob *qualquer* layout de conteúdo.

**Layouts de conteúdo plugáveis** — `veles init` monta por padrão um wiki LLM no estilo Karpathy; `--layout notes` cria um diretório plano de notas; `--layout bare` não adiciona estrutura nenhuma (ideal para repositórios de código). Pacotes de layout personalizados são um único arquivo TOML em `~/.veles/layouts/`.

**Roteamento agnóstico de provedor** — OpenRouter, Anthropic, OpenAI, Gemini, Ollama, llamacpp ou a sua assinatura da CLI `claude`/`gemini`. Diferentes tipos de tarefa (planejamento, compressão, insights) podem ser roteados para modelos diferentes.

**Skills que se acumulam** — Blocos de prompt reutilizáveis viram ferramentas do agente. Promova uma skill de um projeto para o nível global do usuário e ela fica disponível em todos os lugares. A deduplicação embutida encontra skills quase duplicadas antes que elas divirjam.

**Local em primeiro lugar + isolado em sandbox** — Sem telemetria, sem sincronização com a nuvem. O agente enxerga apenas o diretório do projeto ativo. A escada de confiança pede aprovação a cada chamada de ferramenta sensível; pré-conceda para CI.

**Modular, não monolítico** — Núcleo minimalista (memória, loop do agente, protocolo de provedor, registro de ferramentas). Todo o resto — TUI, daemon, gateway do Telegram, pesquisa profunda, agendador de tarefas — é um módulo opcional e carregável.

---

## Início rápido

**Requisitos:** Python 3.13+, macOS / Linux (Windows com suporte na medida do possível). Instale o [uv](https://docs.astral.sh/uv/) primeiro.

```bash
# 1. Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# 2. Install veles (the package is published as `veles-ai`; the command is `veles`)
uv tool install veles-ai
# …or from source:
#   git clone https://github.com/denisotree/veles.git && cd veles && uv tool install .

# 3. Set an API key — OpenRouter is recommended (access to all models, one key)
export OPENROUTER_API_KEY=sk-or-v1-...

# 4. Create a project
mkdir my-project && cd my-project
veles init

# 5. Talk to the agent
veles run "Read AGENTS.md and describe this project."
```

Ou abra a TUI interativa (o `veles` sozinho faz o mesmo):

```bash
veles
```

Na primeira execução, um assistente de configuração perguntará o seu idioma, provedor e nome de projeto preferidos.

---

## Provedores

| Provedor | Variável de ambiente | Observações |
|---|---|---|
| **OpenRouter** *(recomendado)* | `OPENROUTER_API_KEY` | Claude, GPT, Gemini, Llama — uma chave, centenas de modelos |
| Anthropic | `ANTHROPIC_API_KEY` | API direta |
| OpenAI | `OPENAI_API_KEY` | API direta |
| Gemini | `GEMINI_API_KEY` ou `GOOGLE_API_KEY` | API direta |
| CLI `claude` | — | Usa a sua assinatura do Claude; não precisa de chave de API |
| CLI `gemini` | — | Usa a sua assinatura do Gemini; não precisa de chave de API |
| Ollama | — | Modelos locais, `http://localhost:11434/v1` |
| llamacpp | — | Modelos locais, `http://localhost:8080/v1` |
| openai-compat | `OPENAI_COMPAT_BASE_URL` | Qualquer endpoint compatível com a OpenAI |

Sobrescreva por execução:

```bash
veles run --provider anthropic --model anthropic/claude-opus-4-8 "..."
veles run --provider ollama --model llama3.2 "..."
```

Armazene chaves de API no keychain do sistema operacional em vez de variáveis de ambiente:

```bash
veles secret set OPENROUTER_API_KEY    # prompts for value, stores in keychain
```

---

## Fluxo de trabalho principal

### Escolha um layout de conteúdo

```bash
veles init                  # default: Karpathy-style LLM wiki (sources/ + wiki/)
veles init --layout notes   # a single flat notes/ directory
veles init --layout bare    # no content scaffold — code repos, free-form work
```

A própria memória do agente (insights, regras, resumos de sessões em `.veles/`) funciona de forma idêntica sob qualquer layout. Pacotes personalizados são um único `layout.toml` em `~/.veles/layouts/<name>/`.

### Construa uma base de conhecimento (layout llm-wiki)

```bash
veles add paper.pdf                   # read a source → write a wiki page
veles add https://example.com/post    # web pages, PDFs, plain text

veles run "What do we know about the authentication design?"
veles curate                          # explicit session → memory consolidation
```

<p align="center">
  <img src="docs/assets/kb-ingest.gif" alt="Base de conhecimento do Veles — ingira uma fonte em uma página do wiki, depois faça uma pergunta e obtenha uma resposta que a cita" width="800">
</p>

O Curador roda automaticamente após as sessões. A extração de insights captura frases como "sempre prefira X" ou "nunca faça Y" e as registra como insights persistentes do projeto.

### Pesquisa profunda

```bash
veles research "What are the trade-offs between SQLite and PostgreSQL for this use case?"
```

Decompõe a pergunta em subperguntas paralelas, explora cada uma e sintetiza um relatório estruturado.

### Objetivos de longa duração

```bash
veles goal start "Migrate auth module to the new provider" --max-cost-usd 2.00
veles goal list
veles goal checkpoint <id> "Completed step 1: identified all call sites"
```

### Tarefas agendadas

```bash
veles job add --name "weekly-review" --schedule "0 9 * * 1" --prompt "Generate a weekly progress summary"
veles job list
```

---

## Roteamento de modelos (Ensembles)

Roteie diferentes tipos de tarefa para modelos diferentes — configure uma vez e esqueça.

**Via CLI:**
```bash
veles route show                                          # current routing table
veles route set compressor anthropic/claude-haiku-4-5    # typed override
veles route reset compressor                             # back to default
```

**Via linguagem natural no `AGENTS.md`:**
```markdown
## Routing
Use Opus for planning and architecture decisions.
Haiku is fine for compression and insight extraction.
```

```bash
veles route refresh    # parse the NL hints; typed overrides always win
```

---

## Skills e módulos

**Skills** são blocos de prompt reutilizáveis (`SKILL.md`) que viram ferramentas do agente automaticamente.

```bash
veles skill add https://github.com/org/skill-repo    # install from git
veles skill add ./local-skill-dir                    # or from local path
veles skill list                                     # list with telemetry
veles skill promote my-skill                         # copy to ~/.veles/skills (global)
veles skill dedup                                    # find near-duplicates
veles skill suggest-promote --save                   # propose promotions based on usage
```

**Módulos** são plugins Python que podem se conectar ao ciclo de vida do agente (`pre_turn`, `post_turn`, `pre_tool_call`, `post_tool_call`) e vetar despachos de ferramentas.

```bash
veles module add https://github.com/org/module-repo
veles module list
```

---

## TUI

```bash
veles                        # new session (bare `veles` launches the TUI)
veles tui --resume <id>      # continue a session
```

<p align="center">
  <img src="docs/assets/tui-tour.gif" alt="TUI do Veles — inspetores de barra (/status, /context), troca de modos e a paleta de comandos" width="800">
</p>

Os comandos de barra expõem tudo ao vivo — `/status`, `/tokens`, `/context`, `/mode`, `/help` — e `Shift+Tab` alterna entre os modos (auto / planning / writing / goal).

| Tecla | Ação |
|---|---|
| `Enter` | Enviar mensagem |
| `Shift+Enter` | Nova linha no compositor |
| `Ctrl+I` | Alternar o inspetor de atividade de ferramentas |
| `Ctrl+R` | Overlay do seletor de sessões |
| `Ctrl+G` | Abrir o `$EDITOR` no rascunho atual |
| `Tab` | Autocompletar comandos de barra |
| `Ctrl+D` | Sair |

Comandos de barra: `/help` · `/model` · `/mode` · `/status` · `/tokens` · `/context` · `/wiki` · `/save <slug>` · `/history` · `/insights` · `/rules` · `/daemon` e mais.

---

## Daemon + Telegram

Rode o Veles como um daemon persistente com uma API HTTP/WebSocket. Em um diretório de projeto novo, `veles daemon start` orienta você por toda a configuração — inicializar o projeto, habilitar o daemon e **conectar um canal**: primeiro escolha um *tipo* de canal (o Telegram é a única plataforma hoje, mas o seletor é o ponto de encaixe onde novos canais se registram), depois preencha os campos daquele canal (token do bot, whitelist). Não é preciso abrir a TUI antes.

<p align="center">
  <img src="docs/assets/daemon-setup.gif" alt="veles daemon start — assistente que sobe o daemon e conecta um canal do Telegram (tipo do canal primeiro, depois o token e a whitelist)" width="800">
</p>

```bash
veles daemon start                        # wizard (fresh dir) → starts on 127.0.0.1:8765
veles daemon status                       # is it running?
veles daemon list                         # daemons across all projects
```

O `veles daemon` sozinho abre um painel de controle ao vivo — uma árvore de projeto → daemons → canais. Inicie, pare, reinicie ou exclua daemons, e adicione/remova canais (o mesmo fluxo de tipo-de-canal-primeiro, tecla `c`) em todos os projetos, tudo pelo teclado:

<p align="center">
  <img src="docs/assets/daemon-panel.gif" alt="veles daemon — TUI de painel de controle: uma árvore de projeto → daemons → canais com iniciar/parar/reiniciar/excluir e gerenciamento de canais embutido" width="800">
</p>

O mesmo assistente de canal também está disponível de forma independente (`veles channel add`) em um projeto que já esteja rodando.

Endpoints da API: `POST /v1/runs` para enviar um prompt, `WS /v1/runs/{id}/events` para transmitir a resposta, `GET /v1/sessions` para listar sessões. Todos, exceto `GET /v1/health`, exigem `Authorization: Bearer <token>` (gere um com `veles daemon token add <name>`).

Cada usuário do Telegram recebe uma sessão persistente. Use `veles channel list-sessions` / `reset-session` para gerenciar os mapeamentos.

---

## Multiprojeto

```bash
veles project list                       # registered projects
veles project switch <slug>              # print the absolute path
cd $(veles project switch <slug>)        # jump to a project

veles subproject init frontend           # create a child project
veles subproject suggest --save          # agent-detected topic clusters → proposals
```

---

## Confiança e segurança

Toda chamada de ferramenta sensível (execução de shell, escrita de arquivos, busca de URLs) pede confirmação:

```
Tool 'run_shell' wants to execute. Allow?
  [1] Once  [2] Always for this project  [3] Always everywhere  [4] Refuse
```

Pré-conceda para CI ou execuções autônomas prolongadas:

```bash
veles trust set run_shell --scope project   # pre-grant for this project
veles autopilot enable --until +2h          # temporary trust bypass (audit-logged)
veles autopilot disable
```

O agente enxerga apenas o diretório do projeto ativo — outros projetos, escapes por symlink e travessia com `..` são bloqueados.

---

## Exportação / Importação

```bash
veles export full ./backup.tar.gz        # full backup: memory, sessions, telemetry
veles export template ./template.tar.gz  # sanitised template (no sources/sessions/PII)
veles import ./backup.tar.gz --into ./new-dir
```

---

## Referência da CLI

| Comando | Finalidade |
|---|---|
| `veles init [name]` | Criar um novo projeto |
| `veles run "<prompt>"` | Execução do agente em um único turno |
| `veles tui` | REPL interativo em TUI |
| `veles add <file\|url>` | Ingerir uma fonte → página do wiki |
| `veles research "<question>"` | Pesquisa profunda em múltiplos ângulos |
| `veles curate` | Consolidar sessões no wiki |
| `veles sessions {list,show,delete,search}` | Gerenciamento de sessões |
| `veles skill {list,add,remove,promote,demote,dedup,suggest-promote}` | Gerenciamento de skills |
| `veles tool {list,show,promote}` | Gerenciamento de ferramentas |
| `veles module {list,add,remove}` | Gerenciamento de plugins |
| `veles route {show,set,reset,refresh}` | Roteamento de modelos |
| `veles goal {list,show,start,checkpoint,pause,resume,done,cancel}` | Objetivos de longo prazo |
| `veles job {list,add,show,pause,resume,trigger,remove,history}` | Tarefas agendadas |
| `veles dream` | Ciclo de consolidação de memória em segundo plano |
| `veles project {list,add,remove,switch}` | Registro multiprojeto |
| `veles subproject {init,list,switch,remove,suggest}` | Projetos filhos |
| `veles trust {list,set,revoke,clear}` | Concessões de confiança |
| `veles autopilot {enable,disable,status}` | Bypass temporário de confiança |
| `veles secret {set,get,list,delete}` | Segredos no keychain do SO |
| `veles daemon {start,stop,status,list,restart,delete,session,token}` | Daemon HTTP/WS |
| `veles channel {run,list-sessions,reset-session}` | Gateway de canais externos |
| `veles mcp {list,test}` | Servidores MCP externos |
| `veles models <provider>` | Listar modelos do provedor |
| `veles doctor` | Verificações de saúde |
| `veles export / import` | Backup e transferência de projetos |

Todo comando tem `--help`.

---

## Documentação

Documentação completa — organizada por Diátaxis (tutoriais · guias práticos · referência · explicação):

- **Português (BR):** [`docs/pt-BR/index.md`](docs/pt-BR/index.md)

Outros idiomas: use o seletor 🌐 no topo de qualquer página da documentação.

---

## Como contribuir

Contribuições são muito bem-vindas — o Veles foi **feito para ser estendido**. O núcleo permanece pequeno (loop do agente + memória do projeto + protocolo de provedor); quase todo o resto é um ponto de extensão plugável, então adicionar uma capacidade raramente significa mexer no núcleo:

- **Adaptadores de provedor** (`src/veles/adapters/`) — conecte um novo backend de modelo.
- **Skills** — blocos de prompt e ferramentas reutilizáveis com herança via `extends:`, promovíveis de um projeto para o nível global do usuário.
- **Ferramentas** — Python tipado que o agente escreve e reutiliza, em `<project>/.veles/tools/`.
- **Pacotes de layout** — um único `layout.toml` em `~/.veles/layouts/<name>/` define um layout de conteúdo inteiro.
- **Hooks de módulo** — observabilidade, logging e políticas via hooks `pre_turn` / `post_turn` (`src/veles/core/modules.py`).
- **Canais & servidores MCP** — novos gateways e fontes externas de ferramentas.
- **Locales** — traduções em `src/veles/locales/`.

```bash
git clone https://github.com/denisotree/veles.git && cd veles
uv sync                              # runtime + dev dependencies
uv run pytest                        # the full suite (3200+ tests, no network)
uv run ruff check src tests && uv run mypy
```

A base de código é deliberadamente decomposta — responsabilidade única, sem arquivos monstruosos. Leia [`CONTRIBUTING.md`](CONTRIBUTING.md) para conhecer as convenções e [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md) antes de abrir um PR. Boas primeiras contribuições: adaptadores de provedor, skills de fluxo de trabalho, hooks de módulo e arquivos de locale.

---

## Licença

Apache 2.0 com concessão de patente — veja [`LICENSE`](LICENSE) e [`NOTICE`](NOTICE).

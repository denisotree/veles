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
  <a href="README.pt-BR.md">Português (BR)</a> ·
  <b>Português (PT)</b> ·
  <a href="README.ru.md">Русский</a> ·
  <a href="README.ar.md">العربية</a> ·
  <a href="README.hi.md">हिन्दी</a> ·
  <a href="README.bn.md">বাংলা</a> ·
  <a href="README.vi.md">Tiếng Việt</a>
</p>

**Uma framework minimalista de agente CLI que fica mais inteligente a cada sessão.**

<p align="center">
  <img src="docs/assets/tui-hero.gif" alt="TUI do Veles — faz uma pergunta e obtém uma resposta fundamentada na própria memória do projeto" width="800">
</p>

Ao contrário das ferramentas de chat que recomeçam do zero de cada vez, o Veles mantém uma **memória de projeto estruturada** — descobertas, regras e conhecimento curado que se acumulam ao longo das sessões e tornam o agente mais útil quanto mais o utilizas. A forma como o teu *conteúdo* está organizado é configurável: por predefinição, uma wiki LLM ao estilo Karpathy, notas planas ou nenhuma estrutura de todo para repositórios de código. Construído de forma limpa: sem ficheiros-monstro, sem dependência de fornecedores, sem sincronização na nuvem.

```bash
uv tool install veles-ai          # installs the `veles` command
veles init && veles run "Summarize the project architecture."
veles        # interactive REPL (bare `veles` == `veles tui`)
```

---

## Porquê o Veles?

**Memória cumulativa** — Cada sessão é destilada pelo Curador para a memória de cada projeto (descobertas, regras comportamentais, resumos de sessão em `.veles/`). O agente recorda automaticamente factos relevantes e decisões passadas — deixas de ter de reexplicar o mesmo contexto. A memória funciona sob *qualquer* layout de conteúdo.

**Layouts de conteúdo configuráveis** — `veles init` cria por predefinição uma wiki LLM ao estilo Karpathy; `--layout notes` dá-te um diretório de notas planas; `--layout bare` não adiciona estrutura nenhuma (ideal para repositórios de código). Os pacotes de layout personalizados são um único ficheiro TOML em `~/.veles/layouts/`.

**Roteamento agnóstico ao fornecedor** — OpenRouter, Anthropic, OpenAI, Gemini, Ollama, llamacpp ou a tua subscrição da CLI `claude`/`gemini`. Diferentes tipos de tarefa (planeamento, compressão, descobertas) podem ser encaminhados para modelos diferentes.

**Competências que se acumulam** — Blocos de prompt reutilizáveis tornam-se ferramentas do agente. Promove uma competência de um projeto para o nível global do utilizador e fica disponível em todo o lado. A desduplicação integrada encontra competências quase duplicadas antes que comecem a divergir.

**Local em primeiro lugar + isolado** — Sem telemetria, sem sincronização na nuvem. O agente só vê o diretório do projeto ativo. A escala de confiança pede aprovação a cada chamada de ferramenta sensível; concede previamente para CI.

**Modular, não monolítico** — Núcleo mínimo (memória, ciclo do agente, protocolo de fornecedor, registo de ferramentas). Tudo o resto — TUI, daemon, gateway do Telegram, investigação aprofundada, agendador de tarefas — é um módulo opcional e carregável.

---

## Início Rápido

**Requisitos:** Python 3.13+, macOS / Linux (Windows na medida do possível). Instala primeiro o [uv](https://docs.astral.sh/uv/).

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

Em alternativa, abre a TUI interativa (o comando `veles` simples faz o mesmo):

```bash
veles
```

Na primeira execução, um assistente de configuração pede o teu idioma preferido, o fornecedor e o nome do projeto.

---

## Fornecedores

| Fornecedor | Variável de ambiente | Notas |
|---|---|---|
| **OpenRouter** *(recomendado)* | `OPENROUTER_API_KEY` | Claude, GPT, Gemini, Llama — uma só chave, centenas de modelos |
| Anthropic | `ANTHROPIC_API_KEY` | API direta |
| OpenAI | `OPENAI_API_KEY` | API direta |
| Gemini | `GEMINI_API_KEY` ou `GOOGLE_API_KEY` | API direta |
| CLI `claude` | — | Usa a tua subscrição Claude; não é necessária chave de API |
| CLI `gemini` | — | Usa a tua subscrição Gemini; não é necessária chave de API |
| Ollama | — | Modelos locais, `http://localhost:11434/v1` |
| llamacpp | — | Modelos locais, `http://localhost:8080/v1` |
| openai-compat | `OPENAI_COMPAT_BASE_URL` | Qualquer endpoint compatível com OpenAI |

Substitui por execução:

```bash
veles run --provider anthropic --model anthropic/claude-opus-4-8 "..."
veles run --provider ollama --model llama3.2 "..."
```

Guarda as chaves de API na chaveira do sistema operativo em vez de em variáveis de ambiente:

```bash
veles secret set OPENROUTER_API_KEY    # prompts for value, stores in keychain
```

---

## Fluxo de Trabalho Principal

### Escolher um layout de conteúdo

```bash
veles init                  # default: Karpathy-style LLM wiki (sources/ + wiki/)
veles init --layout notes   # a single flat notes/ directory
veles init --layout bare    # no content scaffold — code repos, free-form work
```

A própria memória do agente (descobertas, regras, resumos de sessão em `.veles/`) funciona de forma idêntica sob qualquer layout. Os pacotes personalizados são um único `layout.toml` em `~/.veles/layouts/<name>/`.

### Construir uma base de conhecimento (layout llm-wiki)

```bash
veles add paper.pdf                   # read a source → write a wiki page
veles add https://example.com/post    # web pages, PDFs, plain text

veles run "What do we know about the authentication design?"
veles curate                          # explicit session → memory consolidation
```

<p align="center">
  <img src="docs/assets/kb-ingest.gif" alt="Base de conhecimento do Veles — ingere uma fonte numa página da wiki, depois faz uma pergunta e obtém uma resposta que a cita" width="800">
</p>

O Curador é executado automaticamente após as sessões. A extração de descobertas deteta frases como "preferir sempre X" ou "nunca fazer Y" e regista-as como descobertas persistentes do projeto.

### Investigação aprofundada

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

## Roteamento de Modelos (Conjuntos)

Encaminha diferentes tipos de tarefa para diferentes modelos — configura uma vez e esquece.

**Através da CLI:**
```bash
veles route show                                          # current routing table
veles route set compressor anthropic/claude-haiku-4-5    # typed override
veles route reset compressor                             # back to default
```

**Através de linguagem natural em `AGENTS.md`:**
```markdown
## Routing
Use Opus for planning and architecture decisions.
Haiku is fine for compression and insight extraction.
```

```bash
veles route refresh    # parse the NL hints; typed overrides always win
```

---

## Competências e Módulos

As **Competências** são blocos de prompt reutilizáveis (`SKILL.md`) que se tornam ferramentas do agente automaticamente.

```bash
veles skill add https://github.com/org/skill-repo    # install from git
veles skill add ./local-skill-dir                    # or from local path
veles skill list                                     # list with telemetry
veles skill promote my-skill                         # copy to ~/.veles/skills (global)
veles skill dedup                                    # find near-duplicates
veles skill suggest-promote --save                   # propose promotions based on usage
```

Os **Módulos** são plugins Python que podem ligar-se ao ciclo de vida do agente (`pre_turn`, `post_turn`, `pre_tool_call`, `post_tool_call`) e vetar despachos de ferramentas.

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

Os comandos de barra revelam tudo em tempo real — `/status`, `/tokens`, `/context`, `/mode`, `/help` — e `Shift+Tab` alterna entre modos (auto / planning / writing / goal).

| Tecla | Ação |
|---|---|
| `Enter` | Enviar mensagem |
| `Shift+Enter` | Nova linha no compositor |
| `Ctrl+I` | Alternar inspetor de atividade de ferramentas |
| `Ctrl+R` | Sobreposição do seletor de sessões |
| `Ctrl+G` | Abrir `$EDITOR` no rascunho atual |
| `Tab` | Conclusão automática de comandos de barra |
| `Ctrl+D` | Sair |

Comandos de barra: `/help` · `/model` · `/mode` · `/status` · `/tokens` · `/context` · `/wiki` · `/save <slug>` · `/history` · `/insights` · `/rules` · `/daemon` e mais.

---

## Daemon + Telegram

Executa o Veles como um daemon persistente com uma API HTTP/WebSocket. Num diretório de projeto novo, `veles daemon start` guia-te pela configuração — inicializa o projeto, ativa o daemon e **liga um canal**: primeiro escolhe um *tipo* de canal (o Telegram é a única plataforma disponível hoje, mas o seletor é o ponto de ligação onde os novos canais se registam), depois preenche os campos desse canal (token do bot, lista de autorizações). Não é preciso abrir a TUI primeiro.

<p align="center">
  <img src="docs/assets/daemon-setup.gif" alt="veles daemon start — assistente que arranca o daemon e liga um canal do Telegram (primeiro o tipo de canal, depois o seu token e lista de autorizações)" width="800">
</p>

```bash
veles daemon start                        # wizard (fresh dir) → starts on 127.0.0.1:8765
veles daemon status                       # is it running?
veles daemon list                         # daemons across all projects
```

O comando `veles daemon` simples abre um painel de controlo em tempo real — uma árvore de projeto → daemons → canais. Inicia, para, reinicia ou elimina daemons, e adiciona/remove canais (o mesmo fluxo de tipo de canal primeiro, tecla `c`) em todos os projetos, tudo a partir do teclado:

<p align="center">
  <img src="docs/assets/daemon-panel.gif" alt="veles daemon — TUI de painel de controlo: uma árvore de projeto → daemons → canais com iniciar/parar/reiniciar/eliminar e gestão de canais embutida" width="800">
</p>

O mesmo assistente de canais também está disponível de forma autónoma (`veles channel add`) num projeto já em execução.

Endpoints da API: `POST /v1/runs` para submeter um prompt, `WS /v1/runs/{id}/events` para receber a resposta em fluxo, `GET /v1/sessions` para listar sessões. Todos exceto `GET /v1/health` exigem `Authorization: Bearer <token>` (gera um com `veles daemon token add <name>`).

Cada utilizador do Telegram tem uma sessão persistente. Usa `veles channel list-sessions` / `reset-session` para gerir os mapeamentos.

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

## Confiança e Segurança

Cada chamada de ferramenta sensível (execução de shell, escritas em ficheiros, obtenção de URL) pede aprovação:

```
Tool 'run_shell' wants to execute. Allow?
  [1] Once  [2] Always for this project  [3] Always everywhere  [4] Refuse
```

Concede previamente para CI ou execuções autónomas prolongadas:

```bash
veles trust set run_shell --scope project   # pre-grant for this project
veles autopilot enable --until +2h          # temporary trust bypass (audit-logged)
veles autopilot disable
```

O agente só vê o diretório do projeto ativo — outros projetos, fugas por symlink e travessias com `..` são bloqueados.

---

## Exportar / Importar

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
| `veles run "<prompt>"` | Execução do agente num único turno |
| `veles tui` | REPL interativo em TUI |
| `veles add <file\|url>` | Ingerir uma fonte → página da wiki |
| `veles research "<question>"` | Investigação aprofundada multifacetada |
| `veles curate` | Consolidar sessões na wiki |
| `veles sessions {list,show,delete,search}` | Gestão de sessões |
| `veles skill {list,add,remove,promote,demote,dedup,suggest-promote}` | Gestão de competências |
| `veles tool {list,show,promote}` | Gestão de ferramentas |
| `veles module {list,add,remove}` | Gestão de plugins |
| `veles route {show,set,reset,refresh}` | Roteamento de modelos |
| `veles goal {list,show,start,checkpoint,pause,resume,done,cancel}` | Objetivos de longo horizonte |
| `veles job {list,add,show,pause,resume,trigger,remove,history}` | Tarefas agendadas |
| `veles dream` | Ciclo de consolidação de memória em segundo plano |
| `veles project {list,add,remove,switch}` | Registo multiprojeto |
| `veles subproject {init,list,switch,remove,suggest}` | Projetos-filhos |
| `veles trust {list,set,revoke,clear}` | Concessões de confiança |
| `veles autopilot {enable,disable,status}` | Suspensão temporária da confiança |
| `veles secret {set,get,list,delete}` | Segredos na chaveira do SO |
| `veles daemon {start,stop,status,list,restart,delete,session,token}` | Daemon HTTP/WS |
| `veles channel {run,list-sessions,reset-session}` | Gateway de canais externos |
| `veles mcp {list,test}` | Servidores MCP externos |
| `veles models <provider>` | Listar modelos do fornecedor |
| `veles doctor` | Verificações de saúde |
| `veles export / import` | Cópia de segurança e transferência de projetos |

Cada comando tem `--help`.

---

## Documentação

Documentação completa — organizada segundo Diátaxis (tutoriais · guias práticos · referência · explicação):

- **English:** [`docs/en/index.md`](docs/en/index.md)
- **Русский:** [`docs/ru/index.md`](docs/ru/index.md)

---

## Contribuir

As contribuições são muito bem-vindas — o Veles foi **construído para ser estendido**. O núcleo mantém-se pequeno (ciclo do agente + memória do projeto + protocolo de fornecedor); quase tudo o resto é um ponto de extensão configurável, pelo que acrescentar uma capacidade raramente significa mexer no núcleo:

- **Adaptadores de fornecedor** (`src/veles/adapters/`) — liga um novo backend de modelo.
- **Competências** — blocos de prompt e ferramentas reutilizáveis com herança `extends:`, promovíveis de um projeto para o nível global do utilizador.
- **Ferramentas** — Python tipado que o agente escreve e reutiliza, em `<project>/.veles/tools/`.
- **Pacotes de layout** — um único `layout.toml` em `~/.veles/layouts/<name>/` define um layout de conteúdo inteiro.
- **Hooks de módulo** — observabilidade, registo e política através de hooks `pre_turn` / `post_turn` (`src/veles/core/modules.py`).
- **Canais e servidores MCP** — novos gateways e fontes de ferramentas externas.
- **Localizações** — traduções em `src/veles/locales/`.

```bash
git clone https://github.com/denisotree/veles.git && cd veles
uv sync                              # runtime + dev dependencies
uv run pytest                        # the full suite (3200+ tests, no network)
uv run ruff check src tests && uv run mypy
```

O código está deliberadamente decomposto — responsabilidade única, sem ficheiros-monstro. Lê o [`CONTRIBUTING.md`](CONTRIBUTING.md) para as convenções e o [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md) antes de abrir um PR. Boas primeiras contribuições: adaptadores de fornecedor, competências de fluxo de trabalho, hooks de módulo e ficheiros de localização.

---

## Licença

Apache 2.0 com concessão de patente — vê [`LICENSE`](LICENSE) e [`NOTICE`](NOTICE).

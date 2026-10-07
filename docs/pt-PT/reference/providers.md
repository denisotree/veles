# Fornecedores

> 🌐 **Idiomas:** [English](../../en/reference/providers.md) · [简体中文](../../zh-CN/reference/providers.md) · [繁體中文](../../zh-TW/reference/providers.md) · [日本語](../../ja/reference/providers.md) · [한국어](../../ko/reference/providers.md) · [Español](../../es/reference/providers.md) · [Français](../../fr/reference/providers.md) · [Italiano](../../it/reference/providers.md) · [Português (BR)](../../pt-BR/reference/providers.md) · **Português (PT)** · [Русский](../../ru/reference/providers.md) · [العربية](../../ar/reference/providers.md) · [हिन्दी](../../hi/reference/providers.md) · [বাংলা](../../bn/reference/providers.md) · [Tiếng Việt](../../vi/reference/providers.md)

O Veles é agnóstico quanto ao fornecedor. Passe `--provider <id>` a qualquer comando do
agente, ou defina uma predefinição na configuração. Os IDs de modelo usam a própria
nomenclatura do fornecedor.

## O catálogo de fornecedores

Todos os fornecedores que o Veles conhece são entradas de um único catálogo, construído a
partir de três origens:

1. **Incorporados** — a tabela abaixo, distribuída com o Veles.
2. **Os seus** — `~/.veles/providers.toml`: uma API alojada compatível com a OpenAI ou um
   servidor que o próprio executa, acrescentando uma entrada (ver
   [adicionar o seu próprio fornecedor](../how-to/configure-providers.md#adicionar-o-seu-próprio-fornecedor)).
   Uma entrada com um id incorporado sobrepõe as definições desse fornecedor (o seu
   `base_url`, por exemplo).
3. **Módulos** — um módulo do registo contribui com um fornecedor (`antigravity-cli`).
   Nomeá-lo em `[engine] provider`, numa rota ou em `--provider` instala-o a partir dos
   seus registos ligados na execução seguinte, tal como um canal declarado.

`--provider`, `veles models`, os assistentes de configuração, o encaminhamento e o
`veles doctor` lêem todos o catálogo, pelo que um fornecedor de qualquer origem funciona
em todo o lado onde um incorporado funciona. Um id desconhecido é um erro de uma linha que
lista o que existe; o `veles doctor` verifica também o `~/.veles/providers.toml` e todos
os fornecedores que as suas rotas nomeiam.

| Fornecedor | Tipo | Chave de API | Notas |
|---|---|---|---|
| `openrouter` | Gateway na nuvem | `OPENROUTER_API_KEY` | **Predefinição.** Retransmite centenas de modelos; IDs de modelo como `anthropic/claude-sonnet-4.6` |
| `anthropic` | Nuvem directa | `ANTHROPIC_API_KEY` | API Messages do Claude, prompt caching |
| `openai` | Nuvem directa | `OPENAI_API_KEY` | Chat completions do GPT |
| `gemini` | Nuvem directa | `GEMINI_API_KEY` / `GOOGLE_API_KEY` | Google Gemini |
| `claude-cli` | CLI delegada | — (sessão da CLI) | Delega numa CLI `claude` local em modo JSON-stream |
| `codex` | CLI delegada | — (sessão da CLI) | Delega numa CLI `codex` local (subscrição do ChatGPT) |
| `ollama` | Local | nenhuma | `OLLAMA_BASE_URL` (predefinição `http://localhost:11434/v1`) |
| `llamacpp` | Local | nenhuma | `LLAMACPP_BASE_URL` (predefinição `http://localhost:8080/v1`) |
| `openai-compat` | Local/personalizado | `OPENAI_COMPAT_API_KEY` opcional | `OPENAI_COMPAT_BASE_URL` (obrigatória, sem predefinição) |

O `gemini-cli` foi removido na 1.2.6 — a Google já não disponibiliza a CLI do Gemini a
contas pessoais. Use o `gemini` com uma chave de API, ou o módulo `antigravity-cli`.

Fornecedor predefinido: `openrouter`. **Não existe um modelo predefinido rígido** — defina
um através do assistente de configuração, de `[engine] model`, ou de `--model` (caso
contrário o agente reporta "no model configured"). As rotas por tarefa herdam `[engine]`
como base, a menos que sejam sobrepostas em `[routing.tasks]` — ver
[encaminhamento por tarefa](../how-to/per-task-routing.md).

## Fornecedores locais

`ollama`, `llamacpp` e `openai-compat` não precisam de chave de API. Liste os modelos
instalados com `veles models <provider>` (sempre ao vivo para os fornecedores locais).

**A chamada a ferramentas é detectada** a partir do que o backend anuncia: o ollama indica
as capacidades de cada modelo, um servidor llama.cpp as do seu chat template.
`VELES_LOCAL_TOOLS=1` força a chamada a ferramentas ligada, `=0` desligada; sem definir,
é detectada.

```bash
veles run --provider ollama --model qwen3:4b-instruct "..."
```

Sobreponha os endpoints com as variáveis de ambiente `*_BASE_URL` (ver
[variáveis de ambiente](environment-variables.md)).

## Delegação por CLI (`claude-cli`, `codex`, `antigravity-cli`)

Se tiver uma subscrição do Claude, do ChatGPT ou da Google, o Veles pode executar a
respectiva CLI em modo headless e actuar como coordenador — sem uma chave de API
separada. O `claude-cli` e o `codex` são incorporados; o `antigravity-cli` (a CLI `agy`)
é um módulo do registo que se instala sozinho quando o nomeia.

O delegado é apenas o modelo: as ferramentas do Veles chegam até ele por uma ponte MCP, e
cada chamada passa pela escada de confiança do Veles. A configuração da ponte fica numa
diretoria do processo em execução, `.veles/tmp/delegate-<pid>/`, removida quando este
termina. O `agy` corre num espaço de trabalho temporário fora do seu projecto (em
`~/.veles/tmp/`), pelo que a configuração `.agents/` do próprio projecto nunca chega
até ele, atrás de um filtro que nega o seu próprio shell e as suas ferramentas de
ficheiros.

O `codex` também corre fora do seu projecto (em `~/.veles/tmp/`), com a sua configuração
do codex ignorada e as suas próprias ferramentas — shell, edição de ficheiros, imagens,
subagentes, navegador, pesquisa na web — desligadas; o Veles verifica os nomes dessas
flags uma vez por processo e recusa-se a executar um codex que tenha renomeado alguma de
que depende. O seu servidor MCP é passado nos argumentos, não num ficheiro. No
`veles run`, o codex segue o protocolo de ferramentas do Veles com menos fiabilidade do
que o claude: pode responder que não consegue ler um ficheiro sem chamar a ferramenta —
pergunte de novo ou nomeie a ferramenta ("use read_file em …").

## Estado multimodal (visão / fala-para-texto)

O Veles define um `VisionAdapter` e um protocolo de adaptador STT (`modules/vision.py`,
`modules/stt.py`) mais um registo global ao processo, **mas não vem incluído nenhum
adaptador concreto e nada regista um no arranque do daemon**. Por isso, uma foto ou
mensagem de voz enviada a um canal devolve actualmente um aviso de "não configurado" em vez
de ser analisada. A tarefa de encaminhamento `vision` existe para quando um adaptador for
ligado. Ver [ligar o Telegram](../how-to/connect-telegram.md#multimodal-limitation).

## Escolher um modelo

```bash
veles models openrouter            # cached 24h
veles models openrouter --refresh  # bypass cache
veles models ollama                # always live
```

Para usar modelos diferentes para tarefas diferentes (barato para compressão, forte para
planeamento), ver [encaminhamento por tarefa](../how-to/per-task-routing.md).

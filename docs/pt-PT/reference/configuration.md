# Referência de configuração

> 🌐 **Idiomas:** [English](../../en/reference/configuration.md) · [简体中文](../../zh-CN/reference/configuration.md) · [繁體中文](../../zh-TW/reference/configuration.md) · [日本語](../../ja/reference/configuration.md) · [한국어](../../ko/reference/configuration.md) · [Español](../../es/reference/configuration.md) · [Français](../../fr/reference/configuration.md) · [Italiano](../../it/reference/configuration.md) · [Português (BR)](../../pt-BR/reference/configuration.md) · **Português (PT)** · [Русский](../../ru/reference/configuration.md) · [العربية](../../ar/reference/configuration.md) · [हिन्दी](../../hi/reference/configuration.md) · [বাংলা](../../bn/reference/configuration.md) · [Tiếng Việt](../../vi/reference/configuration.md)

O Veles é configurado por dois ficheiros TOML e um conjunto de directórios de estado.
Os segredos (chaves de API, tokens de bot) **nunca** são escritos nestes ficheiros —
residem no chaveiro do SO ou em variáveis de ambiente (ver [variáveis de ambiente](environment-variables.md)).

## Onde reside o estado

| Caminho | Âmbito | Conteúdo |
|---|---|---|
| `~/.veles/` | Global do utilizador | `config.toml`, concessões de confiança, skills/ferramentas transversais a projectos, cache de modelos, locales, registo |
| `<project>/.veles/` | Local do projecto | `project.toml`, `config.toml`, `memory.db`, skills/ferramentas do projecto, planos, artefactos de runtime |
| `<project>/AGENTS.md` | Projecto | O ficheiro de contexto injectado no agente (com symlink para `CLAUDE.md` / `GEMINI.md`) |
| `<project>/wiki/`, `sources/` | Projecto | Conteúdo do utilizador (o layout LLM-Wiki predefinido) |

`VELES_USER_HOME` redirecciona o `~` (para que o estado do utilizador fique em
`<override>/.veles/`). Ver [estrutura do projecto](project-layout.md) para a árvore completa.

---

## Configuração do utilizador — `~/.veles/config.toml`

Escrita pelo assistente do primeiro arranque; segura para editar à mão.

```toml
[user]
language = "en"                  # "en" | "ru" — UI string locale
default_provider = "openrouter"  # default provider for new projects
default_model = "anthropic/claude-sonnet-4.6"
first_project_name = "myorg"     # recorded by the wizard
tui_theme = "everforest"         # everforest | dracula | gruvbox | tokyo-night | catppuccin

[permissions]                    # optional per-tool policy
fetch_url  = "approval_required" # allow | approval_required | always_confirm
write_file = "always_confirm"

[routing.tasks]                  # optional user-scope routing (see below)
compressor = "openrouter:anthropic/claude-haiku-4.5"

[mcp.servers.my-server]          # optional user-scope MCP servers
transport = "stdio"
command = "python"               # executable only — arguments go in `args`
args = ["-m", "my_mcp_server"]
```

| Chave | Tipo | Finalidade |
|---|---|---|
| `[user] language` | `"en"` \| `"ru"` | Locale para as strings da UI (sobreponível via `VELES_LOCALE`) |
| `[user] default_provider` | string | Fornecedor usado quando nenhum é indicado |
| `[user] default_model` | string | Modelo usado quando nenhum é indicado |
| `[user] tui_theme` | string | Tema de cores predefinido da TUI |
| `[permissions] <tool>` | política | Política de permissões por ferramenta (ver [confiança e sandbox](../explanation/trust-and-sandbox.md)) |

---

## Configuração do projecto — `<project>/.veles/config.toml`

```toml
[engine]
provider = "openrouter"                               # provider name for the main agent + routing base
model = "anthropic/claude-sonnet-4.6"                # model id (omit to require --model or the user default_model)
request_timeout_s = 180                              # opcional; quanto esperar por uma resposta
max_retries = 1                                      # opcional; tentativas por pedido

[routing.tasks]                  # per-task overrides (highest priority below explicit flags)
default    = "openrouter:anthropic/claude-sonnet-4.6"
compressor = "openrouter:anthropic/claude-haiku-4.5"
insights   = "openrouter:anthropic/claude-haiku-4.5"
advisor    = "openrouter:anthropic/claude-opus-4.8"
vision     = "openai:gpt-4o"
embedding  = "openai:text-embedding-3-small"

[daemon]                         # the unnamed/"default" daemon
enabled = true
host = "127.0.0.1"
port = 8765
autostart = false

[daemon.api]                     # a named daemon session ("api")
provider = "anthropic"
model = "claude-opus-4.8"
host = "127.0.0.1"
port = 8801
mode = "auto"

[channels.telegram]              # global channels (served by the unnamed daemon)
enabled = true
whitelist = ["@alice", "123456789"]

[daemon.api.channels.telegram]   # channels bound to a named daemon session
enabled = true
whitelist = ["@bob"]

[mcp.servers.github]             # external MCP servers (project scope)
transport = "stdio"             # stdio | http | sse
command = "npx"                  # executable only — arguments go in `args`
args = ["-y", "@modelcontextprotocol/server-github"]
env = { GITHUB_TOKEN = "${GITHUB_TOKEN}" }   # ${VAR} interpolates from the environment
```

### Secções

| Secção | Finalidade |
|---|---|
| `[engine]` | Fornecedor base (`provider` = nome do fornecedor) + modelo (`model` = id do modelo) para o agente principal e a cascata de encaminhamento, mais os orçamentos de cliente `request_timeout_s` / `max_retries` |
| `[routing.tasks]` | Sobreposições `provider:model` por tarefa — ver [encaminhamento por tarefa](../how-to/per-task-routing.md) |
| `[permissions]` | Política de permissões por ferramenta (âmbito do projecto) |
| `[daemon]` | Vínculo (bind) + autostart do daemon sem nome/"default" |
| `[daemon.<name>]` | Uma sessão de daemon nomeada (modelo/fornecedor/host/porta/modo próprios) |
| `[goal]` | O orçamento de um objetivo novo — `max_steps` (30), `max_cost_usd` (5.0), `max_wall_time_s` (3600); as flags de `veles goal start` substituem-no |
| `[channels.<type>]` | Um canal servido pelo daemon sem nome (p. ex. `telegram`) |
| `[daemon.<name>.channels.<type>]` | Um canal ligado a uma sessão de daemon nomeada |
| `[mcp.servers.<name>]` | Um servidor MCP externo (fonte de ferramentas) |

Tipos de tarefa para `[routing.tasks]`: `default`, `curator`, `compressor`, `insights`,
`skills`, `advisor`, `vision`, `embedding`.

> As pistas de encaminhamento em linguagem natural no `AGENTS.md` são analisadas para um
> `routing.nl.toml` gerado automaticamente; as entradas explícitas em `[routing.tasks]`
> ganham sempre. Execute `veles route refresh` para reanalisar. Ver
> [encaminhamento por tarefa](../how-to/per-task-routing.md).

### Quanto esperar por uma resposta, e quantas tentativas

```toml
[engine]
request_timeout_s = 180
max_retries = 1
```

Ambas são parâmetros do **cliente**, por isso ficam planas em `[engine]` e não em
`[engine.request.<provider>]`: essa secção é o *corpo* do pedido, e um tempo de
espera nunca viaja ali.

Sem elas, o tempo de espera é deduzido do id do modelo: uma família de raciocínio
recebe 900 s, uma variante `flash`/`mini` dela 450 s, o resto 120 s. Essa dedução é
um palpite estruturalmente frágil: **o nome descreve uma família, ao passo que o
tempo de resposta é definido pelo backend que a serve.** Um mesmo id pode correr a
33 tok/s num backend e 0,8 tok/s noutro. Quando o número deduzido não servir para a
sua execução, defina-o; e fixe o backend (abaixo) se quiser que esse número
signifique o mesmo duas vezes.

`max_retries` importa pela mesma razão. Sem ela, o SDK tenta de novo duas vezes, de
modo que um tempo de espera de 450 s são na verdade até 1350 s num único turno —
o bastante para estourar um orçamento que parecia generoso. `0` é um valor legítimo
e não é o mesmo que omitir a chave.

Precedência para ambas: argumento explícito no código → `[engine]` → valor por
modelo. Um valor que não seja um número positivo (ou, para `max_retries`, um
inteiro não negativo) aborta com um `ConfigError` que nomeia o ficheiro.

**Âmbito:** hoje só o adaptador do OpenRouter lê estas chaves. Os clientes
Anthropic, OpenAI e Gemini são construídos sem ambos os parâmetros e ignoram-nas.

### Fixar um backend e outras chaves do corpo do pedido

`[engine.request.<provider>]` é enviado **tal como está** no corpo do pedido
desse fornecedor. O Veles não modela o esquema do fornecedor, portanto qualquer
opção que este aceite funciona sem esperar que o Veles a conheça:

```toml
[engine.request.openrouter.provider]
order = ["GMICloud"]
allow_fallbacks = false

[engine.request.openrouter.reasoning]
enabled = false
```

A secção é indexada pelo **nome do fornecedor** (`openrouter`, `anthropic`,
`openai`, `gemini`, `ollama`, `llamacpp`, `openai-compat`) para que uma mesma
configuração de projeto sobreviva a uma mudança de backend: um bloco `provider`
do OpenRouter enviado ao llama.cpp seria um 400, por isso cada backend lê apenas
a sua própria subsecção. Sem secção declarada, os pedidos são idênticos byte a
byte aos anteriores.

**Quando é preciso: medições reprodutíveis.** Um relé como o OpenRouter distribui
um mesmo modelo por muitos backends com quantizações diferentes, pelo que duas
execuções sobre a mesma entrada podem divergir por razões alheias à entrada. O
encaminhamento persistente por `session_id` mantém uma conversa num único
backend, mas não diz em **qual**.

Fixe por `order`, não por `quantizations`. A 18-09-2026, `z-ai/glm-5.3-flash`
tem 29 endpoints: 16 em `fp8`, 3 em `fp4`, um `nvfp4`, **9 que não declaram
qualquer quantização** e nenhum em `bf16`. Ou seja, `quantizations = ["fp8"]`
ainda deixa 16 candidatos, com janelas de contexto de 262144 a 1310720 tokens,
ao passo que um `order` de um só elemento mais `allow_fallbacks = false`
determina o backend sem ambiguidade. Para listar os endpoints de um modelo:

```bash
curl -s https://openrouter.ai/api/v1/models/<author>/<slug>/endpoints \
  -H "Authorization: Bearer $OPENROUTER_API_KEY" | jq '.data.endpoints[]
  | {provider_name, quantization, context_length}'
```

Mantenha a fixação apenas no projeto de medição: produção quer encaminhamento
persistente, que preserva disponibilidade e fallback.

**Confirmar que se manteve.** Cada chamada ao modelo regista em
`.veles/traces.jsonl` tanto a intenção como o resultado: `request_extra` é o que
foi enviado, `upstream_provider` o backend que respondeu. Basta uma linha:

```bash
jq -r 'select(.session_id=="<sid>") | .upstream_provider' .veles/traces.jsonl | sort -u
```

Mais do que uma linha significa que a execução misturou backends. Os mesmos
registos trazem `reasoning_tokens` (quanto do orçamento foi para raciocínio) e
`est_cost_usd` (o custo real faturado pelo fornecedor, quando este o comunica).

**Os erros são ruidosos de propósito.** Um nome de fornecedor mal escrito ou um
erro no caminho da secção (`[engine.reqest.…]`) aborta a execução com um
`ConfigError` que nomeia o ficheiro e os fornecedores conhecidos: uma fixação que
nunca chegou ao fio invalidaria em silêncio a medição para a qual foi escrita. O
Veles não verifica as chaves *dentro* da subsecção, porque é o fornecedor que o
faz: o OpenRouter responde `400 provider: Unrecognized key: "quantization"` a uma
chave desconhecida e `404 No endpoints found …` a um valor sem correspondência.

### Durante quanto tempo as transcrições são guardadas

**Nada é apagado a menos que o peça.** `turn_retention_days` vale `0` por
predefinição, o que guarda para sempre todos os turnos de conversa. Defina um
número de dias para pôr um teto em `memory.db`:

```toml
[memory]
turn_retention_days = 90   # 0 (predefinição) guarda tudo
```

Com a opção ativa, os turnos em bruto mais antigos do que esse prazo são
apagados; os **insights** e as regras deles extraídos são guardados para sempre
em qualquer caso. A transcrição é a matéria-prima e os insights são aquilo para
que foi lida.

Uma transcrição só é descartada se **ambas** as condições se verificarem: ser mais
antiga do que a janela **e** o curador já ter processado essa sessão. Uma sessão
que o curador ainda não alcançou nunca é apagada, seja qual for a sua idade — caso
contrário a transcrição seria destruída antes de dela se ter aprendido algo.

O custo de a ativar: `veles sessions search` só encontra texto dentro da janela.
`veles sessions list` continua a mostrar execuções antigas, porque as linhas de
sessão (id, título, marcas temporais) são mantidas: só desaparecem os corpos das
mensagens. A limpeza ocorre durante `veles dream`, depois da extração de
insights.

### Rotação de logs

`traces.jsonl` e `events.jsonl` rodam aos 50 MB para `<nome>.<unix_ts>`, sendo
guardadas as **10** rotações mais recentes — as anteriores são apagadas na
rotação seguinte. Antes eram guardadas para sempre.

Em volumes normais não há nada a configurar: a ~530 bytes por registo de trace e
~1,1 KB de eventos por turno do agente, a primeira rotação está a anos de
distância. A definição existe porque um crescimento sem limite e sem política é
uma fuga que terá de ser descoberta por quem herdar a máquina.

### Imagens

Uma fotografia enviada para um canal é descrita antes de o turno começar, com o
modelo para que aponta `[routing.tasks].vision` — que, sem rota explícita, é o seu
modelo `[engine]`. Um motor multimodal não precisa, por isso, de qualquer
configuração.

`[vision] mode` escolhe o pipeline:

- `model` (predefinição) — o modelo de visão descreve a imagem.
- `ocr` — apenas Tesseract. Local, gratuito, sem chamada ao LLM; bom para
  digitalizações de texto.
- `ocr+model` — primeiro o texto literal, depois a descrição do modelo.
- `off` — nada é lido; o ficheiro é guardado à mesma e o agente pode chamar
  `image_describe` / `image_ocr` por iniciativa própria.

Defina `[vision] model` quando o motor for apenas de texto. Serve qualquer
fornecedor com visão, incluindo um servidor local: `ollama:llava`, `llamacpp:…`,
`openai-compat:…`.

### `project.toml`

O `<project>/.veles/project.toml` contém metadados imutáveis do projecto (`name`,
`created_at`, `schema_version`, `layout`). Normalmente não o edita à mão.

---

## AGENTS.md

O ficheiro de contexto do projecto, na raiz do projecto. É injectado no prompt de sistema
do agente no arranque e ligado por symlink a `CLAUDE.md` e `GEMINI.md` para que uma CLI
`claude` ou `gemini` lançada no directório apanhe o mesmo contexto.

Mantenha-o pequeno — os ficheiros `.md` auxiliares (p. ex. `wiki/INDEX.md`) carregam a
pedido. Valide as secções obrigatórias com `veles schema validate`. Ver
[packs de layout e o LLM-Wiki](../explanation/layout-packs-and-llm-wiki.md).

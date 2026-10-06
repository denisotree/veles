# Como configurar provedores

> 🌐 **Idiomas:** [English](../../en/how-to/configure-providers.md) · [简体中文](../../zh-CN/how-to/configure-providers.md) · [繁體中文](../../zh-TW/how-to/configure-providers.md) · [日本語](../../ja/how-to/configure-providers.md) · [한국어](../../ko/how-to/configure-providers.md) · [Español](../../es/how-to/configure-providers.md) · [Français](../../fr/how-to/configure-providers.md) · [Italiano](../../it/how-to/configure-providers.md) · **Português (BR)** · [Português (PT)](../../pt-PT/how-to/configure-providers.md) · [Русский](../../ru/how-to/configure-providers.md) · [العربية](../../ar/how-to/configure-providers.md) · [हिन्दी](../../hi/how-to/configure-providers.md) · [বাংলা](../../bn/how-to/configure-providers.md) · [Tiếng Việt](../../vi/how-to/configure-providers.md)

Alterne o Veles entre OpenRouter, Anthropic, OpenAI, Gemini, modelos locais ou uma
assinatura de CLI. Lista completa de provedores: [referência de provedores](../reference/providers.md).

## Escolha um provedor por comando

```bash
veles run --provider anthropic --model claude-sonnet-4.6 "..."
veles run --provider openai     --model gpt-4o            "..."
veles run --provider gemini     --model gemini-2.5-pro    "..."
```

## Defina um padrão para o projeto

Coloque uma base em `<project>/.veles/config.toml`:

```toml
[engine]
provider = "openrouter"                 # provider name
model = "anthropic/claude-sonnet-4.6"  # model id
```

Ou um padrão global do usuário em `~/.veles/config.toml`:

```toml
[user]
default_provider = "openrouter"
default_model = "anthropic/claude-sonnet-4.6"
```

## Forneça a chave de API

Provedores de nuvem precisam de uma chave. Guarde-a uma vez no chaveiro do SO:

```bash
veles secret set OPENROUTER_API_KEY
veles secret set ANTHROPIC_API_KEY
```

…ou exporte a [variável de ambiente](../reference/environment-variables.md):

```bash
export OPENROUTER_API_KEY=sk-or-v1-...
```

Ordem de busca: chaveiro (escopo do projeto) → chaveiro (default) → variável de
ambiente. As chaves **nunca** são gravadas em arquivos de config.

## Use um modelo totalmente local (sem chave)

Instale o [Ollama](https://ollama.com), baixe um modelo e aponte o Veles para ele:

```bash
ollama pull qwen3:4b-instruct
veles models ollama                     # confirm it's listed
veles run --provider ollama --model qwen3:4b-instruct "Hello"
```

A chamada de tools é **detectada** a partir do que o servidor anuncia. Force-a com
`VELES_LOCAL_TOOLS=1` (ou desligue-a com `=0`).

Sobrescreva os endpoints se o seu servidor não estiver na porta padrão:

```bash
export OLLAMA_BASE_URL=http://localhost:11434/v1
export LLAMACPP_BASE_URL=http://localhost:8080/v1
export OPENAI_COMPAT_BASE_URL=http://my-host:8000/v1   # required for openai-compat
```

## Adicione o seu próprio provedor

Qualquer API hospedada compatível com a OpenAI, ou um servidor que você mesmo roda,
vira um provedor com uma entrada em `~/.veles/providers.toml` — sem código. O id é o
nome da tabela:

```toml
[providers.groq]
kind = "openai-api"                          # a hosted API; needs a key
label = "Groq"                               # shown in the wizards (optional)
base_url = "https://api.groq.com/openai/v1"
key_env = ["GROQ_API_KEY"]

[providers.lmstudio]
kind = "local"                               # a server you run; a key is optional
base_url = "http://localhost:1234/v1"
```

Depois use-o como qualquer provedor nativo:

```bash
veles secret set GROQ_API_KEY      # into the keychain, where the groq entry reads it
veles models groq
veles run --provider groq --model llama-3.3-70b-versatile "..."
```

| Chave | Significado |
|---|---|
| `kind` | `openai-api` (uma API hospedada) ou `local` (um servidor que você mesmo roda) |
| `base_url` | o endpoint compatível com a OpenAI, terminando em `/v1` (ou o equivalente do provedor) |
| `base_url_env` | uma variável de ambiente que, quando definida, sobrescreve `base_url` |
| `key_env` | nomes das variáveis de ambiente de onde a chave é lida; o chaveiro é tentado primeiro |
| `label`, `tagline` | como os assistentes o exibem |
| `tools` | `auto` (padrão), `on` ou `off` — se o modelo recebe chamadas de tools |

Uma entrada com um id nativo (`[providers.ollama]`) altera as configurações desse
provedor — o seu `base_url`, por exemplo — mas não o seu tipo. Um arquivo quebrado é
reportado uma única vez, e o Veles segue com os provedores nativos; o `veles doctor`
lista o que há de errado nele.

Pontos de partida para APIs comuns — **não verificados pela equipe do Veles**, consulte
a documentação do provedor para o endpoint atual:

| id | `base_url` | `key_env` |
|---|---|---|
| `groq` | `https://api.groq.com/openai/v1` | `GROQ_API_KEY` |
| `deepseek` | `https://api.deepseek.com/v1` | `DEEPSEEK_API_KEY` |
| `mistral` | `https://api.mistral.ai/v1` | `MISTRAL_API_KEY` |
| `together` | `https://api.together.xyz/v1` | `TOGETHER_API_KEY` |
| `xai` | `https://api.x.ai/v1` | `XAI_API_KEY` |
| `fireworks` | `https://api.fireworks.ai/inference/v1` | `FIREWORKS_API_KEY` |
| `deepinfra` | `https://api.deepinfra.com/v1/openai` | `DEEPINFRA_API_KEY` |
| `nebius` | `https://api.studio.nebius.com/v1` | `NEBIUS_API_KEY` |
| `cerebras` | `https://api.cerebras.ai/v1` | `CEREBRAS_API_KEY` |
| `zai` | `https://api.z.ai/api/paas/v4` | `ZAI_API_KEY` |
| `moonshot` | `https://api.moonshot.ai/v1` | `MOONSHOT_API_KEY` |
| `lmstudio` (`local`) | `http://localhost:1234/v1` | — |
| `vllm` (`local`) | `http://localhost:8000/v1` | — |

## Delegue para uma assinatura do Claude / ChatGPT / Google

Se você tiver a CLI `claude` autenticada, o Veles pode pilotá-la:

```bash
veles run --provider claude-cli "..."
```

Para uma assinatura do ChatGPT, instale a Codex CLI e faça login uma vez (`codex login`):

```bash
veles run --provider codex --model gpt-6-luna "..."
veles models codex      # the models your account has
```

Para uma assinatura do Google, instale e faça login uma vez na Antigravity CLI (`agy`),
depois nomeie o provedor dela — o módulo `antigravity-cli` se instala sozinho a partir
dos seus registries conectados nessa execução:

```bash
veles run --provider antigravity-cli --model gemini-3.8-flash-high "..."
veles models antigravity-cli
```

Nenhuma chave de API necessária — a CLI cuida da autenticação.

## Liste os modelos disponíveis

```bash
veles models openrouter            # cloud: cached 24h
veles models openrouter --refresh  # force re-fetch
veles models ollama                # local: always live
```

## Próximo

- [Rotear diferentes tarefas para diferentes modelos](per-task-routing.md) — modelo
  barato para compressão, modelo forte para planejamento.

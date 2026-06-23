# Como configurar provedores

> 🌐 **Idiomas:** **English** · [Русский](../../ru/how-to/configure-providers.md)

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
[provider]
default = "openrouter:anthropic/claude-sonnet-4.6"
```

Ou um padrão global do usuário em `~/.veles/config.toml`:

```toml
[user]
default_provider = "openrouter"
default_model = "anthropic/claude-sonnet-4.6"
```

## Forneça a chave de API

Provedores na nuvem precisam de uma chave. Armazene-a uma vez no keychain do SO:

```bash
veles secret set OPENROUTER_API_KEY
veles secret set ANTHROPIC_API_KEY
```

…ou exporte a [variável de ambiente](../reference/environment-variables.md):

```bash
export OPENROUTER_API_KEY=sk-or-v1-...
```

Ordem de busca: keychain (escopo do projeto) → keychain (padrão) → variável de ambiente. As chaves
**nunca** são gravadas em arquivos de configuração.

## Use um modelo totalmente local (sem chave)

Instale o [Ollama](https://ollama.com), baixe um modelo e aponte o Veles para ele:

```bash
ollama pull qwen3:4b-instruct
veles models ollama                     # confirm it's listed
veles run --provider ollama --model qwen3:4b-instruct "Hello"
```

A chamada de ferramentas (tool calling) fica **desativada por padrão** em provedores locais. Ative-a quando você tiver
escolhido um modelo capaz de usar ferramentas:

```bash
export VELES_LOCAL_TOOLS=1
```

Sobrescreva os endpoints se o seu servidor não estiver na porta padrão:

```bash
export OLLAMA_BASE_URL=http://localhost:11434/v1
export LLAMACPP_BASE_URL=http://localhost:8080/v1
export OPENAI_COMPAT_BASE_URL=http://my-host:8000/v1   # required for openai-compat
```

## Delegue a uma assinatura da CLI Claude / Gemini

Se você tem a CLI `claude` ou `gemini` autenticada, o Veles pode controlá-la:

```bash
veles run --provider claude-cli "..."
veles run --provider gemini-cli "..."
```

Nenhuma chave de API é necessária — a CLI cuida da autenticação.

## Liste os modelos disponíveis

```bash
veles models openrouter            # cloud: cached 24h
veles models openrouter --refresh  # force re-fetch
veles models ollama                # local: always live
```

## A seguir

- [Roteie tarefas diferentes para modelos diferentes](per-task-routing.md) — modelo barato
  para compressão, modelo forte para planejamento.

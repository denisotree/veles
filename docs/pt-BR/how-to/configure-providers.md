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
[provider]
default = "openrouter"                 # provider name
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

A chamada de tools vem **desligada por padrão** em provedores locais. Habilite-a
depois de escolher um modelo capaz de usar tools:

```bash
export VELES_LOCAL_TOOLS=1
```

Sobrescreva os endpoints se o seu servidor não estiver na porta padrão:

```bash
export OLLAMA_BASE_URL=http://localhost:11434/v1
export LLAMACPP_BASE_URL=http://localhost:8080/v1
export OPENAI_COMPAT_BASE_URL=http://my-host:8000/v1   # required for openai-compat
```

## Delegue para uma assinatura de CLI do Claude / Gemini

Se você tiver a CLI `claude` ou `gemini` autenticada, o Veles pode pilotá-la:

```bash
veles run --provider claude-cli "..."
veles run --provider gemini-cli "..."
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

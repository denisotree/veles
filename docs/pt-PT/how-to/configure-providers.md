# Como configurar fornecedores

> 🌐 **Idiomas:** [English](../../en/how-to/configure-providers.md) · [简体中文](../../zh-CN/how-to/configure-providers.md) · [繁體中文](../../zh-TW/how-to/configure-providers.md) · [日本語](../../ja/how-to/configure-providers.md) · [한국어](../../ko/how-to/configure-providers.md) · [Español](../../es/how-to/configure-providers.md) · [Français](../../fr/how-to/configure-providers.md) · [Italiano](../../it/how-to/configure-providers.md) · [Português (BR)](../../pt-BR/how-to/configure-providers.md) · **Português (PT)** · [Русский](../../ru/how-to/configure-providers.md) · [العربية](../../ar/how-to/configure-providers.md) · [हिन्दी](../../hi/how-to/configure-providers.md) · [বাংলা](../../bn/how-to/configure-providers.md) · [Tiếng Việt](../../vi/how-to/configure-providers.md)

Alterne o Veles entre OpenRouter, Anthropic, OpenAI, Gemini, modelos locais, ou uma
subscrição de CLI. Lista completa de fornecedores: [referência de fornecedores](../reference/providers.md).

## Escolher um fornecedor por comando

```bash
veles run --provider anthropic --model claude-sonnet-4.6 "..."
veles run --provider openai     --model gpt-4o            "..."
veles run --provider gemini     --model gemini-2.5-pro    "..."
```

## Definir uma predefinição para o projecto

Coloque uma base em `<project>/.veles/config.toml`:

```toml
[engine]
provider = "openrouter"                 # provider name
model = "anthropic/claude-sonnet-4.6"  # model id
```

Ou uma predefinição global do utilizador em `~/.veles/config.toml`:

```toml
[user]
default_provider = "openrouter"
default_model = "anthropic/claude-sonnet-4.6"
```

## Fornecer a chave de API

Os fornecedores na nuvem precisam de uma chave. Guarde-a uma vez no chaveiro do SO:

```bash
veles secret set OPENROUTER_API_KEY
veles secret set ANTHROPIC_API_KEY
```

…ou exporte a [variável de ambiente](../reference/environment-variables.md):

```bash
export OPENROUTER_API_KEY=sk-or-v1-...
```

Ordem de consulta: chaveiro (âmbito do projecto) → chaveiro (default) → variável de
ambiente. As chaves **nunca** são escritas em ficheiros de configuração.

## Usar um modelo totalmente local (sem chave)

Instale o [Ollama](https://ollama.com), descarregue um modelo e aponte o Veles para ele:

```bash
ollama pull qwen3:4b-instruct
veles models ollama                     # confirm it's listed
veles run --provider ollama --model qwen3:4b-instruct "Hello"
```

A chamada a ferramentas está **desligada por predefinição** nos fornecedores locais.
Active-a assim que tiver escolhido um modelo com capacidade para ferramentas:

```bash
export VELES_LOCAL_TOOLS=1
```

Sobreponha os endpoints se o seu servidor não estiver na porta predefinida:

```bash
export OLLAMA_BASE_URL=http://localhost:11434/v1
export LLAMACPP_BASE_URL=http://localhost:8080/v1
export OPENAI_COMPAT_BASE_URL=http://my-host:8000/v1   # required for openai-compat
```

## Delegar numa subscrição de CLI do Claude / Gemini

Se tiver a CLI `claude` ou `gemini` autenticada, o Veles pode conduzi-la:

```bash
veles run --provider claude-cli "..."
veles run --provider gemini-cli "..."
```

Sem chave de API necessária — a CLI trata da autenticação.

## Listar os modelos disponíveis

```bash
veles models openrouter            # cloud: cached 24h
veles models openrouter --refresh  # force re-fetch
veles models ollama                # local: always live
```

## A seguir

- [Encaminhar tarefas diferentes para modelos diferentes](per-task-routing.md) — modelo
  barato para compressão, modelo forte para planeamento.

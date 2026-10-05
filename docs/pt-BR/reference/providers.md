# Provedores

> 🌐 **Idiomas:** [English](../../en/reference/providers.md) · [简体中文](../../zh-CN/reference/providers.md) · [繁體中文](../../zh-TW/reference/providers.md) · [日本語](../../ja/reference/providers.md) · [한국어](../../ko/reference/providers.md) · [Español](../../es/reference/providers.md) · [Français](../../fr/reference/providers.md) · [Italiano](../../it/reference/providers.md) · **Português (BR)** · [Português (PT)](../../pt-PT/reference/providers.md) · [Русский](../../ru/reference/providers.md) · [العربية](../../ar/reference/providers.md) · [हिन्दी](../../hi/reference/providers.md) · [বাংলা](../../bn/reference/providers.md) · [Tiếng Việt](../../vi/reference/providers.md)

O Veles é agnóstico em relação a provedores. Passe `--provider <id>` para
qualquer comando do agente ou defina um padrão na config. Os IDs de modelo usam a
nomenclatura própria de cada provedor.

## O catálogo de provedores

Todo provedor que o Veles conhece é uma entrada de um único catálogo, montado a partir
de três fontes:

1. **Nativos** — a tabela abaixo, distribuída com o Veles.
2. **Os seus** — `~/.veles/providers.toml`: uma API hospedada compatível com a OpenAI ou
   um servidor que você mesmo roda, adicionando uma entrada (veja
   [adicione o seu próprio provedor](../how-to/configure-providers.md#adicione-o-seu-próprio-provedor)).
   Uma entrada com um id nativo sobrescreve as configurações desse provedor (o seu
   `base_url`, por exemplo).
3. **Módulos** — um módulo do registry contribui com um provedor (`antigravity-cli`).
   Nomeá-lo em `[engine] provider`, em uma rota ou em `--provider` o instala a partir
   dos seus registries conectados na próxima execução, como um canal declarado.

`--provider`, `veles models`, os assistentes de configuração, o roteamento e o
`veles doctor` leem todos o catálogo, então um provedor de qualquer fonte funciona em
todo lugar onde um nativo funciona. Um id desconhecido é um erro de uma linha que lista
o que existe; o `veles doctor` também verifica o `~/.veles/providers.toml` e todo
provedor que as suas rotas nomeiam.

| Provedor | Tipo | Chave de API | Observações |
|---|---|---|---|
| `openrouter` | Gateway de nuvem | `OPENROUTER_API_KEY` | **Padrão.** Encaminha centenas de modelos; IDs de modelo como `anthropic/claude-sonnet-4.6` |
| `anthropic` | Nuvem direta | `ANTHROPIC_API_KEY` | Claude Messages API, prompt caching |
| `openai` | Nuvem direta | `OPENAI_API_KEY` | Chat completions da GPT |
| `gemini` | Nuvem direta | `GEMINI_API_KEY` / `GOOGLE_API_KEY` | Google Gemini |
| `claude-cli` | CLI delegada | — (sessão da CLI) | Delega a uma CLI `claude` local em modo de JSON-stream |
| `ollama` | Local | nenhuma | `OLLAMA_BASE_URL` (padrão `http://localhost:11434/v1`) |
| `llamacpp` | Local | nenhuma | `LLAMACPP_BASE_URL` (padrão `http://localhost:8080/v1`) |
| `openai-compat` | Local/customizado | `OPENAI_COMPAT_API_KEY` opcional | `OPENAI_COMPAT_BASE_URL` (obrigatório, sem padrão) |

O `gemini-cli` foi removido na 1.2.6 — o Google não oferece mais a CLI do Gemini a
contas pessoais. Use o `gemini` com uma chave de API, ou o módulo `antigravity-cli`.

Provedor padrão: `openrouter`. **Não há modelo padrão fixo no código** — defina um
pelo assistente de configuração, por `[engine] model` ou por `--model` (caso
contrário, o agente informa "no model configured"). As rotas por tarefa herdam
`[engine]` como base, a menos que sejam sobrescritas em `[routing.tasks]` — veja
[roteamento por tarefa](../how-to/per-task-routing.md).

## Provedores locais

`ollama`, `llamacpp` e `openai-compat` não precisam de chave de API. Liste os
modelos instalados com `veles models <provider>` (sempre consultado ao vivo para
provedores locais).

**A chamada de tools é detectada** a partir do que o backend anuncia: o ollama informa
as capacidades de cada modelo, um servidor llama.cpp as do seu chat template.
`VELES_LOCAL_TOOLS=1` força a chamada de tools ligada, `=0` a desliga; sem definir,
ela é detectada.

```bash
veles run --provider ollama --model qwen3:4b-instruct "..."
```

Sobrescreva os endpoints com as variáveis de ambiente `*_BASE_URL` (veja
[variáveis de ambiente](environment-variables.md)).

## Delegação para CLI (`claude-cli`, `antigravity-cli`)

Se você tiver uma assinatura do Claude ou do Google, o Veles pode rodar a CLI dela em
modo headless e atuar como coordenador — sem precisar de uma chave de API separada. O
`claude-cli` é nativo; o `antigravity-cli` (a CLI `agy`) é um módulo do registry que se
instala sozinho quando você o nomeia.

O delegado é apenas o modelo: as tools do Veles chegam até ele por uma ponte MCP, e
toda chamada passa pela escada de confiança do Veles. A config da ponte fica em um
diretório do processo em execução, `.veles/tmp/delegate-<pid>/`, removido quando ele
termina. O `agy` roda ali em um workspace temporário, não no seu projeto, atrás de um
gate que nega o shell e as tools de arquivo dele.

## Status multimodal (visão / fala-para-texto)

O Veles define um `VisionAdapter` e um protocolo de adaptador de STT
(`modules/vision.py`, `modules/stt.py`) além de um registry global de processo,
**mas nenhum adaptador concreto é distribuído e nada registra um na inicialização
do daemon**. Por isso, uma foto ou mensagem de voz enviada a um canal hoje retorna
um aviso de "não configurado" em vez de ser analisada. A tarefa de roteamento
`vision` existe para quando um adaptador for conectado. Veja
[conectar o Telegram](../how-to/connect-telegram.md#multimodal-limitation).

## Escolhendo um modelo

```bash
veles models openrouter            # cached 24h
veles models openrouter --refresh  # bypass cache
veles models ollama                # always live
```

Para usar modelos diferentes em tarefas diferentes (barato para compressão, forte
para planejamento), veja [roteamento por tarefa](../how-to/per-task-routing.md).

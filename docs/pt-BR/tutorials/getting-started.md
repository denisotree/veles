# Primeiros passos

> 🌐 **Idiomas:** [English](../../en/tutorials/getting-started.md) · [简体中文](../../zh-CN/tutorials/getting-started.md) · [繁體中文](../../zh-TW/tutorials/getting-started.md) · [日本語](../../ja/tutorials/getting-started.md) · [한국어](../../ko/tutorials/getting-started.md) · [Español](../../es/tutorials/getting-started.md) · [Français](../../fr/tutorials/getting-started.md) · [Italiano](../../it/tutorials/getting-started.md) · **Português (BR)** · [Português (PT)](../../pt-PT/tutorials/getting-started.md) · [Русский](../../ru/tutorials/getting-started.md) · [العربية](../../ar/tutorials/getting-started.md) · [हिन्दी](../../hi/tutorials/getting-started.md) · [বাংলা](../../bn/tutorials/getting-started.md) · [Tiếng Việt](../../vi/tutorials/getting-started.md)

Neste tutorial você instala o Veles, fornece uma chave de API, cria seu primeiro
projeto e executa seu primeiro prompt. Cerca de 10 minutos. Ao final, você terá um
projeto Veles funcionando com o qual pode conversar.

## Pré-requisitos

- **Python 3.13+** (o Veles requer `>=3.13`).
- Uma chave de API de LLM. Vamos usar o **OpenRouter** (o provedor padrão);
  qualquer um dos [outros provedores](../reference/providers.md) também funciona,
  incluindo os totalmente locais, sem chave.

## 1. Instalar

O Veles é instalado como um comando global `veles` via [uv](https://docs.astral.sh/uv/):

```bash
# install uv if you don't have it
curl -LsSf https://astral.sh/uv/install.sh | sh

# install veles (published as `veles-ai`; the command is `veles`)
uv tool install veles-ai
# …or from a source checkout: uv tool install .

# verify
veles --help
```

Para atualizar depois: `uv tool upgrade veles-ai`.

## 2. Forneça uma chave de API ao Veles

Pegue uma chave em [openrouter.ai](https://openrouter.ai) e exporte-a:

```bash
export OPENROUTER_API_KEY=sk-or-v1-...
```

Você também pode guardá-la no chaveiro do SO para não precisar exportá-la a cada shell:

```bash
veles secret set OPENROUTER_API_KEY
```

(Prefere uma configuração totalmente local, sem chave? Instale o
[Ollama](https://ollama.com), rode `ollama pull qwen3:4b-instruct` e use
`--provider ollama` abaixo.)

## 3. Crie seu primeiro projeto

Um projeto Veles é apenas um diretório com uma pasta de estado `.veles/`. Crie um:

```bash
mkdir my-notes && cd my-notes
veles init my-notes
```

Isso cria o `AGENTS.md` (o contexto do seu projeto), `sources/` e `wiki/` (o
[layout padrão LLM-Wiki](../explanation/layout-packs-and-llm-wiki.md)) e `.veles/`
(estado de máquina). Veja [layout do projeto](../reference/project-layout.md).

## 4. Execute seu primeiro prompt

```bash
veles run "Read AGENTS.md and describe this project in three sentences."
```

O Veles carrega o contexto do seu projeto, chama o modelo e imprime a resposta. O
turno é salvo na memória do projeto.

Adicione `--stream` para ver os tokens conforme chegam, ou `--verbose` para o
progresso por turno:

```bash
veles run --stream "What files exist in this project right now?"
```

## 5. Abra o REPL interativo

Para uma conversa de múltiplos turnos, abra a TUI:

```bash
veles tui
```

Digite uma mensagem e pressione Enter. Teclas úteis: `Ctrl+D` para sair,
`Shift+Tab` para alternar entre os [modos de execução](../explanation/modes.md),
`/help` para listar os comandos de barra. Lista completa na
[referência da TUI](../reference/tui.md).

## 6. Veja o que o Veles lembra

Toda execução é salva. Liste e pesquise suas sessões:

```bash
veles sessions list
veles sessions search "three sentences"
```

## Para onde ir em seguida

- **[Construindo uma base de conhecimento](building-a-knowledge-base.md)** — ingira
  fontes na wiki e faça perguntas sobre elas.
- **[Configurar provedores](../how-to/configure-providers.md)** — mude para
  Anthropic, OpenAI, Gemini ou um modelo totalmente local.
- **[Visão geral da arquitetura](../explanation/architecture.md)** — entenda o que
  o Veles faz por baixo dos panos.

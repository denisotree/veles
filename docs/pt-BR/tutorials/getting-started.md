# Primeiros passos

> 🌐 **Idiomas:** **English** · [Русский](../../ru/tutorials/getting-started.md)

Neste tutorial você vai instalar o Veles, fornecer uma chave de API, criar seu
primeiro projeto e executar seu primeiro prompt. Cerca de 10 minutos. Ao final
você terá um projeto Veles funcionando com o qual poderá conversar.

## Pré-requisitos

- **Python 3.13+** (o Veles requer `>=3.13`).
- Uma chave de API de LLM. Vamos usar o **OpenRouter** (o provedor padrão);
  qualquer um dos [outros provedores](../reference/providers.md) também funciona,
  incluindo os totalmente locais, que não exigem chave.

## 1. Instalação

O Veles é instalado como um comando global `veles` via [uv](https://docs.astral.sh/uv/):

```bash
# install uv if you don't have it
curl -LsSf https://astral.sh/uv/install.sh | sh

# from the Veles source directory
uv tool install .

# verify
veles --help
```

Para atualizar depois: `uv tool install . --reinstall`.

## 2. Forneça uma chave de API ao Veles

Obtenha uma chave em [openrouter.ai](https://openrouter.ai) e exporte-a:

```bash
export OPENROUTER_API_KEY=sk-or-v1-...
```

Você também pode armazená-la no keychain do sistema operacional, para não
precisar reexportá-la a cada novo shell:

```bash
veles secret set OPENROUTER_API_KEY
```

(Prefere uma configuração totalmente local, sem chave? Instale o
[Ollama](https://ollama.com), rode `ollama pull qwen3:4b-instruct` e use
`--provider ollama` mais adiante.)

## 3. Crie seu primeiro projeto

Um projeto Veles é apenas um diretório com uma pasta de estado `.veles/`. Crie um:

```bash
mkdir my-notes && cd my-notes
veles init my-notes
```

Isso cria o `AGENTS.md` (o contexto do seu projeto), `sources/` e `wiki/` (o
[layout LLM-Wiki](../explanation/layout-packs-and-llm-wiki.md) padrão) e
`.veles/` (estado de máquina). Veja [layout do projeto](../reference/project-layout.md).

## 4. Execute seu primeiro prompt

```bash
veles run "Read AGENTS.md and describe this project in three sentences."
```

O Veles carrega o contexto do seu projeto, chama o modelo e imprime a resposta. O
turno é salvo na memória do projeto.

Adicione `--stream` para ver os tokens conforme chegam, ou `--verbose` para
acompanhar o progresso de cada turno:

```bash
veles run --stream "What files exist in this project right now?"
```

## 5. Abra o REPL interativo

Para uma conversa com vários turnos, abra a TUI:

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

- **[Construindo uma base de conhecimento](building-a-knowledge-base.md)** —
  ingira fontes na wiki e faça perguntas sobre elas.
- **[Configurar provedores](../how-to/configure-providers.md)** — mude para
  Anthropic, OpenAI, Gemini ou um modelo totalmente local.
- **[Visão geral da arquitetura](../explanation/architecture.md)** — entenda o
  que o Veles faz nos bastidores.

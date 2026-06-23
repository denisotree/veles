# Primeiros passos

> 🌐 **Languages:** **English** · [Русский](../../ru/tutorials/getting-started.md)

Neste tutorial instalas o Veles, dás-lhe uma chave de API, crias o teu primeiro projeto
e corres o teu primeiro prompt. Cerca de 10 minutos. Terminarás com um projeto Veles
funcional com o qual podes conversar.

## Pré-requisitos

- **Python 3.13+** (o Veles requer `>=3.13`).
- Uma chave de API de LLM. Vamos usar o **OpenRouter** (o fornecedor predefinido); qualquer
  um dos [outros fornecedores](../reference/providers.md) também serve, incluindo os
  totalmente locais que não precisam de chave.

## 1. Instalar

O Veles instala-se como um comando `veles` global através do [uv](https://docs.astral.sh/uv/):

```bash
# install uv if you don't have it
curl -LsSf https://astral.sh/uv/install.sh | sh

# from the Veles source directory
uv tool install .

# verify
veles --help
```

Para atualizar mais tarde: `uv tool install . --reinstall`.

## 2. Dar uma chave de API ao Veles

Obtém uma chave em [openrouter.ai](https://openrouter.ai) e exporta-a:

```bash
export OPENROUTER_API_KEY=sk-or-v1-...
```

Também a podes guardar no keychain do sistema operativo para não a teres de re-exportar em
cada shell:

```bash
veles secret set OPENROUTER_API_KEY
```

(Preferes uma configuração totalmente local sem chave? Instala o [Ollama](https://ollama.com),
`ollama pull qwen3:4b-instruct`, e usa `--provider ollama` abaixo.)

## 3. Criar o teu primeiro projeto

Um projeto Veles é apenas um diretório com uma pasta de estado `.veles/`. Cria um:

```bash
mkdir my-notes && cd my-notes
veles init my-notes
```

Isto cria o `AGENTS.md` (o contexto do teu projeto), `sources/` e `wiki/` (o
[layout LLM-Wiki](../explanation/layout-packs-and-llm-wiki.md) predefinido) e
`.veles/` (estado de máquina). Consulta a [estrutura do projeto](../reference/project-layout.md).

## 4. Correr o teu primeiro prompt

```bash
veles run "Read AGENTS.md and describe this project in three sentences."
```

O Veles carrega o contexto do teu projeto, chama o modelo e imprime a resposta. O
turno é guardado na memória do projeto.

Adiciona `--stream` para ver os tokens à medida que chegam, ou `--verbose` para o progresso
por turno:

```bash
veles run --stream "What files exist in this project right now?"
```

## 5. Abrir a REPL interativa

Para uma conversa de vários turnos, abre a TUI:

```bash
veles tui
```

Escreve uma mensagem e prime Enter. Teclas úteis: `Ctrl+D` para sair, `Shift+Tab` para
percorrer os [modos de execução](../explanation/modes.md), `/help` para listar os comandos
slash. Lista completa na [referência da TUI](../reference/tui.md).

## 6. Ver o que o Veles recorda

Cada execução é guardada. Lista e pesquisa as tuas sessões:

```bash
veles sessions list
veles sessions search "three sentences"
```

## Para onde ir a seguir

- **[Construir uma base de conhecimento](building-a-knowledge-base.md)** — ingere fontes
  para a wiki e faz-lhe perguntas.
- **[Configurar fornecedores](../how-to/configure-providers.md)** — muda para
  Anthropic, OpenAI, Gemini ou um modelo totalmente local.
- **[Visão geral da arquitetura](../explanation/architecture.md)** — compreende o que o
  Veles está a fazer nos bastidores.

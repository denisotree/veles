# Primeiros passos

> 🌐 **Languages:** **English** · [Русский](../../ru/tutorials/getting-started.md)

Neste tutorial vai instalar o Veles, dar-lhe uma chave de API, criar o seu primeiro
projecto e executar o seu primeiro prompt. Cerca de 10 minutos. No fim terá um projecto
Veles funcional com o qual pode falar.

## Pré-requisitos

- **Python 3.13+** (o Veles requer `>=3.13`).
- Uma chave de API de um LLM. Vamos usar o **OpenRouter** (o fornecedor predefinido);
  qualquer um dos [outros fornecedores](../reference/providers.md) também serve, incluindo
  os totalmente locais sem chave.

## 1. Instalar

O Veles instala-se como um comando global `veles` através do [uv](https://docs.astral.sh/uv/):

```bash
# install uv if you don't have it
curl -LsSf https://astral.sh/uv/install.sh | sh

# install veles (published as `veles-ai`; the command is `veles`)
uv tool install veles-ai
# …or from a source checkout: uv tool install .

# verify
veles --help
```

Para actualizar mais tarde: `uv tool upgrade veles-ai`.

## 2. Dar ao Veles uma chave de API

Obtenha uma chave em [openrouter.ai](https://openrouter.ai) e exporte-a:

```bash
export OPENROUTER_API_KEY=sk-or-v1-...
```

Também a pode guardar no chaveiro do SO para não a reexportar em cada shell:

```bash
veles secret set OPENROUTER_API_KEY
```

(Prefere uma configuração totalmente local sem chave? Instale o [Ollama](https://ollama.com),
`ollama pull qwen3:4b-instruct`, e use `--provider ollama` em baixo.)

## 3. Criar o seu primeiro projecto

Um projecto Veles é apenas um directório com uma pasta de estado `.veles/`. Crie um:

```bash
mkdir my-notes && cd my-notes
veles init my-notes
```

Isto cria o `AGENTS.md` (o contexto do seu projecto), `sources/` e `wiki/` (o
[layout LLM-Wiki predefinido](../explanation/layout-packs-and-llm-wiki.md)), e
`.veles/` (estado de máquina). Ver [estrutura do projecto](../reference/project-layout.md).

## 4. Executar o seu primeiro prompt

```bash
veles run "Read AGENTS.md and describe this project in three sentences."
```

O Veles carrega o contexto do seu projecto, chama o modelo e imprime a resposta. O turno é
guardado na memória do projecto.

Acrescente `--stream` para ver os tokens à medida que chegam, ou `--verbose` para o
progresso por turno:

```bash
veles run --stream "What files exist in this project right now?"
```

## 5. Abrir o REPL interactivo

Para uma conversa de vários turnos, abra a TUI:

```bash
veles tui
```

Escreva uma mensagem e prima Enter. Teclas úteis: `Ctrl+D` para sair, `Shift+Tab` para
percorrer os [modos de execução](../explanation/modes.md), `/help` para listar os comandos
de barra. Lista completa na [referência da TUI](../reference/tui.md).

## 6. Ver o que o Veles recorda

Cada execução é guardada. Liste e pesquise as suas sessões:

```bash
veles sessions list
veles sessions search "three sentences"
```

## Para onde ir a seguir

- **[Construir uma base de conhecimento](building-a-knowledge-base.md)** — ingerir fontes
  na wiki e fazer perguntas sobre elas.
- **[Configurar fornecedores](../how-to/configure-providers.md)** — mudar para a
  Anthropic, OpenAI, Gemini, ou um modelo totalmente local.
- **[Visão geral da arquitectura](../explanation/architecture.md)** — perceber o que o
  Veles está a fazer nos bastidores.

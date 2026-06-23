# Atalhos de teclado e comandos slash da TUI

> 🌐 **Idiomas:** [English](../../en/reference/tui.md) · [简体中文](../../zh-CN/reference/tui.md) · [繁體中文](../../zh-TW/reference/tui.md) · [日本語](../../ja/reference/tui.md) · [한국어](../../ko/reference/tui.md) · [Español](../../es/reference/tui.md) · [Français](../../fr/reference/tui.md) · [Italiano](../../it/reference/tui.md) · [Português (BR)](../../pt-BR/reference/tui.md) · **Português (PT)** · [Русский](../../ru/reference/tui.md) · [العربية](../../ar/reference/tui.md) · [हिन्दी](../../hi/reference/tui.md) · [বাংলা](../../bn/reference/tui.md) · [Tiếng Việt](../../vi/reference/tui.md)

`veles tui` (ou simplesmente `veles`) abre a REPL interativa. É um chat com scrollback
com um composer multilinha, uma barra de estado e um inspetor recolhível.

## Atalhos de teclado

| Tecla | Ação |
|---|---|
| `Ctrl+D` | Sair |
| `Ctrl+C` | Copiar a última resposta do assistente; prime duas vezes em 1,5 s para sair |
| `Ctrl+V` | Colar a partir da área de transferência |
| `Ctrl+Shift+C` / `⌘C` | Copiar a seleção atual (OSC52). No Terminal.app do macOS, a seleção nativa por arrasto + ⌘C funciona diretamente |
| `Ctrl+I` | Alternar o inspetor (raciocínio, atividade de ferramentas, registo de tokens/erros) |
| `Ctrl+R` | Abrir o seletor de sessões (retomar uma sessão anterior) |
| `Ctrl+T` | Abrir o seletor de temas |
| `Shift+Tab` | Percorrer os modos de execução: `auto → planning → writing → goal` |
| `Tab` | Percorrer as sugestões de comandos slash |
| `Up` / `Down` | Histórico (e desempilhar prompts em fila) |

Os modos de execução são explicados em [Modos de execução](../explanation/modes.md).

## Comandos slash

Escreve `/` no composer; o `Tab` completa. Os comandos registados são:

| Comando | Função |
|---|---|
| `/help` | Listar os comandos disponíveis |
| `/quit`, `/q`, `/exit` | Sair da REPL |
| `/clear` | Limpar o registo do chat |
| `/model` | Abrir o seletor de modelos |
| `/mode` | Mudar o modo de execução (auto/planning/writing/goal) |
| `/session` | Abrir o seletor de sessões (retomar) |
| `/save` | Guardar / nomear a sessão atual |
| `/history` | Mostrar o histórico de sessões |
| `/tokens` | Uso de tokens (entrada / saída / por turno / por sessão) |
| `/context` | Tamanho atual do contexto vs o limite |
| `/status` | Instantâneo: modelo, fornecedor, modo, sessão, ocupado, fila |
| `/insights` | Mostrar os insights aprendidos do projeto |
| `/rules` | Mostrar o resumo das regras do projeto |
| `/schema` | Validar / corrigir o `AGENTS.md` |
| `/wiki` | Operações de wiki para o layout ativo |
| `/daemon` | Abrir o painel de controlo do daemon (projeto → daemons → canais) |

> O conjunto de comandos slash é o mesmo quer lances a TUI diretamente quer a chames a
> partir de outro ecrã. Os canais (p. ex. o Telegram) expõem o seu próprio conjunto de
> comandos, separado.

## Temas

Temas integrados: `everforest` (predefinição), `dracula`, `gruvbox`, `tokyo-night`,
`catppuccin`. Escolhe um com `Ctrl+T`, `veles tui --theme <name>`, ou
`[user] tui_theme` em `~/.veles/config.toml`.

# Atalhos de teclado e comandos de barra da TUI

> 🌐 **Idiomas:** [English](../../en/reference/tui.md) · [简体中文](../../zh-CN/reference/tui.md) · [繁體中文](../../zh-TW/reference/tui.md) · [日本語](../../ja/reference/tui.md) · [한국어](../../ko/reference/tui.md) · [Español](../../es/reference/tui.md) · [Français](../../fr/reference/tui.md) · [Italiano](../../it/reference/tui.md) · **Português (BR)** · [Português (PT)](../../pt-PT/reference/tui.md) · [Русский](../../ru/reference/tui.md) · [العربية](../../ar/reference/tui.md) · [हिन्दी](../../hi/reference/tui.md) · [বাংলা](../../bn/reference/tui.md) · [Tiếng Việt](../../vi/reference/tui.md)

`veles tui` (ou `veles` puro) abre o REPL interativo. É um chat com scrollback,
um compositor de várias linhas, uma barra de status e um inspetor recolhível.

## Atalhos de teclado

| Tecla | Ação |
|---|---|
| `Ctrl+D` | Sair |
| `Ctrl+C` | Copia a última resposta do assistente; pressione duas vezes em 1,5 s para sair |
| `Ctrl+V` | Cola da área de transferência |
| `Ctrl+Shift+C` / `⌘C` | Copia a seleção atual (OSC52). No Terminal.app do macOS, a seleção nativa por arraste + ⌘C funciona diretamente |
| `Ctrl+I` | Alterna o inspetor (raciocínio, atividade de ferramentas, log de tokens/erros) |
| `Ctrl+R` | Abre a seletora de sessões (retomar uma sessão anterior) |
| `Ctrl+T` | Abre a seletora de temas |
| `Shift+Tab` | Cicla o modo de execução: `auto → planning → writing → goal` |
| `Tab` | Cicla as sugestões de completar comandos de barra |
| `Up` / `Down` | Histórico (e desempilha prompts na fila) |

Os modos de execução são explicados em [Modos de execução](../explanation/modes.md).

## Comandos de barra

Digite `/` no compositor; `Tab` completa. Os comandos registrados são:

| Comando | Finalidade |
|---|---|
| `/help` | Lista os comandos disponíveis |
| `/quit`, `/q`, `/exit` | Sai do REPL |
| `/clear` | Limpa o log do chat |
| `/model` | Abre a seletora de modelos |
| `/mode` | Alterna o modo de execução (auto/planning/writing/goal) |
| `/session` | Abre a seletora de sessões (retomar) |
| `/save` | Salva / nomeia a sessão atual |
| `/history` | Mostra o histórico da sessão |
| `/tokens` | Uso de tokens (entrada / saída / por turno / por sessão) |
| `/context` | Tamanho atual do contexto vs. o limite |
| `/status` | Snapshot: modelo, provedor, modo, sessão, ocupado, fila |
| `/insights` | Mostra os insights aprendidos do projeto |
| `/rules` | Mostra o resumo de regras do projeto |
| `/schema` | Valida / corrige o `AGENTS.md` |
| `/wiki` | Operações de wiki para o layout ativo |
| `/daemon` | Abre o painel de controle do daemon (projeto → daemons → canais) |

> O conjunto de comandos de barra é o mesmo quer você inicie a TUI diretamente, quer a abra a partir de
> outra tela. Os canais (ex.: Telegram) expõem o próprio conjunto de comandos, separado.

## Temas

Temas embutidos: `everforest` (padrão), `dracula`, `gruvbox`, `tokyo-night`,
`catppuccin`. Escolha um com `Ctrl+T`, `veles tui --theme <name>` ou
`[user] tui_theme` em `~/.veles/config.toml`.

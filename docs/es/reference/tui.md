# Atajos de teclado y comandos de barra de la TUI

> 🌐 **Languages:** **English** · [Русский](../../ru/reference/tui.md)

`veles tui` (o simplemente `veles`) abre el REPL interactivo. Es un chat con
desplazamiento, un compositor multilínea, una barra de estado y un inspector
plegable.

## Atajos de teclado

| Tecla | Acción |
|---|---|
| `Ctrl+D` | Salir |
| `Ctrl+C` | Copiar la última respuesta del asistente; púlsalo dos veces en 1,5 s para salir |
| `Ctrl+V` | Pegar desde el portapapeles |
| `Ctrl+Shift+C` / `⌘C` | Copiar la selección actual (OSC52). En Terminal.app de macOS, la selección nativa por arrastre + ⌘C funciona directamente |
| `Ctrl+I` | Alternar el inspector (razonamiento, actividad de herramientas, registro de tokens/errores) |
| `Ctrl+R` | Abrir el selector de sesiones (reanudar una sesión anterior) |
| `Ctrl+T` | Abrir el selector de temas |
| `Shift+Tab` | Rotar el modo de ejecución: `auto → planning → writing → goal` |
| `Tab` | Rotar las sugerencias de autocompletado de comandos de barra |
| `Up` / `Down` | Historial (y extrae prompts en cola) |

Los modos de ejecución se explican en [Run modes](../explanation/modes.md).

## Comandos de barra

Escribe `/` en el compositor; `Tab` completa. Los comandos registrados son:

| Comando | Propósito |
|---|---|
| `/help` | Listar los comandos disponibles |
| `/quit`, `/q`, `/exit` | Salir del REPL |
| `/clear` | Limpiar el registro del chat |
| `/model` | Abrir el selector de modelos |
| `/mode` | Cambiar el modo de ejecución (auto/planning/writing/goal) |
| `/session` | Abrir el selector de sesiones (reanudar) |
| `/save` | Guardar / nombrar la sesión actual |
| `/history` | Mostrar el historial de sesiones |
| `/tokens` | Uso de tokens (entrada / salida / por turno / por sesión) |
| `/context` | Tamaño del contexto actual frente al límite |
| `/status` | Instantánea: modelo, proveedor, modo, sesión, ocupado, cola |
| `/insights` | Mostrar los insights aprendidos del proyecto |
| `/rules` | Mostrar el resumen de reglas del proyecto |
| `/schema` | Validar / corregir `AGENTS.md` |
| `/wiki` | Operaciones de wiki para el layout activo |
| `/daemon` | Abrir el panel de control del daemon (proyecto → daemons → canales) |

> El conjunto de comandos de barra es el mismo tanto si lanzas la TUI directamente
> como si la abres desde otra pantalla. Los canales (p. ej. Telegram) exponen su
> propio conjunto de comandos, distinto.

## Temas

Temas integrados: `everforest` (por defecto), `dracula`, `gruvbox`, `tokyo-night`,
`catppuccin`. Elige uno con `Ctrl+T`, `veles tui --theme <name>`, o
`[user] tui_theme` en `~/.veles/config.toml`.

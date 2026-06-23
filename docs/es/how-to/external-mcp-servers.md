# Cómo conectar servidores MCP externos

> 🌐 **Languages:** **English** · [Русский](../../ru/how-to/external-mcp-servers.md)

Veles es un **cliente** [MCP](https://modelcontextprotocol.io/): puede conectarse a
servidores MCP externos y exponer sus herramientas al agente como si fueran
integradas (GitHub, documentación de librerías, búsqueda web, tus propios
servicios, …).

## Configurar un servidor

Añade un bloque `[mcp.servers.<name>]` a `<project>/.veles/config.toml` (o al
`~/.veles/config.toml` global del usuario). El `<name>` debe cumplir
`[A-Za-z0-9][A-Za-z0-9_-]{0,31}` — pasa a formar parte del nombre de cada
herramienta. Se admiten tres transportes: `stdio` (por defecto), `http`, `sse`.

| Clave | Transporte | Por defecto | Propósito |
|---|---|---|---|
| `transport` | — | `"stdio"` | `stdio` \| `http` \| `sse` |
| `command` | stdio (obligatorio) | — | el ejecutable a lanzar — **solo el programa, no sus argumentos** |
| `args` | stdio | `[]` | lista de argumentos, un token por elemento |
| `env` | stdio | `{}` | entorno adicional para el subproceso (fusionado sobre el entorno heredado) |
| `url` | http/sse (obligatorio) | — | el endpoint del servidor |
| `timeout_s` | — | `120` | presupuesto para una sola llamada a herramienta |
| `connect_timeout_s` | — | `30` | presupuesto para la conexión inicial |
| `enabled` | — | `true` | ponlo a `false` para conservar la entrada pero omitir la conexión |

Los valores de cadena en `command`, `args`, `env` y `url` interpolan `${VAR}` desde
el entorno (una variable no definida se convierte en una cadena vacía con una
advertencia) — mantén los secretos fuera del archivo.

> **`command` frente a `args`.** Veles ejecuta el programa directamente (sin shell),
> así que el ejecutable y sus argumentos son campos **separados**. Escribe
> `command = "npx"`, `args = ["-y", "pkg"]` — **no** `command = "npx -y pkg"`.

### stdio (subproceso local)

```toml
[mcp.servers.github]
transport = "stdio"
command = "npx"
args = ["-y", "@modelcontextprotocol/server-github"]
env = { GITHUB_TOKEN = "${GITHUB_TOKEN}" }
```

Un servidor que ejecutes tú mismo funciona igual — apunta `command`/`args` a él:

```toml
[mcp.servers.mytools]
transport = "stdio"
command = "python"
args = ["-m", "my_mcp_server"]
```

### Un servidor que necesita una clave de API (context7)

[Context7](https://context7.com) ofrece documentación de librerías al día. Pasa la
clave como argumento para que `${VAR}` la mantenga fuera del archivo:

```toml
[mcp.servers.context7]
transport = "stdio"
command = "npx"
args = ["-y", "@upstash/context7-mcp", "--api-key", "${CONTEXT7_API_KEY}"]
```

```bash
export CONTEXT7_API_KEY=...   # then start veles
```

### http / sse (remoto)

```toml
[mcp.servers.search]
transport = "http"            # streamable HTTP; use "sse" for an SSE endpoint
url = "https://mcp.example.com/mcp"
```

> **Aún no hay cabeceras personalizadas.** Los transportes `http`/`sse` envían solo
> la `url` — Veles no puede adjuntar una cabecera `Authorization`. Para un servidor
> remoto que necesita una clave, prefiere su variante `stdio` (p. ej. `npx`) con la
> clave en `args`/`env`, o un endpoint que acepte la clave en la URL.

## Ocultar herramientas concretas

Define `[mcp] disabled_tools` — una tabla que asigna a cada servidor los nombres de
las herramientas a omitir:

```toml
[mcp]
disabled_tools = { github = ["delete_repository"], search = ["raw_query"] }
```

## Inspeccionar y probar

```bash
veles mcp list              # every configured server: transport, status, tool count
veles mcp test github       # connect to one server and list its tools
```

`veles mcp list` siempre termina con código 0 — es un inspector, no una verificación
de estado. `veles mcp test` termina con código 1 cuando la conexión falla y con 2
ante un nombre de servidor desconocido.

## Cómo aparecen las herramientas

Una vez configurados, los servidores se montan **automáticamente** en el siguiente
`veles run` / inicio de la TUI / arranque del daemon — no hay un flag aparte para
"habilitar MCP": la presencia de la configuración es el interruptor. Cada
herramienta entra en el registro normal como `mcp_<server>_<tool>` y el agente puede
invocarla como cualquier herramienta integrada. Los esquemas se sanean (límites de
nombre/longitud, eliminación de caracteres de control) para que un servidor no
fiable no pueda inyectar contenido en el prompt. Las pistas de las herramientas se
asignan a la escala de confianza: las herramientas destructivas siempre piden
confirmación, las de solo lectura no preguntan, y todo lo demás pasa por el flujo de
[confianza](security-and-permissions.md) habitual — concede una aprobación
permanente con `veles trust set` si no quieres que te pregunten cada vez.

## Gestión de fallos

Un servidor que no logra conectarse — un `command` ausente, una `url` incorrecta o
cualquier entrada inválida — se registra como advertencia y se omite. Nunca bloquea
el arranque ni al agente. Vuelve a ejecutar `veles mcp list` para ver el estado y el
error.

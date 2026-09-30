# Cómo gestionar la seguridad: confianza, autopilot, secretos

> 🌐 **Idiomas:** [English](../../en/how-to/security-and-permissions.md) · [简体中文](../../zh-CN/how-to/security-and-permissions.md) · [繁體中文](../../zh-TW/how-to/security-and-permissions.md) · [日本語](../../ja/how-to/security-and-permissions.md) · [한국어](../../ko/how-to/security-and-permissions.md) · **Español** · [Français](../../fr/how-to/security-and-permissions.md) · [Italiano](../../it/how-to/security-and-permissions.md) · [Português (BR)](../../pt-BR/how-to/security-and-permissions.md) · [Português (PT)](../../pt-PT/how-to/security-and-permissions.md) · [Русский](../../ru/how-to/security-and-permissions.md) · [العربية](../../ar/how-to/security-and-permissions.md) · [हिन्दी](../../hi/how-to/security-and-permissions.md) · [বাংলা](../../bn/how-to/security-and-permissions.md) · [Tiếng Việt](../../vi/how-to/security-and-permissions.md)

Veles restringe las acciones peligrosas mediante una **escalera de confianza**,
aísla el acceso a archivos en un sandbox y guarda los secretos en el llavero del
sistema operativo. Para conocer la justificación, consulta
[confianza y el sandbox](../explanation/trust-and-sandbox.md).

## La escalera de confianza

Las herramientas sensibles (`run_shell`, `write_file`, `fetch_url`, …) piden
confirmación antes de ejecutarse. Tú eliges: permitir **una vez**, **siempre para
este proyecto**, **siempre en todas partes** o **rechazar**. Las concesiones
persisten para que no te lo vuelvan a preguntar.

Gestiona las concesiones sin esperar a una solicitud:

```bash
veles trust list                          # concesiones actuales (usuario + proyecto)
veles trust set run_shell --scope project # conceder previamente para este proyecto
veles trust set write_file --scope user   # conceder previamente en todas partes
veles trust revoke run_shell              # quitar una concesión
veles trust clear --scope all             # borrar todo
```

Algunas acciones **siempre se confirman**, incluso con una concesión: borrar
archivos, descargar URLs, instalar una nueva skill/herramienta/módulo, conectar un
canal y escribir fuera del proyecto.

## Autopilot — una omisión con límite de tiempo

Para una ejecución desatendida (un lote nocturno), abre una ventana en la que las
solicitudes de confianza se autoaprueban:

```bash
veles autopilot enable --until +2h
veles autopilot enable --until 2026-12-31T23:00:00Z
veles autopilot status
veles autopilot disable
```

Cada acción del autopilot queda registrada para su posterior revisión. Los
contextos no interactivos (daemon, lote) rechazan por defecto a menos que el
autopilot esté activo.

## Secretos

Las claves de API y los tokens de bots viven en el llavero del sistema operativo,
nunca en archivos de configuración:

```bash
veles secret set OPENROUTER_API_KEY       # pide el valor (o pásalo por stdin)
veles secret list                         # qué secretos están configurados
veles secret get OPENROUTER_API_KEY --reveal
veles secret delete OPENROUTER_API_KEY
veles secret set OPENROUTER_API_KEY --project myproj   # una clave solo para un proyecto
```

La búsqueda recurre a la [variable de entorno](../reference/environment-variables.md)
correspondiente a menos que pases `--no-env-fallback`.

## El sandbox

Las herramientas pueden leer dentro del proyecto activo, `~/.veles/skills/` y
`~/.veles/locales/`, y escribir solo dentro del proyecto — o solo en las zonas
escribibles del layout, cuando este las declara. Sobrescribe las raíces para
configuraciones avanzadas con `VELES_SANDBOX_ROOTS` (separadas por `:`). Las
descargas de URL mantienen una lista de denegación contra SSRF;
`VELES_FETCH_ALLOW_PRIVATE=1` elimina el bloqueo de redes privadas.

Dentro del `.veles/` del proyecto, las herramientas de archivos del agente solo pueden
escribir en `skills/`, `tools/`, `tmp/`, `plans/`, `memory/` y `artifacts/`. Todo lo
demás — `trust.json`, `config.toml`, `project.toml`, `modules/`, `wiki.toml`,
`memory.db` — cambia solo mediante comandos `veles` y las herramientas propias de
Veles. Las herramientas de archivos también rechazan cualquier otro directorio
`.veles/` del proyecto (el de un subproyecto, o uno que el agente plantaría en
`wiki/`) a cualquier profundidad. Así, con sus herramientas de archivos el agente no
puede concederse confianza a sí mismo ni añadir código que Veles ejecutaría (una
herramienta que escriba en `.veles/tools/` se carga solo después de que apruebes su
archivo). Otras formas de escribir el mismo archivo (mayúsculas/minúsculas, `..`, un
symlink) también se rechazan.

Los archivos que se ejecutan sin un comando explícito o que dirigen a una CLI de agente
— todo lo que esté bajo `.git/`, `.githooks/`, `.claude/`, `.gemini/`, `.codex/`,
`.vscode/`, `.devcontainer/`, `.husky/`, y `.envrc`, `.mcp.json`,
`.pre-commit-config.yaml`, `lefthook.yml`, a cualquier profundidad, además del
directorio `core.hooksPath` del repositorio y el destino de un `.git` que sea un
symlink — las herramientas de archivos del agente los escriben solo después de que
confirmes esa escritura. Las concesiones de confianza y el autopilot no la cubren; el
daemon pregunta en el canal, y una ejecución por lotes sin nadie a quien preguntar la
rechaza.

Los proveedores `claude-cli` y `gemini-cli` se ejecutan como un modelo con las
herramientas de Veles únicamente: sus propias herramientas de shell, edición de
archivos y web, los ajustes y hooks de `.claude/` del proyecto y otros servidores MCP
no se aplican, y toda herramienta de Veles que llamen pasa por la escalera de
confianza anterior (nadie puede responder a una pregunta ahí, así que todo lo que no
esté ya concedido se rechaza).

Límites conocidos:

- `run_shell` es un shell: una vez que lo concedes (o bajo autopilot) puede escribir
  cualquiera de los archivos anteriores sin la confirmación por archivo.
- Una aprobación de MCP fija la línea de comandos del servidor, no los archivos que
  ejecuta desde el proyecto (un script indicado en `args`) — revísalos también.
- Con un proveedor CLI, las ejecuciones que preautorizan herramientas solo para sí
  mismas (tareas en segundo plano del daemon, `veles research`) no se lo transmiten a
  la CLI delegada: sus herramientas de Veles necesitan una concesión permanente con
  `veles trust set` o una ventana de autopilot. El modo de planificación de la
  ejecución padre tampoco les llega.
- `gemini-cli` confía en la carpeta del proyecto durante su ejecución, así que gemini
  también lee el `.env` del proyecto — mantén fuera de él los ajustes de gemini que no
  quieras que el agente dirija.
- En una máquina con políticas de gemini gestionadas (del sistema), gemini ignora la
  política que le pasa Veles, así que allí `gemini-cli` no se limita a las
  herramientas de Veles.

Las rutas con caracteres de control (secuencias de escape de terminal, sobrescrituras
bidi) se rechazan, y las confirmaciones, el aviso de confianza y la vista previa del
diff muestran esos caracteres escapados — una llamada a una herramienta no puede
falsificar el texto que apruebas.

Los servidores MCP de una configuración se inician solo después de que los apruebes —
consulta [servidores MCP externos](external-mcp-servers.md#aprobar-inspeccionar-y-probar).

# Confianza y el sandbox

> 🌐 **Languages:** **English** · [Русский](../../ru/explanation/trust-and-sandbox.md)

Veles ejecuta un agente autónomo en tu máquina, así que limita lo que ese agente
puede hacer. Dos mecanismos trabajan juntos: una **escala de confianza** para las
acciones sensibles y un **sandbox** para el sistema de archivos. Para los comandos,
consulta [seguridad y permisos](../how-to/security-and-permissions.md).

## La escala de confianza

No todas las herramientas son iguales. Leer un archivo es inofensivo; ejecutar un
comando de shell o escribir en disco no lo es. Las herramientas sensibles
(`run_shell`, `write_file`, `fetch_url`, …) se detienen y preguntan antes de
ejecutarse, ofreciendo cuatro opciones:

- **Una vez** — permitir esta única llamada.
- **Siempre para este proyecto** — persistir una concesión con alcance de proyecto.
- **Siempre en todas partes** — persistir una concesión con alcance de usuario.
- **Rechazar** — denegarla.

Las concesiones se almacenan para que no se te vuelva a preguntar. Esto te da un
control graduado: confía en una herramienta una vez, en un proyecto o globalmente —
tu elección, hecha la primera vez que importa.

### Acciones de confirmación obligatoria

Algunas operaciones son lo bastante arriesgadas como para que Veles las confirme
**incluso con una concesión**: borrar archivos, obtener URLs, instalar un nuevo
skill/herramienta/módulo, conectar un canal y escribir fuera del proyecto. Son
acciones de cara al exterior o difíciles de revertir, así que una concesión
permanente no debería cubrirlas en silencio.

### Seguridad no interactiva

En un daemon, en modo batch u otro contexto sin TTY no hay un humano al que
preguntar, así que Veles **rechaza** las acciones sensibles por defecto: un stdin
errante no puede colar una aprobación. Para ejecutar sin supervisión a propósito,
abre una ventana de [autopilot](../how-to/security-and-permissions.md#autopilot--a-time-boxed-bypass);
cada acción de autopilot se registra para su revisión.

## El sandbox del sistema de archivos

Un guardián de rutas acota dónde pueden leer y escribir las herramientas:

- **Lectura** — dentro del proyecto activo (y sus subproyectos) más `~/.veles/`.
- **Escritura** — solo las zonas escribibles del layout (p. ej. `wiki/`); `.veles/`
  siempre es escribible para el estado de la máquina.

Los enlaces simbólicos que escapan del sandbox se rechazan, y el recorrido `..` se
deniega antes de la resolución. Las obtenciones de URL mantienen una lista de
denegación SSRF. Las configuraciones avanzadas pueden anular las raíces con
`VELES_SANDBOX_ROOTS`, o levantar el bloqueo de red privada con
`VELES_FETCH_ALLOW_PRIVATE=1` — ambas de activación explícita.

## Por qué este diseño

El objetivo es **autonomía útil sin sorpresas desagradables**: el agente puede hacer
trabajo real sin un aviso en cada lectura, pero cualquier cosa que pueda dañar tu
máquina, gastar dinero o salir de la caja queda controlada — una vez, y luego
recordada según tu gusto.

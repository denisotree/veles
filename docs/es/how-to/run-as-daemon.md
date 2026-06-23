# Cómo ejecutar Veles como daemon

> 🌐 **Languages:** **English** · [Русский](../../ru/how-to/run-as-daemon.md)

El daemon es un servidor HTTP+WS opcional y de larga duración que expone el agente
como una API: la base para los [canales](connect-telegram.md) (Telegram, …), los
[trabajos](long-running-tasks.md) programados y el uso remoto/sin interfaz.

## Iniciar y detener

```bash
veles daemon start              # se desacopla por defecto; escucha en 127.0.0.1:8765
veles daemon status             # ¿está en ejecución?
veles daemon stop               # SIGTERM mediante el archivo pid
```

`start` se desacopla y te devuelve la terminal. Para un proceso en primer plano
(systemd `Type=simple`, Docker, depuración) pasa `--foreground`. Sobrescribe la
dirección de escucha:

```bash
veles daemon start --host 0.0.0.0 --port 9000
```

El modelo y el proveedor del daemon provienen de la configuración del proyecto y
son **fijos durante toda su vida**: configúralos antes de iniciar:

```toml
# <project>/.veles/config.toml
[provider]
default = "ollama:qwen3:4b-instruct"
```

## Tokens de autenticación

Los clientes de la API se autentican con un token de portador (bearer):

```bash
veles daemon token add tui-client     # genera un token
veles daemon token list               # lista (enmascarado)
veles daemon token remove tui-client
```

## El selector de daemons (TUI)

Ejecuta `veles daemon` sin subcomando para abrir el panel de control: un árbol con
los daemons de tu proyecto y los canales de cada daemon:

```
Project: my-project
  default   running  pid=…  up 1.2h  qwen3:4b-instruct
    chan: telegram
  api       stopped
Other projects
  other-proj  running
```

Teclas: `Enter` abre el log de un daemon; `s`/`t`/`r` iniciar/detener/reiniciar;
`d` eliminar; `c`/`x` añadir/quitar un canal; `q` salir.

## Varios daemons por proyecto (sesiones con nombre)

Un proyecto puede ejecutar varios daemons con distintos modelos/puertos a la vez.
Declara una sesión con nombre y luego iníciala:

```bash
veles daemon session create api --port 8801 --provider anthropic --model claude-opus-4.8
veles daemon start --name api
veles daemon session list
```

Cada sesión con nombre tiene su propio bloque de configuración `[daemon.<name>]` y
sus propios canales (`[daemon.<name>.channels.*]`).

## Listar daemons en todos los proyectos

```bash
veles daemon list
veles daemon restart <project-or-slug>
veles daemon delete  <project-or-slug>
```

## Siguiente

- [Conectar un canal de Telegram](connect-telegram.md)
- [Programar trabajos](long-running-tasks.md)

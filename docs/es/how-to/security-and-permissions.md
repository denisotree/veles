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
```

La búsqueda recurre a la [variable de entorno](../reference/environment-variables.md)
correspondiente a menos que pases `--no-env-fallback`.

## El sandbox

Las herramientas pueden leer dentro del proyecto activo y de `~/.veles/`, y
escribir solo en las zonas escribibles del layout (`wiki/`, `.veles/` por
defecto). Sobrescribe las raíces para configuraciones avanzadas con
`VELES_SANDBOX_ROOTS` (separadas por `:`). Las descargas de URL mantienen una
lista de denegación contra SSRF; `VELES_FETCH_ALLOW_PRIVATE=1` elimina el bloqueo
de redes privadas.

# Paquetes de layout y la LLM-Wiki

> 🌐 **Idiomas:** [English](../../en/explanation/layout-packs-and-llm-wiki.md) · [简体中文](../../zh-CN/explanation/layout-packs-and-llm-wiki.md) · [繁體中文](../../zh-TW/explanation/layout-packs-and-llm-wiki.md) · [日本語](../../ja/explanation/layout-packs-and-llm-wiki.md) · [한국어](../../ko/explanation/layout-packs-and-llm-wiki.md) · **Español** · [Français](../../fr/explanation/layout-packs-and-llm-wiki.md) · [Italiano](../../it/explanation/layout-packs-and-llm-wiki.md) · [Português (BR)](../../pt-BR/explanation/layout-packs-and-llm-wiki.md) · [Português (PT)](../../pt-PT/explanation/layout-packs-and-llm-wiki.md) · [Русский](../../ru/explanation/layout-packs-and-llm-wiki.md) · [العربية](../../ar/explanation/layout-packs-and-llm-wiki.md) · [हिन्दी](../../hi/explanation/layout-packs-and-llm-wiki.md) · [বাংলা](../../bn/explanation/layout-packs-and-llm-wiki.md) · [Tiếng Việt](../../vi/explanation/layout-packs-and-llm-wiki.md)

Un **paquete de layout** define cómo se organiza el *contenido de usuario* de un
proyecto: qué directorios existen, en cuáles puede escribir el agente y qué
operaciones ofrece. El predeterminado es la **LLM-Wiki**. Esto es una opción de
contenido, **no** un principio central de Veles.

## Qué es un paquete de layout

Un paquete de layout es un directorio con un manifiesto `layout.toml` (más archivos
opcionales de skills y plantillas). El manifiesto declara:

- **Zonas escribibles** — directorios en los que el agente puede escribir contenido
  (se aplica en cada `write_file`).
- **Zonas de solo lectura** — material que el agente lee pero nunca modifica.
- **Operaciones** — flujos de trabajo con nombre, distribuidos como skills dentro
  del paquete.
- **Scaffold** (`[layout.scaffold]`) — lo que crea `veles init`: directorios y una
  plantilla opcional de `AGENTS.md` (se sustituye `{name}`).
- **Engines** (`[layout.engines]`) — qué maquinaria de contenido del núcleo activa
  el paquete. Hoy hay un único engine: `wiki`. Sin él, en el proyecto no existen
  herramientas de wiki, ni recall de wiki, ni inyección de INDEX.
- **Archivo de contexto** (`context_file`) — un archivo que se inyecta en el prompt
  de sistema estable del agente (la LLM-Wiki usa `INDEX.md`).

## Paquetes integrados

| Paquete | Qué produce `veles init --layout <name>` |
|---|---|
| `llm-wiki` *(predeterminado)* | La [LLM-Wiki al estilo de Karpathy](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f): `sources/` (solo lectura), `wiki/` (escribible por el agente), `INDEX.md` inyectado en el prompt, los skills `ingest`/`query`/`lint`, y el engine de wiki activado. |
| `notes` | Un único directorio plano `notes/` en el que escribe el agente. Sin maquinaria de wiki. |
| `bare` | Sin scaffold de contenido alguno — para repositorios de código y trabajo de forma libre. Las escrituras son permisivas dentro de la raíz del proyecto (sujetas igualmente a la escala de confianza). |

## Layouts personalizados

Coloca un paquete en `~/.veles/layouts/<name>/layout.toml` (global del usuario) o
en `<project>/.veles/layouts/<name>/` (local del proyecto; oculta los paquetes del
usuario e integrados con el mismo nombre) y pasa `veles init --layout <name>`. El
integrado `notes` es el ejemplo mínimo a copiar. También puedes describir
convenciones en `AGENTS.md`: el layout aplica las zonas, AGENTS.md guía el
comportamiento.

## Qué *no* es

El layout gobierna **únicamente tu contenido**. La propia memoria de proyecto de
Veles —`memory.db` más el árbol de artefactos `.veles/memory/` (insights, resúmenes
de sesión, propuestas, el diario de operaciones del sistema)— es del lado del
sistema y funciona de forma idéntica bajo cualquier layout. Cambiar de layout nunca
toca el bucle de aprendizaje, las sesiones ni los registros. Consulta
[arquitectura](architecture.md) y [estructura del proyecto](../reference/project-layout.md).

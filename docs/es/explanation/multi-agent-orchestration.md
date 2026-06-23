# Orquestación multi-agente

> 🌐 **Idiomas:** [English](../../en/explanation/multi-agent-orchestration.md) · [简体中文](../../zh-CN/explanation/multi-agent-orchestration.md) · [繁體中文](../../zh-TW/explanation/multi-agent-orchestration.md) · [日本語](../../ja/explanation/multi-agent-orchestration.md) · [한국어](../../ko/explanation/multi-agent-orchestration.md) · **Español** · [Français](../../fr/explanation/multi-agent-orchestration.md) · [Italiano](../../it/explanation/multi-agent-orchestration.md) · [Português (BR)](../../pt-BR/explanation/multi-agent-orchestration.md) · [Português (PT)](../../pt-PT/explanation/multi-agent-orchestration.md) · [Русский](../../ru/explanation/multi-agent-orchestration.md) · [العربية](../../ar/explanation/multi-agent-orchestration.md) · [हिन्दी](../../hi/explanation/multi-agent-orchestration.md) · [বাংলা](../../bn/explanation/multi-agent-orchestration.md) · [Tiếng Việt](../../vi/explanation/multi-agent-orchestration.md)

Para trabajos complejos, Veles puede repartir una tarea entre un **manager** y
sub-agentes **worker** especializados en lugar de hacerlo todo en un solo contexto.
Esta página explica el modelo; para activarlo, consulta
[modo manager](../how-to/long-running-tasks.md#manager-mode--decompose-any-prompt).

## La forma

```
            manager  (decomposes the task, never writes the final answer)
           /    |    \
    explorer  writer  advisor   (specialised workers, run in parallel)
```

- El **manager** planifica la descomposición y coordina, pero **no** escribe él
  mismo el entregable final.
- Los **workers** tienen prompts de sistema específicos por rol: `explorer`
  recopila, `writer` produce la respuesta, `advisor` revisa. El conjunto es
  extensible.
- Al final, el manager escribe un breve informe en la memoria.

## Sin "teléfono escacharrado"

Una regla clave: los artefactos intermedios llegan al sintetizador **literalmente**,
no como una paráfrasis del manager. Los hallazgos de un explorer se entregan
directamente al writer, de modo que el detalle no se pierde a través de una cadena
de resúmenes. Esto es lo que hace que la descomposición aporte calidad en lugar de
diluirla.

## Por qué "el manager nunca escribe"

Si el coordinador también escribiera la respuesta, tendría la tentación de saltarse
a los workers y perder el beneficio de la especialización. Mantener la síntesis en
un `writer` dedicado (alimentado con entradas literales) impone la división del
trabajo. Veles lo convierte en una garantía en tiempo de ejecución.

## Cuándo ayuda — y cuándo no

La descomposición compensa en tareas amplias o de múltiples facetas (auditar este
código, investigar esta pregunta desde varios ángulos). Para una petición rápida de
contexto único solo añade sobrecarga, razón por la cual el modo manager es de
**activación explícita**, desactivado por defecto (`veles run --manager` o
`VELES_MANAGER_MODE=1`).

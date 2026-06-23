# Documentazione di Veles

> 🌐 **Lingue:** [English](../en/index.md) · [简体中文](../zh-CN/index.md) · [繁體中文](../zh-TW/index.md) · [日本語](../ja/index.md) · [한국어](../ko/index.md) · [Español](../es/index.md) · [Français](../fr/index.md) · **Italiano** · [Português (BR)](../pt-BR/index.md) · [Português (PT)](../pt-PT/index.md) · [Русский](../ru/index.md) · [العربية](../ar/index.md) · [हिन्दी](../hi/index.md) · [বাংলা](../bn/index.md) · [Tiếng Việt](../vi/index.md)

Veles è un framework di agenti da riga di comando minimalista e local-first. Lo punti verso una directory
di progetto; lui mantiene una **memoria di progetto** strutturata, **impara** dalle tue
sessioni, esegue qualunque provider LLM (cloud o locale) e accumula **skill** e **tool**
riutilizzabili man mano che lavora.

Questa documentazione segue il modello [Diátaxis](https://diataxis.fr/). Scegli il
quadrante che corrisponde a ciò di cui hai bisogno in questo momento.

## Inizia da qui

Se non hai mai usato Veles, fai i due tutorial in ordine:

1. **[Per iniziare](tutorials/getting-started.md)** — installa Veles, imposta una chiave
   API, crea il tuo primo progetto ed esegui il tuo primo prompt.
2. **[Costruire una base di conoscenza](tutorials/building-a-knowledge-base.md)** — importa
   fonti nella LLM-Wiki, fai domande e consolida le sessioni.

## Tutorial — impara facendo

- [Per iniziare](tutorials/getting-started.md)
- [Costruire una base di conoscenza](tutorials/building-a-knowledge-base.md)

## Guide pratiche — porta a termine un'attività

- [Configurare i provider (cloud e locali)](how-to/configure-providers.md)
- [Instradare attività diverse verso modelli diversi](how-to/per-task-routing.md)
- [Eseguire Veles come daemon](how-to/run-as-daemon.md)
- [Collegare un canale Telegram](how-to/connect-telegram.md)
- [Gestire skill, tool e moduli](how-to/manage-skills-and-tools.md)
- [Lavorare con progetti multipli e sottoprogetti](how-to/multi-project-and-subprojects.md)
- [Sicurezza: trust, autopilot, secret](how-to/security-and-permissions.md)
- [Attività di lunga durata: goal, job, dreaming, ricerca](how-to/long-running-tasks.md)
- [Collegare server MCP esterni](how-to/external-mcp-servers.md)
- [Eseguire backup e condividere un progetto](how-to/backup-and-share.md)

## Riferimento — consultalo

- [Riferimento dei comandi CLI](reference/cli.md)
- [Configurazione (`config.toml`)](reference/configuration.md)
- [Variabili d'ambiente](reference/environment-variables.md)
- [Provider](reference/providers.md)
- [Scorciatoie da tastiera e slash command della TUI](reference/tui.md)
- [Layout e stato del progetto](reference/project-layout.md)

## Spiegazione — comprendi il design

- [Panoramica dell'architettura](explanation/architecture.md)
- [Memoria del progetto e ciclo di apprendimento](explanation/project-memory-and-learning-loop.md)
- [Skill e tool come capacità accumulata](explanation/skills-and-tools.md)
- [Modalità di esecuzione](explanation/modes.md)
- [Orchestrazione multi-agente](explanation/multi-agent-orchestration.md)
- [Layout pack e la LLM-Wiki](explanation/layout-packs-and-llm-wiki.md)
- [Trust e la sandbox](explanation/trust-and-sandbox.md)

---

Per la visione del prodotto e le motivazioni di design vedi `VISION.md` (nella radice del repo);
per la cronologia completa dell'implementazione vedi `MILESTONES.md`. Quelli sono rivolti agli sviluppatori
— questa documentazione serve a **usare** Veles.

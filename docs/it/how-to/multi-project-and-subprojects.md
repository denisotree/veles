# Come lavorare con più progetti e sottoprogetti

> 🌐 **Lingue:** [English](../../en/how-to/multi-project-and-subprojects.md) · [简体中文](../../zh-CN/how-to/multi-project-and-subprojects.md) · [繁體中文](../../zh-TW/how-to/multi-project-and-subprojects.md) · [日本語](../../ja/how-to/multi-project-and-subprojects.md) · [한국어](../../ko/how-to/multi-project-and-subprojects.md) · [Español](../../es/how-to/multi-project-and-subprojects.md) · [Français](../../fr/how-to/multi-project-and-subprojects.md) · **Italiano** · [Português (BR)](../../pt-BR/how-to/multi-project-and-subprojects.md) · [Português (PT)](../../pt-PT/how-to/multi-project-and-subprojects.md) · [Русский](../../ru/how-to/multi-project-and-subprojects.md) · [العربية](../../ar/how-to/multi-project-and-subprojects.md) · [हिन्दी](../../hi/how-to/multi-project-and-subprojects.md) · [বাংলা](../../bn/how-to/multi-project-and-subprojects.md) · [Tiếng Việt](../../vi/how-to/multi-project-and-subprojects.md)

Veles esegue molti progetti in un unico loop dell'agente. Ogni progetto ha la
propria memoria, le proprie skill e i propri strumenti. I **sottoprogetti** sono
progetti annidati sotto un genitore — utili per scomporre un grande monorepo o una
base di conoscenza in memorie con ambito ristretto.

## Progetti

Veles individua il progetto attivo risalendo dalla tua cwd fino a una directory
`.veles/` (come fa `git`). Gestisci il registro:

```bash
veles project list                  # registered projects, most-recent first
veles project add /path/to/project  # register an existing project
veles project add /path --slug web  # with a custom slug
veles project remove <slug>         # unregister (files untouched)
```

`switch` stampa un percorso, così puoi fare `cd` in un progetto:

```bash
cd "$(veles project switch web)"
```

Esegui un comando su un progetto altrove senza `cd`:

```bash
veles run --project-root /path/to/project "..."
```

## Sottoprogetti

Un sottoprogetto è un progetto Veles figlio all'interno di un genitore. Crearne uno:

```bash
veles subproject init frontend --description "the web client"
veles subproject list
cd "$(veles subproject switch frontend)"
veles subproject remove frontend    # unregister (files untouched)
```

### Lascia che Veles suggerisca una suddivisione

Quando la wiki di un progetto cresce, Veles può rilevare cluster tematici e
proporli come sottoprogetti:

```bash
veles subproject suggest            # print candidates
veles subproject suggest --save     # save each to .veles/memory/proposals/ for recall
```

## Quando usare cosa

- **Progetti separati** — basi di conoscenza / codebase non correlate.
- **Sottoprogetti** — parti di un'unica cosa più grande che traggono vantaggio da
  una memoria con ambito ristretto ma condividono un contesto genitore.

Vedi [architettura](../explanation/architecture.md) per capire come il contesto
multi-progetto viene caricato su richiesta anziché come un unico scarico monolitico.

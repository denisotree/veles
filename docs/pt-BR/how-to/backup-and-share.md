# Como fazer backup e compartilhar um projeto

> 🌐 **Idiomas:** [English](../../en/how-to/backup-and-share.md) · [简体中文](../../zh-CN/how-to/backup-and-share.md) · [繁體中文](../../zh-TW/how-to/backup-and-share.md) · [日本語](../../ja/how-to/backup-and-share.md) · [한국어](../../ko/how-to/backup-and-share.md) · [Español](../../es/how-to/backup-and-share.md) · [Français](../../fr/how-to/backup-and-share.md) · [Italiano](../../it/how-to/backup-and-share.md) · **Português (BR)** · [Português (PT)](../../pt-PT/how-to/backup-and-share.md) · [Русский](../../ru/how-to/backup-and-share.md) · [العربية](../../ar/how-to/backup-and-share.md) · [हिन्दी](../../hi/how-to/backup-and-share.md) · [বাংলা](../../bn/how-to/backup-and-share.md) · [Tiếng Việt](../../vi/how-to/backup-and-share.md)

Projetos Veles são portáteis. Exporte um projeto para um único pacote `.tar.gz` para
backup ou migração, ou um template higienizado para compartilhar sem vazar seus dados.

## Backup completo

Empacota o projeto inteiro (`.veles/` + `AGENTS.md`), menos os efêmeros de runtime (locks,
estado de orçamento):

```bash
veles export full ./my-project-backup.tar.gz
```

Restaure-o em qualquer lugar:

```bash
veles import ./my-project-backup.tar.gz                # into cwd
veles import ./my-project-backup.tar.gz --into ./restored
veles import ./my-project-backup.tar.gz --force        # overwrite an existing .veles/
```

Um pacote completo inclui seu `memory.db` (sessões, insights), então trate-o como
dados privados.

## Template compartilhável

Empacota apenas o esqueleto reutilizável — schema, skills, módulos e páginas de wiki
que não são de sessão. Ele **remove** `memory.db`, `sources/`, `sessions/`, concessões de confiança e
faz redação de PII no texto:

```bash
veles export template ./my-template.tar.gz
```

Entregue o template a um colega; ele faz `veles import` e obtém sua estrutura
e skills sem o seu histórico de conversas ou as fontes brutas.

## Qual usar

| Objetivo | Comando |
|---|---|
| Fazer backup / mover um projeto intacto | `veles export full` |
| Compartilhar estrutura + skills, não dados | `veles export template` |

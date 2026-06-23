# Como fazer backup e compartilhar um projeto

> 🌐 **Idiomas:** **English** · [Русский](../../ru/how-to/backup-and-share.md)

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

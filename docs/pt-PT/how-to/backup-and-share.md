# Como fazer cópia de segurança e partilhar um projeto

> 🌐 **Idiomas:** [English](../../en/how-to/backup-and-share.md) · [简体中文](../../zh-CN/how-to/backup-and-share.md) · [繁體中文](../../zh-TW/how-to/backup-and-share.md) · [日本語](../../ja/how-to/backup-and-share.md) · [한국어](../../ko/how-to/backup-and-share.md) · [Español](../../es/how-to/backup-and-share.md) · [Français](../../fr/how-to/backup-and-share.md) · [Italiano](../../it/how-to/backup-and-share.md) · [Português (BR)](../../pt-BR/how-to/backup-and-share.md) · **Português (PT)** · [Русский](../../ru/how-to/backup-and-share.md) · [العربية](../../ar/how-to/backup-and-share.md) · [हिन्दी](../../hi/how-to/backup-and-share.md) · [বাংলা](../../bn/how-to/backup-and-share.md) · [Tiếng Việt](../../vi/how-to/backup-and-share.md)

Os projetos Veles são portáteis. Exporte um projeto para um único pacote `.tar.gz`
para cópia de segurança ou migração, ou um modelo higienizado para partilhar sem
expor os seus dados.

## Cópia de segurança completa

Empacota o projeto inteiro (`.veles/` + `AGENTS.md`), excluindo os dados efémeros
de execução (locks, estado do orçamento):

```bash
veles export full ./my-project-backup.tar.gz
```

Restaure-o em qualquer lugar:

```bash
veles import ./my-project-backup.tar.gz                # into cwd
veles import ./my-project-backup.tar.gz --into ./restored
veles import ./my-project-backup.tar.gz --force        # overwrite an existing .veles/
```

Um pacote completo inclui o seu `memory.db` (sessões, insights), por isso trate-o
como dados privados.

## Modelo partilhável

Empacota apenas o andaime reutilizável — esquema, skills, módulos e páginas de
wiki que não sejam de sessão. **Remove** o `memory.db`, `sources/`, `sessions/`,
concessões de confiança, e aplica redação de PII ao texto:

```bash
veles export template ./my-template.tar.gz
```

Entregue o modelo a um colega; ele faz `veles import` e obtém a sua estrutura e
skills sem o seu histórico de conversas nem as fontes em bruto.

## Qual usar

| Objetivo | Comando |
|---|---|
| Fazer cópia de segurança / mover um projeto intacto | `veles export full` |
| Partilhar estrutura + skills, não dados | `veles export template` |

# Documentação do Veles

> 🌐 **Idiomas:** [English](../en/index.md) · [简体中文](../zh-CN/index.md) · [繁體中文](../zh-TW/index.md) · [日本語](../ja/index.md) · [한국어](../ko/index.md) · [Español](../es/index.md) · [Français](../fr/index.md) · [Italiano](../it/index.md) · **Português (BR)** · [Português (PT)](../pt-PT/index.md) · [Русский](../ru/index.md) · [العربية](../ar/index.md) · [हिन्दी](../hi/index.md) · [বাংলা](../bn/index.md) · [Tiếng Việt](../vi/index.md)

O Veles é um framework de agente de linha de comando minimalista e local-first.
Você o aponta para um diretório de projeto; ele mantém uma **memória do projeto**
estruturada, **aprende** com as suas sessões, executa qualquer provedor de LLM
(nuvem ou local) e acumula **skills** e **ferramentas** reutilizáveis conforme
trabalha.

Esta documentação segue o modelo [Diátaxis](https://diataxis.fr/). Escolha o
quadrante que corresponde ao que você precisa agora.

## Comece por aqui

Se você nunca executou o Veles, faça os dois tutoriais na ordem:

1. **[Primeiros passos](tutorials/getting-started.md)** — instale o Veles, defina
   uma chave de API, crie o seu primeiro projeto e execute o seu primeiro prompt.
2. **[Construindo uma base de conhecimento](tutorials/building-a-knowledge-base.md)** —
   ingira fontes na LLM-Wiki, faça perguntas e consolide sessões.

## Tutoriais — aprenda fazendo

- [Primeiros passos](tutorials/getting-started.md)
- [Construindo uma base de conhecimento](tutorials/building-a-knowledge-base.md)

## Guias práticos — realize uma tarefa

- [Configurar provedores (nuvem e local)](how-to/configure-providers.md)
- [Rotear diferentes tarefas para diferentes modelos](how-to/per-task-routing.md)
- [Executar o Veles como daemon](how-to/run-as-daemon.md)
- [Conectar um canal do Telegram](how-to/connect-telegram.md)
- [Gerenciar skills, ferramentas e módulos](how-to/manage-skills-and-tools.md)
- [Trabalhar com múltiplos projetos e subprojetos](how-to/multi-project-and-subprojects.md)
- [Segurança: trust, autopilot, segredos](how-to/security-and-permissions.md)
- [Tarefas de longa duração: goals, jobs, dreaming, pesquisa](how-to/long-running-tasks.md)
- [Conectar servidores MCP externos](how-to/external-mcp-servers.md)
- [Fazer backup e compartilhar um projeto](how-to/backup-and-share.md)

## Referência — consulte

- [Referência de comandos da CLI](reference/cli.md)
- [Configuração (`config.toml`)](reference/configuration.md)
- [Variáveis de ambiente](reference/environment-variables.md)
- [Provedores](reference/providers.md)
- [Atalhos de teclado e comandos slash da TUI](reference/tui.md)
- [Layout e estado do projeto](reference/project-layout.md)

## Explicação — entenda o design

- [Visão geral da arquitetura](explanation/architecture.md)
- [Memória do projeto e o loop de aprendizado](explanation/project-memory-and-learning-loop.md)
- [Skills e ferramentas como capacidade acumulável](explanation/skills-and-tools.md)
- [Modos de execução](explanation/modes.md)
- [Orquestração multiagente](explanation/multi-agent-orchestration.md)
- [Layout packs e a LLM-Wiki](explanation/layout-packs-and-llm-wiki.md)
- [Trust e o sandbox](explanation/trust-and-sandbox.md)

---

Para a visão de produto e a justificativa de design, veja o `VISION.md` (na raiz
do repositório); para o histórico completo de implementação, veja o
`MILESTONES.md`. Esses são voltados para desenvolvedores — esta documentação é
para **usar** o Veles.

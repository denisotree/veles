# Documentação do Veles

> 🌐 **Idiomas:** [English](../en/index.md) · [简体中文](../zh-CN/index.md) · [繁體中文](../zh-TW/index.md) · [日本語](../ja/index.md) · [한국어](../ko/index.md) · [Español](../es/index.md) · [Français](../fr/index.md) · [Italiano](../it/index.md) · [Português (BR)](../pt-BR/index.md) · **Português (PT)** · [Русский](../ru/index.md) · [العربية](../ar/index.md) · [हिन्दी](../hi/index.md) · [বাংলা](../bn/index.md) · [Tiếng Việt](../vi/index.md)

O Veles é uma framework minimalista de agentes CLI, local-first. Aponta-lo para um
diretório de projeto; ele mantém uma **memória de projeto** estruturada, **aprende**
com as tuas sessões, corre qualquer fornecedor de LLM (na nuvem ou local) e acumula
**skills** e **ferramentas** reutilizáveis à medida que trabalha.

Esta documentação segue o modelo [Diátaxis](https://diataxis.fr/). Escolhe o
quadrante que corresponde ao que precisas neste momento.

## Começa por aqui

Se nunca correste o Veles, faz os dois tutoriais por ordem:

1. **[Primeiros passos](tutorials/getting-started.md)** — instala o Veles, define uma
   chave de API, cria o teu primeiro projeto e corre o teu primeiro prompt.
2. **[Construir uma base de conhecimento](tutorials/building-a-knowledge-base.md)** — ingere
   fontes para o LLM-Wiki, faz perguntas e consolida sessões.

## Tutoriais — aprende fazendo

- [Primeiros passos](tutorials/getting-started.md)
- [Construir uma base de conhecimento](tutorials/building-a-knowledge-base.md)

## Guias práticos — concretizar uma tarefa

- [Configurar fornecedores (nuvem e local)](how-to/configure-providers.md)
- [Encaminhar tarefas diferentes para modelos diferentes](how-to/per-task-routing.md)
- [Correr o Veles como daemon](how-to/run-as-daemon.md)
- [Ligar um canal de Telegram](how-to/connect-telegram.md)
- [Gerir skills, ferramentas e módulos](how-to/manage-skills-and-tools.md)
- [Trabalhar com vários projetos e subprojetos](how-to/multi-project-and-subprojects.md)
- [Segurança: confiança, autopilot, segredos](how-to/security-and-permissions.md)
- [Tarefas de longa duração: objetivos, jobs, dreaming, pesquisa](how-to/long-running-tasks.md)
- [Ligar servidores MCP externos](how-to/external-mcp-servers.md)
- [Fazer cópia de segurança e partilhar um projeto](how-to/backup-and-share.md)

## Referência — consulta

- [Referência de comandos CLI](reference/cli.md)
- [Configuração (`config.toml`)](reference/configuration.md)
- [Variáveis de ambiente](reference/environment-variables.md)
- [Fornecedores](reference/providers.md)
- [Atalhos de teclado e comandos slash da TUI](reference/tui.md)
- [Estrutura e estado do projeto](reference/project-layout.md)

## Explicação — compreende o design

- [Visão geral da arquitetura](explanation/architecture.md)
- [Memória de projeto e o ciclo de aprendizagem](explanation/project-memory-and-learning-loop.md)
- [Skills e ferramentas como capacidade acumulada](explanation/skills-and-tools.md)
- [Modos de execução](explanation/modes.md)
- [Orquestração multi-agente](explanation/multi-agent-orchestration.md)
- [Layout packs e o LLM-Wiki](explanation/layout-packs-and-llm-wiki.md)
- [Confiança e a sandbox](explanation/trust-and-sandbox.md)

---

Para a visão de produto e a fundamentação do design, consulta `VISION.md` (na raiz
do repositório); para o histórico completo de implementação, consulta `MILESTONES.md`.
Esses documentos destinam-se a programadores — esta documentação é para **usar** o Veles.

# Como gerir a segurança: confiança, autopilot, segredos

> 🌐 **Idiomas:** [English](../../en/how-to/security-and-permissions.md) · [简体中文](../../zh-CN/how-to/security-and-permissions.md) · [繁體中文](../../zh-TW/how-to/security-and-permissions.md) · [日本語](../../ja/how-to/security-and-permissions.md) · [한국어](../../ko/how-to/security-and-permissions.md) · [Español](../../es/how-to/security-and-permissions.md) · [Français](../../fr/how-to/security-and-permissions.md) · [Italiano](../../it/how-to/security-and-permissions.md) · [Português (BR)](../../pt-BR/how-to/security-and-permissions.md) · **Português (PT)** · [Русский](../../ru/how-to/security-and-permissions.md) · [العربية](../../ar/how-to/security-and-permissions.md) · [हिन्दी](../../hi/how-to/security-and-permissions.md) · [বাংলা](../../bn/how-to/security-and-permissions.md) · [Tiếng Việt](../../vi/how-to/security-and-permissions.md)

O Veles condiciona as ações perigosas por trás de uma **escada de confiança**,
coloca o acesso a ficheiros numa sandbox e mantém os segredos no porta-chaves
(keychain) do sistema operativo. Para a justificação, consulte
[confiança e a sandbox](../explanation/trust-and-sandbox.md).

## A escada de confiança

As ferramentas sensíveis (`run_shell`, `write_file`, `fetch_url`, …) pedem
confirmação antes de executar. Escolhe: permitir **uma vez**, **sempre
para este projeto**, **sempre em todo o lado** ou **recusar**. As autorizações
persistem, pelo que não voltará a ser questionado.

Faça a gestão das autorizações sem esperar por um pedido:

```bash
veles trust list                          # autorizações atuais (utilizador + projeto)
veles trust set run_shell --scope project # autorizar previamente para este projeto
veles trust set write_file --scope user   # autorizar previamente em todo o lado
veles trust revoke run_shell              # remover uma autorização
veles trust clear --scope all             # apagar tudo
```

Algumas ações são **sempre confirmadas**, mesmo com uma autorização — eliminar
ficheiros, obter URLs, instalar uma nova skill/ferramenta/módulo, ligar um canal
e escrever fora do projeto.

## Autopilot — uma exceção com limite temporal

Para uma execução sem supervisão (um lote durante a noite), abra uma janela em
que os pedidos de confiança são permitidos automaticamente:

```bash
veles autopilot enable --until +2h
veles autopilot enable --until 2026-12-31T23:00:00Z
veles autopilot status
veles autopilot disable
```

Cada ação em autopilot é registada para revisão posterior. Os contextos não
interativos (daemon, lote) recusam por omissão, a menos que o autopilot esteja
ativo.

## Segredos

As chaves de API e os tokens de bots ficam no porta-chaves do sistema operativo,
nunca em ficheiros de configuração:

```bash
veles secret set OPENROUTER_API_KEY       # pede o valor (ou passe por stdin)
veles secret list                         # que segredos estão configurados
veles secret get OPENROUTER_API_KEY --reveal
veles secret delete OPENROUTER_API_KEY
veles secret set OPENROUTER_API_KEY --project myproj   # uma chave só para um projeto
```

A pesquisa recorre, em alternativa, à [variável de ambiente](../reference/environment-variables.md)
correspondente, a menos que passe `--no-env-fallback`.

## A sandbox

As ferramentas podem ler dentro do projeto ativo, de `~/.veles/skills/` e de
`~/.veles/locales/`, e escrever apenas dentro do projeto — ou apenas nas zonas
graváveis do layout, quando o layout as declara. Substitua as raízes para
configurações avançadas com `VELES_SANDBOX_ROOTS` (separadas por `:`). A obtenção
de URLs mantém uma lista de negação de SSRF; `VELES_FETCH_ALLOW_PRIVATE=1` levanta
o bloqueio da rede privada.

Dentro de `.veles/` do projeto, as ferramentas de ficheiros do agente só podem
escrever em `skills/`, `tools/`, `tmp/`, `plans/`, `memory/` e `artifacts/`. Tudo o
resto aí — `trust.json`, `config.toml`, `project.toml`, `modules/`, `wiki.toml`,
`memory.db` — só muda através de comandos `veles` e das ferramentas do próprio
Veles. As ferramentas de ficheiros recusam também qualquer outro diretório
`.veles/` do projeto (o de um subprojeto, ou um que o agente plantasse em `wiki/`)
a qualquer profundidade. Assim, através das suas ferramentas de ficheiros, o agente
não pode conceder confiança a si próprio nem adicionar código que o Veles
executaria (uma ferramenta que escreva em `.veles/tools/` só é carregada depois de
aprovar o seu ficheiro). Outras grafias do mesmo ficheiro (maiúsculas/minúsculas,
`..`, um symlink) também são recusadas.

Ficheiros que são executados sem um comando explícito ou que orientam uma CLI de
agente — tudo em `.git/`, `.githooks/`, `.claude/`, `.gemini/`, `.agents/`,
`.codex/`, `.vscode/`, `.devcontainer/`, `.husky/`, e `.envrc`, `.mcp.json`,
`.pre-commit-config.yaml`, `lefthook.yml`, a qualquer profundidade, mais o
diretório `core.hooksPath` do repositório e o destino de um `.git` que seja
symlink — as ferramentas de ficheiros do agente só escrevem depois de confirmar
essa escrita. Concessões de confiança e o autopilot não a cobrem; o daemon
pergunta no canal, e uma execução em lote sem ninguém a quem perguntar recusa.

Os fornecedores `claude-cli` e `antigravity-cli` funcionam como um modelo apenas com as
ferramentas do Veles: o seu próprio shell, edição de ficheiros e ferramentas web,
as definições e hooks `.claude/` do projeto e outros servidores MCP não se
aplicam, e cada ferramenta do Veles que chamam passa pela escada de confiança
acima (ninguém pode responder a um pedido aí, por isso tudo o que ainda não foi
concedido é recusado). A sua configuração MCP fica em `.veles/tmp/delegate-<pid>/`, uma
por cada processo em execução. O `agy` corre aí num espaço de trabalho temporário, com
`--dangerously-skip-permissions` quando tem as ferramentas do Veles — caso contrário o
agy recusa chamadas MCP sem interface — e um hook nesse espaço de trabalho nega todas as
suas ferramentas; um hook que falhe também nega. O ficheiro do hook está sob `.agents/`,
por isso o agy não o consegue reescrever através das ferramentas do Veles sem a sua
confirmação.

Limites conhecidos:

- `run_shell` é um shell: depois de o conceder (ou sob autopilot), pode escrever
  qualquer um dos ficheiros acima sem a confirmação por ficheiro.
- Uma aprovação MCP fixa a linha de comando do servidor, não os ficheiros que ele
  executa a partir do projeto (um script indicado em `args`) — reveja-os também.
- Com um fornecedor CLI, as execuções que pré-autorizam ferramentas apenas para si
  próprias (tarefas de fundo do daemon, `veles research`) não transmitem isso à CLI
  delegada: a pré-autorização vive no processo do Veles, e o servidor MCP que a CLI
  arranca é outro, por isso as suas ferramentas do Veles precisam de uma concessão
  permanente `veles trust set` ou de uma janela de autopilot. O modo de planeamento da
  execução principal também não as alcança.
- O `antigravity-cli` depende de o agy respeitar o `.agents/hooks.json` do seu espaço de
  trabalho; uma versão do agy que deixasse de ler os hooks do espaço de trabalho deixaria
  as suas próprias ferramentas abertas sob `--dangerously-skip-permissions`.

Caminhos com caracteres de controlo (sequências de escape de terminal, substituições
bidi) são recusados, e as confirmações, o pedido de confiança e a pré-visualização
do diff mostram esses caracteres escapados — uma chamada de ferramenta não pode
forjar o texto que aprova.

Os servidores MCP de uma configuração só arrancam depois de os aprovar — veja
[servidores MCP externos](external-mcp-servers.md).

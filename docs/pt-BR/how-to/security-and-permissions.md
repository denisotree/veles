# Como gerenciar segurança: confiança, autopilot, segredos

> 🌐 **Idiomas:** [English](../../en/how-to/security-and-permissions.md) · [简体中文](../../zh-CN/how-to/security-and-permissions.md) · [繁體中文](../../zh-TW/how-to/security-and-permissions.md) · [日本語](../../ja/how-to/security-and-permissions.md) · [한국어](../../ko/how-to/security-and-permissions.md) · [Español](../../es/how-to/security-and-permissions.md) · [Français](../../fr/how-to/security-and-permissions.md) · [Italiano](../../it/how-to/security-and-permissions.md) · **Português (BR)** · [Português (PT)](../../pt-PT/how-to/security-and-permissions.md) · [Русский](../../ru/how-to/security-and-permissions.md) · [العربية](../../ar/how-to/security-and-permissions.md) · [हिन्दी](../../hi/how-to/security-and-permissions.md) · [বাংলা](../../bn/how-to/security-and-permissions.md) · [Tiếng Việt](../../vi/how-to/security-and-permissions.md)

O Veles protege ações perigosas por trás de uma **escada de confiança**, isola o acesso
a arquivos em um sandbox e mantém os segredos no keychain do sistema operacional. Para
entender o porquê, veja [confiança & sandbox](../explanation/trust-and-sandbox.md).

## A escada de confiança

Tools sensíveis (`run_shell`, `write_file`, `fetch_url`, …) pedem confirmação antes de
executar. Você escolhe: permitir **uma vez**, **sempre para este projeto**, **sempre em
todo lugar** ou **recusar**. As permissões concedidas são persistidas, então você não é
questionado de novo.

Gerencie as permissões sem esperar por um prompt:

```bash
veles trust list                          # current grants (user + project)
veles trust set run_shell --scope project # pre-grant for this project
veles trust set write_file --scope user   # pre-grant everywhere
veles trust revoke run_shell              # remove a grant
veles trust clear --scope all             # wipe everything
```

Algumas ações são **sempre confirmadas** mesmo com uma permissão concedida — excluir
arquivos, buscar URLs, instalar uma nova skill/tool/módulo, conectar um canal e
escrever fora do projeto.

## Autopilot — um bypass com tempo limitado

Para uma execução sem supervisão (um lote noturno), abra uma janela em que os prompts
de confiança são autoaprovados:

```bash
veles autopilot enable --until +2h
veles autopilot enable --until 2026-12-31T23:00:00Z
veles autopilot status
veles autopilot disable
```

Toda ação do autopilot é registrada para revisão posterior. Contextos não interativos
(daemon, lote) recusam por padrão, a menos que o autopilot esteja ativo.

## Segredos

Chaves de API e tokens de bot ficam no keychain do sistema operacional, nunca em
arquivos de configuração:

```bash
veles secret set OPENROUTER_API_KEY       # prompts (or pipe via stdin)
veles secret list                         # which secrets are configured
veles secret get OPENROUTER_API_KEY --reveal
veles secret delete OPENROUTER_API_KEY
veles secret set OPENROUTER_API_KEY --project myproj   # a key for one project only
```

A busca recorre, como fallback, à [variável de ambiente](../reference/environment-variables.md)
correspondente, a menos que você passe `--no-env-fallback`.

## O sandbox

As tools podem ler dentro do projeto ativo, de `~/.veles/skills/` e de
`~/.veles/locales/`, e escrever apenas dentro do projeto — ou apenas nas zonas
graváveis do layout, quando o layout as declara. Sobrescreva as raízes para
configurações avançadas com `VELES_SANDBOX_ROOTS` (separadas por `:`). As buscas de URL
mantêm uma deny-list de SSRF; `VELES_FETCH_ALLOW_PRIVATE=1` remove o bloqueio de rede
privada.

Dentro do `.veles/` do projeto, as tools de arquivo do agente só podem escrever em
`skills/`, `tools/`, `tmp/`, `plans/`, `memory/` e `artifacts/`. Todo o resto —
`trust.json`, `config.toml`, `project.toml`, `modules/`, `wiki.toml`, `memory.db` — só
muda por comandos `veles` e pelas tools do próprio Veles. As tools de arquivo também
recusam qualquer outro diretório `.veles/` do projeto (o de um subprojeto, ou um que o
agente plantaria em `wiki/`) em qualquer profundidade. Assim, pelas suas tools de
arquivo o agente não consegue conceder confiança a si mesmo nem adicionar código que o
Veles executaria (uma tool que ele escreve em `.veles/tools/` só carrega depois que
você aprova o arquivo dela). Outras grafias do mesmo arquivo (maiúsculas/minúsculas,
`..`, um symlink) também são recusadas.

Arquivos que rodam sem um comando explícito ou que direcionam uma CLI de agente —
qualquer coisa sob `.git/`, `.githooks/`, `.claude/`, `.gemini/`, `.agents/`,
`.codex/`, `.vscode/`, `.devcontainer/`, `.husky/`, e `.envrc`, `.mcp.json`,
`.pre-commit-config.yaml`, `lefthook.yml`, em qualquer profundidade, mais o diretório
`core.hooksPath` do repositório e o destino de um `.git` que seja symlink — as tools de
arquivo do agente só os escrevem depois que você confirma essa escrita. Concessões de
confiança e o autopilot não a cobrem; o daemon pergunta no canal, e uma execução em
lote sem ninguém para perguntar recusa.

Os provedores `claude-cli`, `codex` e `antigravity-cli` rodam como um modelo apenas com as tools
do Veles: as próprias tools de shell, edição de arquivos e web deles, as configurações e
hooks de `.claude/` do projeto e outros servidores MCP não se aplicam, e toda tool do
Veles que eles chamam passa pela escada de confiança acima (ninguém pode responder a
uma pergunta ali, então tudo que ainda não foi concedido é recusado). A config de MCP
deles fica em `.veles/tmp/delegate-<pid>/`, uma por processo em execução, e as tools de
arquivo do agente não conseguem escrever nela. O `agy` roda em um workspace temporário
fora do projeto, em `~/.veles/tmp/`, então os hooks e servidores MCP de `.agents/` do
próprio projeto nunca chegam a ele. Ele roda com `--dangerously-skip-permissions` quando
tem as tools do Veles — o agy recusa chamadas MCP em modo headless caso contrário — e um
hook nesse workspace nega toda tool dele; um hook que falha também nega. As tools de
arquivo do Veles não escrevem fora do projeto, então o agy não consegue reescrever esse
hook por meio delas. O `codex` também roda fora do projeto, com a sua config do codex
ignorada, um sandbox somente leitura e as tools próprias dele desligadas por flags de
recurso cujos nomes o Veles confere antes de cada primeira execução — um codex que
renomeou uma de que depende é recusado, não executado aberto. O servidor MCP dele vai
nos argumentos (sem arquivo de config), só as tools desse servidor são aprovadas, e o
ambiente que esse servidor recebe é repassado por nome — nunca `VELES_TRUST_AUTO_ALLOW`.

Limites conhecidos:

- `run_shell` é um shell: depois que você o concede (ou sob autopilot), ele pode
  escrever qualquer um dos arquivos acima sem a confirmação por arquivo.
- Uma aprovação de MCP fixa a linha de comando do servidor, não os arquivos que ele
  executa a partir do projeto (um script citado em `args`) — revise esses também.
- Com um provedor CLI, execuções que pré-autorizam tools só para si mesmas (jobs em
  segundo plano do daemon, `veles research`) não repassam isso à CLI delegada: a
  pré-autorização vive no processo do Veles, e o servidor MCP que a CLI inicia é outro,
  então as tools do Veles dela precisam de uma concessão permanente com
  `veles trust set` ou de uma janela de autopilot. O modo de planejamento da execução
  pai também não chega a elas.
- O `antigravity-cli` depende de o agy respeitar o `.agents/hooks.json` do seu
  workspace; uma versão do agy que parasse de ler os hooks do workspace deixaria as
  tools dele abertas sob `--dangerously-skip-permissions`.

Caminhos com caracteres de controle (escapes de terminal, sobrescritas bidi) são
recusados, e as confirmações, o prompt de confiança e a prévia do diff mostram esses
caracteres escapados — uma chamada de tool não consegue forjar o texto que você aprova.

Servidores MCP de uma configuração só iniciam depois que você os aprova — veja
[servidores MCP externos](external-mcp-servers.md#aprovar-inspecionar-e-testar).

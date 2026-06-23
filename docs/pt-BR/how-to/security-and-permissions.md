# Como gerenciar segurança: confiança, autopilot, segredos

> 🌐 **Idiomas:** **English** · [Русский](../../ru/how-to/security-and-permissions.md)

O Veles protege ações perigosas por trás de uma **escada de confiança**, isola o acesso
a arquivos em um sandbox e mantém os segredos no keychain do sistema operacional. Para
entender o porquê, veja [confiança & sandbox](../explanation/trust-and-sandbox.md).

## A escada de confiança

Tools sensíveis (`run_shell`, `write_file`, `fetch_url`, …) pedem confirmação antes de
executar. Você escolhe: permitir **uma vez**, **sempre para este projeto**, **sempre em
todo lugar** ou **recusar**. As permissões concedidas são persistidas, então você não é
perguntado de novo.

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
```

A busca recorre, como fallback, à [variável de ambiente](../reference/environment-variables.md)
correspondente, a menos que você passe `--no-env-fallback`.

## O sandbox

As tools podem ler dentro do projeto ativo e de `~/.veles/`, e escrever apenas nas
zonas graváveis do layout (`wiki/`, `.veles/` por padrão). Sobrescreva as raízes para
configurações avançadas com `VELES_SANDBOX_ROOTS` (separadas por `:`). As buscas de URL
mantêm uma deny-list de SSRF; `VELES_FETCH_ALLOW_PRIVATE=1` remove o bloqueio de rede
privada.

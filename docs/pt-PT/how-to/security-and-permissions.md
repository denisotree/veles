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
```

A pesquisa recorre, em alternativa, à [variável de ambiente](../reference/environment-variables.md)
correspondente, a menos que passe `--no-env-fallback`.

## A sandbox

As ferramentas podem ler dentro do projeto ativo e de `~/.veles/`, e escrever
apenas nas zonas graváveis do layout (`wiki/`, `.veles/` por omissão).
Substitua as raízes para configurações avançadas com `VELES_SANDBOX_ROOTS`
(separadas por `:`). A obtenção de URLs mantém uma lista de negação de SSRF;
`VELES_FETCH_ALLOW_PRIVATE=1` levanta o bloqueio da rede privada.

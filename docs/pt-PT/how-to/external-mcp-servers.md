# Como ligar servidores MCP externos

> 🌐 **Idiomas:** [English](../../en/how-to/external-mcp-servers.md) · [简体中文](../../zh-CN/how-to/external-mcp-servers.md) · [繁體中文](../../zh-TW/how-to/external-mcp-servers.md) · [日本語](../../ja/how-to/external-mcp-servers.md) · [한국어](../../ko/how-to/external-mcp-servers.md) · [Español](../../es/how-to/external-mcp-servers.md) · [Français](../../fr/how-to/external-mcp-servers.md) · [Italiano](../../it/how-to/external-mcp-servers.md) · [Português (BR)](../../pt-BR/how-to/external-mcp-servers.md) · **Português (PT)** · [Русский](../../ru/how-to/external-mcp-servers.md) · [العربية](../../ar/how-to/external-mcp-servers.md) · [हिन्दी](../../hi/how-to/external-mcp-servers.md) · [বাংলা](../../bn/how-to/external-mcp-servers.md) · [Tiếng Việt](../../vi/how-to/external-mcp-servers.md)

O Veles é um **cliente** [MCP](https://modelcontextprotocol.io/): pode ligar-se a
servidores MCP externos e expor as suas ferramentas ao agente como se fossem
nativas (GitHub, documentação de bibliotecas, pesquisa na web, os seus próprios
serviços, …).

## Configurar um servidor

Adicione um bloco `[mcp.servers.<name>]` a `<project>/.veles/config.toml` (ou ao
global do utilizador `~/.veles/config.toml`). O `<name>` tem de corresponder a
`[A-Za-z0-9][A-Za-z0-9_-]{0,31}` — passa a fazer parte do nome de cada ferramenta.
São suportados três transportes: `stdio` (predefinição), `http`, `sse`.

| Chave | Transporte | Predefinição | Finalidade |
|---|---|---|---|
| `transport` | — | `"stdio"` | `stdio` \| `http` \| `sse` |
| `command` | stdio (obrigatório) | — | o executável a lançar — **apenas o programa, não os seus argumentos** |
| `args` | stdio | `[]` | lista de argumentos, um token por item |
| `env` | stdio | `{}` | ambiente adicional para o subprocesso (combinado por cima do ambiente herdado) |
| `url` | http/sse (obrigatório) | — | o endpoint do servidor |
| `timeout_s` | — | `120` | orçamento para uma única chamada de ferramenta |
| `connect_timeout_s` | — | `30` | orçamento para a ligação inicial |
| `enabled` | — | `true` | defina `false` para manter a entrada mas saltar a ligação |

Os valores de string em `command`, `args`, `env`, e `url` interpolam `${VAR}` a
partir do ambiente (uma variável não definida torna-se uma string vazia com um
aviso) — mantenha os segredos fora do ficheiro.

> **`command` vs `args`.** O Veles executa o programa diretamente (sem shell), pelo
> que o executável e os seus argumentos são campos **separados**. Escreva
> `command = "npx"`, `args = ["-y", "pkg"]` — **e não** `command = "npx -y pkg"`.

### stdio (subprocesso local)

```toml
[mcp.servers.github]
transport = "stdio"
command = "npx"
args = ["-y", "@modelcontextprotocol/server-github"]
env = { GITHUB_TOKEN = "${GITHUB_TOKEN}" }
```

Um servidor que execute por conta própria funciona da mesma forma — aponte
`command`/`args` para ele:

```toml
[mcp.servers.mytools]
transport = "stdio"
command = "python"
args = ["-m", "my_mcp_server"]
```

### Um servidor que precisa de uma chave de API (context7)

O [Context7](https://context7.com) fornece documentação de bibliotecas atualizada.
Passe a chave como argumento para que `${VAR}` a mantenha fora do ficheiro:

```toml
[mcp.servers.context7]
transport = "stdio"
command = "npx"
args = ["-y", "@upstash/context7-mcp", "--api-key", "${CONTEXT7_API_KEY}"]
```

```bash
export CONTEXT7_API_KEY=...   # then start veles
```

### http / sse (remoto)

```toml
[mcp.servers.search]
transport = "http"            # streamable HTTP; use "sse" for an SSE endpoint
url = "https://mcp.example.com/mcp"
```

> **Ainda sem cabeçalhos personalizados.** Os transportes `http`/`sse` enviam
> apenas o `url` — o Veles não consegue anexar um cabeçalho `Authorization`. Para
> um servidor remoto que precise de uma chave, prefira a sua variante `stdio` (por
> exemplo `npx`) com a chave em `args`/`env`, ou um endpoint que aceite a chave no
> URL.

## Ocultar ferramentas específicas

Defina `[mcp] disabled_tools` — uma tabela que mapeia cada servidor para os nomes
das ferramentas a saltar:

```toml
[mcp]
disabled_tools = { github = ["delete_repository"], search = ["raw_query"] }
```

## Inspecionar e testar

```bash
veles mcp list              # every configured server: transport, status, tool count
veles mcp test github       # connect to one server and list its tools
```

`veles mcp list` termina sempre com 0 — é um inspetor, não um portão de saúde.
`veles mcp test` termina com 1 quando a ligação falha e com 2 para um nome de
servidor desconhecido.

## Como as ferramentas aparecem

Uma vez configurados, os servidores são montados **automaticamente** no próximo
`veles run` / TUI / arranque do daemon — não há nenhuma flag separada de "ativar
MCP", a presença da configuração é o interruptor. Cada ferramenta entra no registo
normal como `mcp_<server>_<tool>` e pode ser invocada pelo agente como qualquer
ferramenta nativa. Os esquemas são higienizados (limites de nome/comprimento,
remoção de caracteres de controlo) para que um servidor não confiável não consiga
injetar conteúdo no prompt. As dicas das ferramentas mapeiam para a escada de
confiança: as ferramentas destrutivas pedem sempre confirmação, as ferramentas de
leitura passam sem pedido, e tudo o resto passa pelo fluxo de
[confiança](security-and-permissions.md) habitual — conceda aprovação permanente
com `veles trust set` se não quiser que lhe perguntem todas as vezes.

## Tratamento de falhas

Um servidor que não consiga ligar — um `command` em falta, um `url` inválido, ou
qualquer entrada inválida — é registado como um aviso e ignorado. Nunca bloqueia o
arranque nem o agente. Volte a executar `veles mcp list` para ver o estado e o erro.

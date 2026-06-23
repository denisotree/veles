# Como conectar servidores MCP externos

> 🌐 **Idiomas:** [English](../../en/how-to/external-mcp-servers.md) · [简体中文](../../zh-CN/how-to/external-mcp-servers.md) · [繁體中文](../../zh-TW/how-to/external-mcp-servers.md) · [日本語](../../ja/how-to/external-mcp-servers.md) · [한국어](../../ko/how-to/external-mcp-servers.md) · [Español](../../es/how-to/external-mcp-servers.md) · [Français](../../fr/how-to/external-mcp-servers.md) · [Italiano](../../it/how-to/external-mcp-servers.md) · **Português (BR)** · [Português (PT)](../../pt-PT/how-to/external-mcp-servers.md) · [Русский](../../ru/how-to/external-mcp-servers.md) · [العربية](../../ar/how-to/external-mcp-servers.md) · [हिन्दी](../../hi/how-to/external-mcp-servers.md) · [বাংলা](../../bn/how-to/external-mcp-servers.md) · [Tiếng Việt](../../vi/how-to/external-mcp-servers.md)

O Veles é um **cliente** [MCP](https://modelcontextprotocol.io/): ele pode se conectar a
servidores MCP externos e expor as ferramentas deles ao agente como se fossem nativas
(GitHub, documentação de bibliotecas, busca na web, seus próprios serviços, …).

## Configurar um servidor

Adicione um bloco `[mcp.servers.<name>]` ao `<project>/.veles/config.toml` (ou ao
`~/.veles/config.toml` global do usuário). O `<name>` deve corresponder a
`[A-Za-z0-9][A-Za-z0-9_-]{0,31}` — ele se torna parte do nome de cada ferramenta. Três
transportes são suportados: `stdio` (padrão), `http`, `sse`.

| Chave | Transporte | Padrão | Propósito |
|---|---|---|---|
| `transport` | — | `"stdio"` | `stdio` \| `http` \| `sse` |
| `command` | stdio (obrigatório) | — | o executável a ser iniciado — **apenas o programa, não seus argumentos** |
| `args` | stdio | `[]` | lista de argumentos, um token por item |
| `env` | stdio | `{}` | ambiente extra para o subprocesso (mesclado sobre o ambiente herdado) |
| `url` | http/sse (obrigatório) | — | o endpoint do servidor |
| `timeout_s` | — | `120` | orçamento para uma única chamada de ferramenta |
| `connect_timeout_s` | — | `30` | orçamento para a conexão inicial |
| `enabled` | — | `true` | defina `false` para manter a entrada mas pular a conexão |

Valores de string em `command`, `args`, `env` e `url` interpolam `${VAR}` a partir do
ambiente (uma variável não definida vira uma string vazia com um aviso) — mantenha
segredos fora do arquivo.

> **`command` vs `args`.** O Veles executa o programa diretamente (sem shell), então o
> executável e seus argumentos são campos **separados**. Escreva
> `command = "npx"`, `args = ["-y", "pkg"]` — **não** `command = "npx -y pkg"`.

### stdio (subprocesso local)

```toml
[mcp.servers.github]
transport = "stdio"
command = "npx"
args = ["-y", "@modelcontextprotocol/server-github"]
env = { GITHUB_TOKEN = "${GITHUB_TOKEN}" }
```

Um servidor que você mesmo executa funciona da mesma forma — aponte `command`/`args` para ele:

```toml
[mcp.servers.mytools]
transport = "stdio"
command = "python"
args = ["-m", "my_mcp_server"]
```

### Um servidor que precisa de uma chave de API (context7)

O [Context7](https://context7.com) fornece documentação de bibliotecas atualizada. Passe a
chave como um argumento para que `${VAR}` a mantenha fora do arquivo:

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

> **Sem cabeçalhos personalizados (ainda).** Os transportes `http`/`sse` enviam apenas a `url` —
> o Veles não consegue anexar um cabeçalho `Authorization`. Para um servidor remoto que precisa de uma
> chave, prefira a variante `stdio` dele (ex.: `npx`) com a chave em `args`/`env`, ou um
> endpoint que aceite a chave na URL.

## Ocultar ferramentas específicas

Defina `[mcp] disabled_tools` — uma tabela que mapeia cada servidor aos nomes das ferramentas a serem puladas:

```toml
[mcp]
disabled_tools = { github = ["delete_repository"], search = ["raw_query"] }
```

## Inspecionar e testar

```bash
veles mcp list              # every configured server: transport, status, tool count
veles mcp test github       # connect to one server and list its tools
```

`veles mcp list` sempre sai com 0 — é um inspetor, não um portão de saúde.
`veles mcp test` sai com 1 quando a conexão falha e com 2 para um nome de servidor desconhecido.

## Como as ferramentas aparecem

Uma vez configurados, os servidores são montados **automaticamente** no próximo `veles run` /
TUI / início do daemon — não há uma flag separada de "habilitar MCP"; a presença da
configuração é o interruptor. Cada ferramenta entra no registro normal como `mcp_<server>_<tool>`
e pode ser chamada pelo agente como qualquer ferramenta nativa. Os schemas são higienizados (limites de nome/tamanho,
remoção de caracteres de controle) para que um servidor não confiável não consiga injetar conteúdo no prompt.
As dicas de ferramenta mapeiam para a escada de confiança: ferramentas destrutivas sempre confirmam, ferramentas somente leitura
são executadas sem pergunta, e tudo o mais passa pelo fluxo usual de
[confiança](security-and-permissions.md) — conceda aprovação permanente com
`veles trust set` se você não quiser ser perguntado a cada vez.

## Tratamento de falhas

Um servidor que falha ao conectar — um `command` ausente, uma `url` inválida ou qualquer entrada
inválida — é registrado como um aviso e pulado. Ele nunca bloqueia a inicialização ou o agente.
Execute novamente `veles mcp list` para ver o status e o erro.

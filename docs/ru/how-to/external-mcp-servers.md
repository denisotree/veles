# Как подключать внешние MCP-серверы

> 🌐 **Языки:** [English](../../en/how-to/external-mcp-servers.md) · **Русский**

Veles — это [MCP](https://modelcontextprotocol.io/)-**клиент**: он может
подключаться к внешним MCP-серверам и предоставлять их инструменты агенту так, как
будто они встроенные (GitHub, веб-поиск, ваши собственные сервисы, …).

## Настройка сервера

Добавьте блок `[mcp.servers.<name>]` в `<project>/.veles/config.toml` (или в
пользовательский глобальный `~/.veles/config.toml`). Поддерживаются три транспорта:
`stdio`, `http`, `sse`.

```toml
[mcp.servers.github]
transport = "stdio"
command = "npx -y @modelcontextprotocol/server-github"
env = { GITHUB_TOKEN = "${GITHUB_TOKEN}" }   # ${VAR} interpolates from the environment
enabled = true

[mcp.servers.search]
transport = "http"
url = "http://localhost:3000/mcp"
```

Чтобы скрыть отдельные инструменты сервера, используйте
`[mcp] disabled_tools = ["..."]`.

## Просмотр и проверка

```bash
veles mcp list                  # configured servers, connection status, tool counts
veles mcp test github           # connect to one server and list its tools
```

## Как появляются инструменты

Инструменты подключённого сервера попадают в обычный реестр инструментов как
`mcp_<server>_<tool>` и вызываются агентом как любой встроенный. Их схемы
санитизируются (ограничения имени/длины, удаление управляющих символов), чтобы
недоверенный сервер не мог внедриться в промпт. Подсказки инструментов
отображаются на лестницу доверия: деструктивные инструменты всегда требуют
подтверждения, инструменты только для чтения запускаются без запроса, остальные
проходят обычный поток [доверия](security-and-permissions.md).

## Обработка сбоев

Сервер, к которому не удалось подключиться, логируется как предупреждение и
пропускается — он никогда не блокирует запуск или агента. Перезапустите
`veles mcp list`, чтобы увидеть статус.

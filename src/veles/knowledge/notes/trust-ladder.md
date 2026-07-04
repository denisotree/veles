---
title: Grant trust for sensitive tools
topics: [trust, permission, grant, sensitive, tool, autopilot]
related: ["cmd:trust", "cmd:autopilot"]
---

Use `veles trust {list,set,revoke,clear}` to manage standing permission
grants for sensitive tools, so the agent doesn't prompt for approval every
time it wants to use one.

`veles trust list` shows grants from both user and project scopes; `veles
trust set <tool>` grants one without an interactive prompt; `veles trust
revoke <tool>` removes it. For a temporary blanket bypass instead of
per-tool grants, see `veles autopilot enable --until +30m`.

Example: `veles trust set write_file`.

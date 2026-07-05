---
title: Run the daemon and chat channels
topics: [daemon, channel, telegram, gateway, background, token]
related: ["cmd:daemon", "cmd:channel"]
---

Use `veles daemon {start,stop,status,list,restart,delete,session,token}` to
run the persistent HTTP+WS daemon that channels and remote clients talk to.
`veles daemon start` detaches by default (`--foreground` keeps it attached).

Use `veles channel {run,list,list-sessions,reset-session,add,remove}` to
attach and run an external chat gateway (e.g. Telegram) against a running
daemon session.

Example: `veles daemon start` then `veles channel run --channel telegram`.

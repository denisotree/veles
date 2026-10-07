---
title: Run the daemon and chat channels
topics: [daemon, channel, telegram, gateway, background, token, platform, module]
related: ["cmd:daemon", "cmd:channel"]
---

Use `veles daemon {start,stop,status,list,restart,delete,session,token}` to
run the persistent HTTP+WS daemon that channels and remote clients talk to.
`veles daemon start` detaches by default (`--foreground` keeps it attached).
A daemon starts only with at least one ready channel (module installed,
secrets in place); otherwise it offers to connect one at a terminal, or
refuses and prints the command to run.

Channel platforms (Telegram, …) are modules from the extension registry,
not part of core. Use `veles channel add --channel telegram` to install and
configure one (the token goes to the keychain); a `[channels.telegram]` block
in config installs the module on the next `veles daemon start`.

Use `veles channel {run,list,list-sessions,reset-session,add,remove}` to
attach and run an external chat gateway against a running daemon session.

Example: `veles channel add --channel telegram` then `veles daemon start`.

Output daemon-setup.gif

Set Shell "zsh"
Set FontSize 18
Set Width 1200
Set Height 720
Set Padding 20
Set WindowBar Colorful
Set Theme "Catppuccin Mocha"
Set TypingSpeed 55ms
Set PlaybackSpeed 1.2

# Bring a daemon + channel up from scratch. In a fresh project directory,
# `veles daemon start` runs the project wizard, then the registry-driven
# channel step (pick a channel TYPE first, then configure it), then starts the
# daemon — no need to open the TUI and type /daemon.
Type "veles daemon start --port 8799" Enter
Sleep 3.5s

# Layout picker (llm-wiki is the default) → accept.
Enter
Sleep 1.5s

# Initialize this directory as a Veles project? → yes.
Type "y"
Sleep 1.5s

# Pin a project-specific provider/model? → no (inherit user config).
Type "n"
Sleep 1.2s

# Seed wiki/sources/ from existing docs? → no.
Type "n"
Sleep 1.2s

# Run this project as a long-lived daemon? → yes.
Type "y"
Sleep 1.5s

# Daemon host → default 127.0.0.1.
Enter
Sleep 1s
# Daemon port.
Type "8799"
Sleep 400ms
Enter
Sleep 1.5s

# Connect a chat channel? → yes.
Type "y"
Sleep 2s

# Channel TYPE first — Telegram is the only registered platform today, but the
# picker is the seam any new channel registers on. Accept Telegram.
Enter
Sleep 2.2s

# Now the channel-specific fields. Telegram bot token (masked).
Type "123456:FAKE-demo-bot-token"
Sleep 700ms
Enter
Sleep 1.5s

# Allowed chat ids (whitelist; blank = allow all).
Type "424242"
Sleep 700ms
Enter
Sleep 2.5s

# Recap → close the wizard; the daemon spins up.
Enter
Sleep 4.5s

# It's live — confirm.
Type "veles daemon status" Enter
Sleep 3.5s

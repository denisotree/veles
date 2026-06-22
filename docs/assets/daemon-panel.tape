Output daemon-panel.gif

Set Shell "zsh"
Set FontSize 18
Set Width 1200
Set Height 720
Set Padding 20
Set WindowBar Colorful
Set Theme "Catppuccin Mocha"
Set TypingSpeed 55ms
Set PlaybackSpeed 1.2

# Bare `veles daemon` opens the control panel: a tree of project → daemons →
# channels, with start/stop/restart/delete and channel add/remove inline.
Type "veles daemon" Enter
Sleep 4s

# The cursor lands on the running daemon. Channels are managed right here —
# `c` opens the same registry-driven add-channel flow (channel type first).
Type "c"
Sleep 2.5s
Escape
Sleep 1.6s

# Walk down to the telegram channel leaf under the daemon.
Down
Sleep 2.2s

# Footer lists the keys: (s)tart (t)op (r)estart (d)elete (c)hannel (q)uit.
Type "q"
Sleep 1.5s

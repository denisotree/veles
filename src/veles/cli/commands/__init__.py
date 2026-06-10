"""Per-verb command implementations.

Each module here owns one top-level CLI verb's `_cmd_*` body
function(s). The argparse subparser definitions stay in the package's
`__init__._build_parser` (monolithic for now); only command bodies move
out to keep the entrypoint thin and prepare for Tier-gamma command
additions (M47 wizard, M48 TUI, M51 daemon, etc.) without continuing
to bloat `cli/__init__.py`.

Backward compatibility: `veles.cli` re-exports each `_cmd_*` so tests
that monkey-patch `veles.cli._foo` continue to work where the lookup
side stays in `cli/__init__.py`. New code should import directly from
the per-verb module.
"""

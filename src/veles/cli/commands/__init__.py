"""Per-verb command implementations.

Each module owns one top-level CLI verb's `cmd_*` function; the argparse
definitions live in `veles.cli._parsers`, and `veles.cli.main` imports the
module for the verb being run only.
"""

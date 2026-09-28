"""Parser for `veles registry …` — connect, search, install and publish extensions."""

from __future__ import annotations

import argparse

from veles.cli._parsers._common import add_project_root_flag


def register(sub: argparse._SubParsersAction) -> None:
    reg = sub.add_parser("registry", help="Extension registries: search, install, publish.")
    add_project_root_flag(reg)
    rs = reg.add_subparsers(dest="registry_command", required=True)

    p = rs.add_parser("add", help="Connect a registry (git URL). Unnamed → 'private'.")
    p.add_argument("url")
    p.add_argument("--name", default=None)
    p.add_argument("--ref", default=None, help="Branch to follow (default: the remote HEAD).")
    p = rs.add_parser("remove", help="Disconnect a registry and drop its cache.")
    p.add_argument("name")
    rs.add_parser("list", help="Connected registries.")
    p = rs.add_parser("update", help="Fetch the latest registry contents.")
    p.add_argument("name", nargs="?")

    p = rs.add_parser("search", help="Search connected registries.")
    p.add_argument("query", nargs="?", default="")
    p.add_argument("--kind", choices=("module", "skill", "layout", "mcp"))
    p.add_argument("--registry", default=None)
    p.add_argument("--json", action="store_true")

    p = rs.add_parser("install", help="Install <name> or <registry>:<name>.")
    p.add_argument("spec")
    p.add_argument("--user", action="store_true", help="Skills: install for all projects.")
    p.add_argument("--force", action="store_true", help="Install even if yanked.")
    p = rs.add_parser("upgrade", help="Upgrade one or all installed extensions.")
    p.add_argument("name", nargs="?")
    p = rs.add_parser("uninstall", help="Remove an installed extension.")
    p.add_argument("name")
    rs.add_parser("verify", help="Check installed extensions for drift, yanks and updates.")

    p = rs.add_parser("validate", help="Run a registry's CI checks locally.")
    p.add_argument("path", nargs="?", default=".")
    p.add_argument("--base", default=None, help="Only extensions changed since this git ref.")
    p.add_argument("--report", default=None, help="Write the Markdown report to this file.")
    p.add_argument(
        "--run-code",
        action="store_true",
        help="Also import modules and run their tests (CI only — executes the PR's code).",
    )
    p = rs.add_parser("scaffold", help="Create a new extension skeleton in a registry.")
    p.add_argument("kind", choices=("module", "skill", "layout", "mcp"))
    p.add_argument("name")
    p.add_argument("--group", default="internal")
    p.add_argument("--root", default=".")
    p = rs.add_parser("init", help="Create a new registry from the template.")
    p.add_argument("dir")
    p.add_argument("--name", required=True)
    p.add_argument("--ci", choices=("github", "gitlab", "none"), default="github")
    p.add_argument(
        "--public", action="store_true", help="Public registry: permissive licences only."
    )
    p = rs.add_parser("vendor", help="Copy an extension into another registry you maintain.")
    p.add_argument("spec")
    p.add_argument("--into", required=True)
    p.add_argument("--group", default="vendor")

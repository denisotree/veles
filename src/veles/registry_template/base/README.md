# @@NAME@@ — Veles extension registry

Reviewed modules, skills, layout packs and MCP recipes for Veles.

## Connect

    veles registry add <this repository's git URL>      # becomes "private"
    veles registry search
    veles registry install private:<name>

Access follows your git permissions (SSH key or `gh auth setup-git`).

## Publish

1. `veles registry scaffold <module|skill|layout|mcp> <name> --group internal`
2. `veles registry validate .` — the same checks CI runs
3. Open a pull request. A merge after review publishes it.

To ship a new version, change the files and raise `version` in `extension.toml`.
To withdraw one, add `yanked = "reason"` to its `[extension]` table.

## Set up (once)

- Put your reviewers into `.github/CODEOWNERS`.
- Protect the default branch: require the `validate` check and a Code Owner review.

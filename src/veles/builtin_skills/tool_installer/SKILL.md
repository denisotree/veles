---
name: tool_installer
description: Read a user-supplied python file or executable, copy it into the project's tool directory, and register it in the catalogue
tools: [read_file, write_file, advisor_review]
parameters:
  - name: source_path
    type: string
    description: absolute or project-relative path to a .py file or executable the user wants installed as a tool
  - name: tool_name
    type: string
    description: kebab-or-snake-case name the tool will register under (optional; default derived from filename)
---

You install a user-supplied python tool into the active project. The
input is a path the user pointed at; the output is a file at
`<project>/.veles/tools/<tool_name>.py` that the next bootstrap
discovers automatically.

## Process

1. **Read the source file.** Use `read_file` on `source_path`. If the
   path doesn't exist or isn't a `.py` file (or `.py.txt` template),
   refuse and ask the user for a clarifying path. Don't try to
   install binaries here — that's a separate `tool_installer_binary`
   skill not in this build.

2. **Inspect the code.** Read it end-to-end. Refuse to install when:
   - the file calls dangerous shell-execution APIs without a timeout
     or with arbitrary user input — that's a flag for review.
   - the file imports / references network endpoints not declared in
     a top-level constant the user can audit.
   - the file mutates global state at import time (writing to disk,
     hitting the network, modifying environment variables).

   If any of those fire, summarise the concern to the user and stop.
   The user can edit the source file and re-invoke the skill.

   Then **run `advisor_review` on the file contents (mandatory)** with
   an explicit ask: "Review this user-supplied Veles tool for safety —
   shell execution, undeclared network/env access, import-time side
   effects, silent error-swallowing." If the verdict raises concerns,
   summarise them and stop (the user edits + re-invokes); never install
   a file the advisor flagged. If the advisor is unavailable
   (`<advisor unavailable: …>`), say so and proceed only after restating
   the manual checks above. Quote the verdict in your final message.

3. **Pick the tool name.** Default: derive from the source filename
   (`my_tool.py` → `my_tool`). If `tool_name` was supplied, use it
   verbatim. Validate: lowercase, kebab- or snake_case, no path
   separators, no spaces.

4. **Check for collisions.** Use `read_file` on
   `<project>/.veles/tools/<tool_name>.py`. If it exists, refuse and
   propose a renamed installation.

5. **Copy and adapt.** Write the file to
   `<project>/.veles/tools/<tool_name>.py` via `write_file`. Two
   adaptations as you copy:
   - Ensure the module imports `from veles.core.tools.registry import
     tool` and the top-level function is decorated with `@tool()`.
     If the user's file is a plain function without the decorator,
     wrap it: add the import and the decorator, but keep the body
     unchanged.
   - Add a `# installed via tool_installer skill on <ISO date>` line
     at the top so users can find the entry point later.

6. **Confirm.** Print to the user:
   - "Installed `<tool_name>` from `<source_path>`."
   - "Run `veles tool show <tool_name>` to verify the catalogue entry."
   - "Run `veles tool promote <tool_name>` if you want every project
     to see it."

You do **not** delete the original `source_path`. The user supplied
it; they decide what to do with the original copy.

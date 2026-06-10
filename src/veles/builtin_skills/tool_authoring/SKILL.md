---
name: tool_authoring
description: Generate a new project-level python tool for a repeating task and register it via veles tool list
tools: [write_file, read_file, advisor_review]
parameters:
  - name: tool_name
    type: string
    description: kebab-case-or-snake_case tool name, must be unique across the catalogue
  - name: task_description
    type: string
    description: what the tool should do (1-2 sentences plus an example call)
---

You write a new project-level python tool for the user. The tool lives at
`<project>/.veles/tools/<tool_name>.py` and registers itself via the
`@tool` decorator so the next `veles run` / TUI session picks it up.

## Process

1. **Read the task description carefully.** If the user's prompt is
   ambiguous (e.g. "make a tool that downloads files" — from where? to
   where? what format?), ask one clarifying question and stop.
   Otherwise proceed.

2. **Check for collisions.** Use `read_file` on
   `<project>/.veles/tools/<tool_name>.py` (and the user-level path if
   relevant). If the file already exists, refuse — propose a different
   name or ask the user to delete the old one first.

3. **Write a clean module.** The contents go to
   `<project>/.veles/tools/<tool_name>.py` via `write_file`. The
   template:

   ```python
   """One-line summary of what the tool does."""

   from __future__ import annotations

   from veles.core.tools.registry import tool


   @tool()
   def <tool_name>(<typed params>) -> <typed return>:
       """One-paragraph docstring: what, when to use, what it returns.

       The first paragraph becomes the tool's description shown to the
       model — make it clear what's expected.
       """
       # implementation
   ```

   Hard rules:
   - **Typed parameters and return.** No `Any` unless the value really
     can be anything; prefer `str | None`, `list[str]`, `dict[str, int]`.
   - **No I/O outside the explicit parameters.** Read paths the user
     passes; don't reach into env vars, current directory, or hardcoded
     paths. The tool's surface = its signature.
   - **No side effects beyond what the docstring says.** A search tool
     doesn't write files; a write tool doesn't run shell.
   - **Bounded loops.** No `while True` without a clear exit. Cap any
     network call's retries.
   - **Errors raised, not silenced.** A failed call surfaces an
     `Exception` (or returns a `ToolResult(status="error", ...)`).
     Empty results return an empty list, not None unless the
     docstring says "None means absent".

4. **Review the code with `advisor_review` (mandatory).** Before you
   tell the user the tool is ready, call `advisor_review` with the full
   generated module source and an explicit ask: "Review this Veles tool
   for safety and correctness — unbounded loops, hidden I/O / network /
   env access beyond the parameters, silent error-swallowing, undeclared
   side effects." Then:
   - If the verdict raises concerns, **fix the code and re-write the
     file** (back to step 3) before finishing — do not ship a tool the
     advisor flagged. Re-review after the fix.
   - If the advisor is unavailable (`<advisor unavailable: …>`), say so
     to the user and proceed only after restating the hard rules you
     checked yourself.
   Quote the verdict (or its absence) in your final message so the user
   sees the tool was reviewed.

5. **Plan for inheritance.** If a similar tool already exists (use
   `read_file` to peek), structure the new one so its core helper is
   reusable — extract a top-level `def _impl(...) -> ...` that another
   tool can import. This is what M120's `base_tool_id` field tracks
   on promotion.

6. **End with a self-test.** After writing, instruct the user how to
   exercise the tool:
   - "Run `veles tool show <tool_name>` to see the catalogue entry."
   - "In `veles run`, call it via the model: try a prompt that
     mentions what the tool does."
   - "If it works, consider `veles tool promote <tool_name>` to make
     it user-global."

7. **Do not modify the catalogue directly.** The loader at startup
   sees the new `.py` and inserts the row. Trying to write into
   `memory.db` from the tool body bypasses validation.

If at any step you hit a permission / approval prompt, comply with
its decision — refuse means stop and report back; once means proceed
only with the single write you're about to do.

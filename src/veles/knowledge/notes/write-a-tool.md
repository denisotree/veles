---
title: Author a Veles tool
topics: [tool, authoring, decorator, approve, tool_authoring]
related: ["skill:tool_authoring", "cmd:tool"]
---

A Veles tool is a python function decorated with `@tool()` in
`<project>/.veles/tools/<name>.py` (or `~/.veles/tools/` for every project).
The easiest way is the `tool_authoring` skill — call it instead of writing the
file by hand; it follows this contract and has the code reviewed.

The contract:

- `from veles.core.tools.registry import tool`, then `@tool()` on a top-level
  function. A file with no `@tool` function registers nothing, and a file
  whose name starts with `_` is not loaded at all.
- Type annotations become the JSON schema of the arguments; the first
  paragraph of the docstring is the description the model sees.
- Return a `str`. Longer than `max_result_chars` (8000 by default) is saved to
  `.veles/artifacts/` and replaced by a preview — aggregate in the tool.
- `@tool(timeout_s=…)` is advisory; bound slow work inside the function.
- **It loads only after a human approves it**: `veles tool approve <name>`
  (the agent cannot do this itself). Every edit needs approving again.

Example:

```python
from veles.core.tools.registry import tool


@tool()
def word_freq(path: str, top: int = 10) -> str:
    """Top-N most frequent words of a file, one `word:count` per line."""
    ...
```

Then `veles tool approve word_freq` and `veles tool show word_freq`.

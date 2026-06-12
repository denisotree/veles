"""Pack-driven project scaffolding (M162).

`veles init` used to hardcode the Karpathy wiki skeleton
(`Wiki.ensure_layout()` + a wiki-centric AGENTS.md) regardless of the
chosen layout pack. `apply_scaffold` makes the pack the owner:

- `[layout.scaffold].dirs` are created under the project root,
- AGENTS.md comes from the pack's `agents_md_template` (with `{name}`
  substituted) or falls back to core's layout-agnostic default,
- the wiki tree is created only when the pack activates the `wiki`
  engine (`[layout.engines] wiki = true`).

A missing pack degrades to the bare minimum (default AGENTS.md, no
content dirs) — the project memory in `.veles/` works regardless.
"""

from __future__ import annotations

import sys
from pathlib import Path

from veles.core.layout.discovery import LayoutDirectory


def apply_scaffold(
    pack: LayoutDirectory | None, root: Path, name: str
) -> None:
    """Create the user-content skeleton the pack declares.

    Idempotent: existing dirs are kept, an existing AGENTS.md is never
    overwritten."""
    if pack is not None:
        for rel in pack.manifest.scaffold_dirs:
            (root / rel).mkdir(parents=True, exist_ok=True)
        if pack.manifest.engine_enabled("wiki"):
            from veles.core.wiki import Wiki

            Wiki(root).ensure_layout()

    agents_md = root / "AGENTS.md"
    if not agents_md.exists():
        agents_md.write_text(_render_agents_md(pack, name), encoding="utf-8")


def _render_agents_md(pack: LayoutDirectory | None, name: str) -> str:
    from veles.core.agents_md_schema import default_template

    if pack is None or pack.manifest.agents_md_template is None:
        return default_template(name)
    template_path = pack.root / pack.manifest.agents_md_template
    try:
        template = template_path.read_text(encoding="utf-8")
    except OSError as exc:
        print(
            f"warning: layout pack {pack.manifest.name!r} declares "
            f"agents_md_template but {template_path} is unreadable ({exc}); "
            "using the default template",
            file=sys.stderr,
        )
        return default_template(name)
    # Plain replace, not str.format — markdown is full of literal braces.
    return template.replace("{name}", name)


__all__ = ["apply_scaffold"]

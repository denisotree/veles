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


def apply_scaffold(pack: LayoutDirectory | None, root: Path, name: str) -> None:
    """Create the user-content skeleton the pack declares.

    Idempotent and content-preserving: existing dirs are kept and a
    *customised* AGENTS.md is never overwritten. The one exception (M181):
    if AGENTS.md is still the unmodified scaffold default but its `# ` title
    names a different project, the directory was copied/renamed from another
    project (e.g. `cp -R old new && cd new && veles init`) and the stale
    title would otherwise leak the wrong identity into the system prompt — so
    it's regenerated for the new name. A default whose title already matches,
    or any file the user has edited, is left untouched."""
    from veles.core.agents_md_schema import is_default_template, title_of

    if pack is not None:
        for rel in pack.manifest.scaffold_dirs:
            (root / rel).mkdir(parents=True, exist_ok=True)
        if pack.manifest.engine_enabled("wiki"):
            from veles.modules.wiki.wiki import Wiki

            Wiki(root).ensure_layout()

    agents_md = root / "AGENTS.md"
    if not agents_md.exists():
        agents_md.write_text(_render_agents_md(pack, name), encoding="utf-8")
        return
    existing = agents_md.read_text(encoding="utf-8", errors="replace")
    if is_default_template(existing) and title_of(existing) not in (None, name):
        agents_md.write_text(_render_agents_md(pack, name), encoding="utf-8")
        print(
            f"note: regenerated a stale default AGENTS.md (was titled "
            f"'# {title_of(existing)}', now '# {name}') — looked copied from "
            "another project",
            file=sys.stderr,
        )


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

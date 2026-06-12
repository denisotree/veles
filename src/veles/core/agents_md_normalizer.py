"""M96: detect + merge AGENTS.md / CLAUDE.md / GEMINI.md into one.

Conventional Veles project layout is: `AGENTS.md` is the single source
of truth, `CLAUDE.md` and `GEMINI.md` are symlinks pointing to it. When
a project already has any of these as real files (e.g. the user
imported a Claude Code project), the wizard's normalization step
offers to merge them and replace the redundant copies.

Public entry points:
    scan_for_context_files(root)      -> ScanResult
    llm_merge(provider, model, files) -> str   # uses one cheap LLM call
    deterministic_merge(files)        -> str   # offline fallback
    apply_merge(root, merged_text, mode='symlink'|'delete'|'backup')

The LLM-merge route is preferred when a working provider is available;
on any failure (no key, network error, parse miss, exception) the
caller falls back to `deterministic_merge`, which concatenates by H2
section with simple de-duplication. The end result must still pass
`agents_md_schema.validate()`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from veles.core.agents_md_schema import RECOMMENDED_SECTIONS, default_template

_CONTEXT_FILES: tuple[str, ...] = ("AGENTS.md", "CLAUDE.md", "GEMINI.md")
_H2_RE = re.compile(r"^\s*##\s+(.+?)\s*$")


@dataclass(slots=True)
class ContextFileInfo:
    name: str
    path: Path
    is_symlink: bool
    size: int
    content: str = ""


@dataclass(slots=True)
class ScanResult:
    files: list[ContextFileInfo] = field(default_factory=list)

    @property
    def conflicting(self) -> list[ContextFileInfo]:
        """Real files (not symlinks). Two-or-more conflicting = needs merge."""
        return [f for f in self.files if not f.is_symlink]

    @property
    def needs_merge(self) -> bool:
        return len(self.conflicting) >= 2


def scan_for_context_files(root: Path) -> ScanResult:
    """Inspect AGENTS.md / CLAUDE.md / GEMINI.md in `root`. Reads file
    bodies for the conflicting ones so the merge step doesn't re-do I/O."""
    result = ScanResult()
    for name in _CONTEXT_FILES:
        p = root / name
        try:
            exists = p.exists()
        except OSError:
            continue
        if not exists:
            continue
        is_symlink = p.is_symlink()
        try:
            size = p.stat().st_size
        except OSError:
            size = 0
        info = ContextFileInfo(name=name, path=p, is_symlink=is_symlink, size=size)
        if not is_symlink:
            try:
                info.content = p.read_text(encoding="utf-8", errors="replace")
            except OSError:
                info.content = ""
        result.files.append(info)
    return result


# ---------------- merge implementations ----------------


_MERGE_SYSTEM_PROMPT = (
    "You are merging two or three project-context markdown files into a single"
    " canonical `AGENTS.md`. Preserve every unique fact; de-duplicate overlapping"
    " statements; keep the H2 section structure (`## Layout`, `## Conventions`,"
    " `## Workflows`); add other custom H2 sections if the source files have"
    " them. Output ONLY the merged markdown — no preamble, no closing notes."
)


def llm_merge(
    *,
    provider: object,  # veles.core.provider.Provider
    model: str,
    files: list[ContextFileInfo],
    project_name: str,
    max_tokens: int = 4096,
) -> str:
    """Run a single tool-less LLM turn that merges `files` into one
    AGENTS.md body. Raises on any failure; callers should fall back to
    `deterministic_merge`."""
    from veles.core.agent import Agent
    from veles.core.tools.registry import Registry

    blocks: list[str] = [
        f"Project name: {project_name}",
        "",
        "Source files to merge:",
    ]
    for f in files:
        blocks.append(f'\n<file path="{f.name}">\n{f.content}\n</file>')

    sub = Agent(
        provider=provider,  # type: ignore[arg-type]
        registry=Registry(),
        model=model,
        max_iterations=1,
        system_prompt=_MERGE_SYSTEM_PROMPT,
        max_tokens=max_tokens,
    )
    result = sub.run("\n".join(blocks))
    text = (result.text or "").strip()
    if not text:
        raise RuntimeError("LLM merge returned empty body")
    return text


def deterministic_merge(files: list[ContextFileInfo], *, project_name: str = "Project") -> str:
    """Offline fallback. Walks each file, splits on H2, concatenates by
    section name preserving first-seen order. Duplicate H2 names dedupe
    body lines (case-sensitive). Sections start with `## <name>`.

    Missing standard sections (Layout / Conventions / Workflows) are
    filled from the canonical template so the result passes `validate()`.
    """
    sections: dict[str, list[str]] = {}
    order: list[str] = []
    # Preserve the first H1 we see, otherwise fall back to project_name.
    h1: str | None = None

    for f in files:
        if not f.content:
            continue
        if h1 is None:
            for line in f.content.splitlines():
                if line.startswith("# ") and not line.startswith("## "):
                    h1 = line[2:].strip()
                    break
        # Split by H2.
        current_name: str | None = None
        current_buf: list[str] = []

        def _flush(name: str | None, buf: list[str]) -> None:
            if name is None:
                return
            existing = sections.setdefault(name, [])
            if name not in order:
                order.append(name)
            # Dedupe body lines while preserving order.
            seen = {line for line in existing}
            for line in buf:
                if line in seen:
                    continue
                existing.append(line)
                seen.add(line)

        for raw in f.content.splitlines():
            m = _H2_RE.match(raw)
            if m:
                _flush(current_name, current_buf)
                current_name = m.group(1)
                current_buf = []
                continue
            if current_name is None:
                continue  # ignore pre-H2 prose (we keep only sectioned content)
            current_buf.append(raw.rstrip())
        _flush(current_name, current_buf)

    if h1 is None:
        h1 = project_name

    # Fill missing recommended sections from the canonical template so the
    # output validates without manual editing.
    template = default_template(h1)
    template_sections = _split_template_sections(template)
    for required in RECOMMENDED_SECTIONS:
        if required not in sections:
            sections[required] = template_sections.get(required, [])
            if required not in order:
                order.append(required)

    rendered: list[str] = [f"# {h1}", ""]
    for name in order:
        rendered.append(f"## {name}")
        body = sections.get(name) or []
        # Trim leading/trailing blank lines.
        while body and not body[0].strip():
            body.pop(0)
        while body and not body[-1].strip():
            body.pop()
        rendered.extend(body)
        rendered.append("")
    return "\n".join(rendered).rstrip() + "\n"


def _split_template_sections(template: str) -> dict[str, list[str]]:
    """Parse `default_template` output into {section_name: [lines]}."""
    out: dict[str, list[str]] = {}
    current: str | None = None
    buf: list[str] = []
    for raw in template.splitlines():
        m = _H2_RE.match(raw)
        if m:
            if current is not None:
                out[current] = buf
            current = m.group(1)
            buf = []
            continue
        if current is None:
            continue
        buf.append(raw.rstrip())
    if current is not None:
        out[current] = buf
    return out


# ---------------- apply ----------------


def apply_merge(
    root: Path,
    merged_text: str,
    *,
    originals: list[ContextFileInfo],
    mode: str = "symlink",
) -> dict[str, str]:
    """Write `merged_text` to `<root>/AGENTS.md` and reconcile the
    original CLAUDE.md / GEMINI.md according to `mode`:

      - "symlink": replace originals with relative symlinks to AGENTS.md
      - "delete": remove originals outright
      - "backup": move originals to `<name>.bak`

    Returns {filename: action} so the caller can recap. Best-effort:
    OS errors per-file are recorded as `"failed: <msg>"`."""
    if mode not in ("symlink", "delete", "backup"):
        raise ValueError(f"unknown mode {mode!r}")
    agents = root / "AGENTS.md"
    agents.write_text(merged_text, encoding="utf-8")
    actions: dict[str, str] = {"AGENTS.md": "rewritten"}
    for f in originals:
        if f.name == "AGENTS.md":
            continue
        target = root / f.name
        try:
            if mode == "delete":
                target.unlink()
                actions[f.name] = "deleted"
            elif mode == "backup":
                target.rename(target.with_suffix(target.suffix + ".bak"))
                actions[f.name] = f"backed-up to {f.name}.bak"
            else:  # symlink
                target.unlink()
                target.symlink_to("AGENTS.md")
                actions[f.name] = "symlinked to AGENTS.md"
        except OSError as exc:
            actions[f.name] = f"failed: {exc}"
    return actions


__all__ = [
    "ContextFileInfo",
    "ScanResult",
    "apply_merge",
    "deterministic_merge",
    "llm_merge",
    "scan_for_context_files",
]

"""Bring an existing CLAUDE.md / GEMINI.md into AGENTS.md (M96, wired in M272).

Conventional Veles project layout is: `AGENTS.md` is the single source
of truth, `CLAUDE.md` and `GEMINI.md` are symlinks pointing to it. When
a project already has one of these as a real file (a Claude Code project
being brought into Veles), `init_project` imports it into AGENTS.md —
the agent reads only AGENTS.md — and keeps the original as `<name>.bak`.

Public entry points:
    scan_for_context_files(root)          -> ScanResult
    import_context_files(files)           -> str   # lossless, see its docstring
    apply_merge(root, text, originals=…)    -> {file: action}  # originals → .bak

The module shipped in M96 and was never called until M272.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

_CONTEXT_FILES: tuple[str, ...] = ("AGENTS.md", "CLAUDE.md", "GEMINI.md")


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


# ---------------- import ----------------


def import_context_files(files: list[ContextFileInfo]) -> str:
    """AGENTS.md body built from existing CLAUDE.md / GEMINI.md — **losslessly**.

    M272: `veles init` in a Claude Code project used to leave CLAUDE.md alone
    and write a template AGENTS.md, and since the agent reads only AGENTS.md,
    the user's instructions were silently not loaded. The obvious fix was the
    module's own `deterministic_merge` — measured on a realistic CLAUDE.md it
    was destructive: it dropped everything before the first `##` (in the test
    file, the only rule it contained: "Always answer in French"), and its
    per-section line de-duplication removed repeated lines, including blank
    lines and the second code block's ``` fences, so fenced code spilled into
    prose. It and the unusable-at-init `llm_merge` were removed.

    So: the first file verbatim; a second one, if it says something
    different, verbatim under its own heading. Nothing is de-duplicated or
    re-ordered — a stray repeat is cheap, a lost rule is the bug. The
    originals are also kept byte for byte as `.bak` by `apply_merge`."""
    real = [f for f in files if not f.is_symlink and f.content.strip()]
    if not real:
        return ""
    first, *rest = real
    parts = [first.content.rstrip() + "\n"]
    for f in rest:
        if f.content.strip() == first.content.strip():
            continue
        parts.append(f"\n## Imported from {f.name}\n\n{f.content.rstrip()}\n")
    return "".join(parts)


# ---------------- apply ----------------


def _free_backup_path(target: Path) -> Path:
    """`CLAUDE.md.bak`, or `CLAUDE.md.bak.1`, `.2`, … — never an existing file.

    `Path.rename` silently replaces an existing target on POSIX, so a plain
    `.bak` would overwrite a backup the user already had."""
    candidate = target.with_name(target.name + ".bak")
    n = 1
    while candidate.exists() or candidate.is_symlink():
        candidate = target.with_name(f"{target.name}.bak.{n}")
        n += 1
    return candidate


def apply_merge(
    root: Path, merged_text: str, *, originals: list[ContextFileInfo]
) -> dict[str, str]:
    """Write `merged_text` to `<root>/AGENTS.md` and move each original
    CLAUDE.md / GEMINI.md aside to a backup, so `init_project` can put the
    AGENTS.md symlink in its place.

    Backup only. The M96 version also offered "delete" (remove the original
    outright) and "symlink" (replace it in place); nothing ever called them,
    and the first destroys the only copy of what was imported. Returns
    {filename: action} for the caller's recap. An OS error on one file is
    recorded as `"failed: <msg>"` and leaves that original in place."""
    (root / "AGENTS.md").write_text(merged_text, encoding="utf-8")
    actions: dict[str, str] = {"AGENTS.md": "written"}
    for f in originals:
        if f.name == "AGENTS.md":
            continue
        target = root / f.name
        backup = _free_backup_path(target)
        try:
            target.rename(backup)
            actions[f.name] = f"kept as {backup.name}"
        except OSError as exc:
            actions[f.name] = f"failed: {exc}"
    return actions


__all__ = [
    "ContextFileInfo",
    "ScanResult",
    "apply_merge",
    "import_context_files",
    "scan_for_context_files",
]

"""M78: enumerate project files for the `@` file picker/reference.

Framework-agnostic — no Textual dependency. Used by the inline REPL's
`@` file completion and (until it's deleted, M187 follow-up) the
Textual `FilePickerScreen`.
"""

from __future__ import annotations

from pathlib import Path

_DEFAULT_FILE_PICKER_EXCLUDES: frozenset[str] = frozenset(
    {".git", ".venv", "venv", "__pycache__", "node_modules", "tmp", "dist", "build"}
)


def iter_project_files(
    root: Path,
    *,
    excludes: frozenset[str] = _DEFAULT_FILE_PICKER_EXCLUDES,
    include_veles_tmp: bool = True,
    cap: int = 5000,
) -> list[Path]:
    """Enumerate files under `root` for the `@` file picker.

    Excludes top-level dirs by name (passed as a set). The `.veles/`
    project state dir is always excluded EXCEPT for `.veles/tmp/`,
    which holds runtime artifacts (clipboard pastes, web fetches) the
    user may want to reference back. Returns paths relative to `root`,
    sorted alphabetically. Caps at `cap` to keep the picker responsive.
    """
    root = root.resolve()
    results: list[Path] = []

    def _walk(dir_path: Path) -> None:
        if len(results) >= cap:
            return
        try:
            entries = sorted(dir_path.iterdir(), key=lambda p: p.name)
        except OSError:
            return
        for entry in entries:
            if len(results) >= cap:
                return
            name = entry.name
            try:
                is_dir = entry.is_dir()
            except OSError:
                continue
            if is_dir:
                if name in excludes:
                    continue
                # Special-case .veles: drop the dir but keep .veles/tmp if asked.
                if name == ".veles":
                    if include_veles_tmp:
                        tmp_dir = entry / "tmp"
                        if tmp_dir.is_dir():
                            _walk(tmp_dir)
                    continue
                _walk(entry)
            else:
                try:
                    results.append(entry.relative_to(root))
                except ValueError:
                    continue

    _walk(root)
    return results

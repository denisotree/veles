"""M204 Phase 1: the batch-ingest KERNEL in `modules/wiki/ingest.py`.

The batch loop moves out of `cli/commands/ingest.py` into the module kernel so
BOTH the CLI (`veles add --recursive`) and the agent-callable `wiki_add` tool
drive the same loop — only `spawn_one` (how one per-file sub-agent is built)
differs per caller. Invariants under test:

- strictly sequential, in listed order (M203 cross-file dedup: file N+1's
  wiki_search must see file N's pages);
- a per-file failure is RECORDED, never raised (one bad file must not kill a
  200-file migration);
- layering: the kernel imports nothing from `veles.cli`.
"""

from __future__ import annotations

from pathlib import Path

from veles.modules.wiki.ingest import (
    BatchIngestResult,
    IngestOutcome,
    batch_ingest_files,
    run_batch_ingest,
)


def test_batch_ingest_files_skips_dot_dirs_and_sorts(tmp_path: Path) -> None:
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "b.md").write_text("b", encoding="utf-8")
    (tmp_path / "docs" / "a.md").write_text("a", encoding="utf-8")
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "config.md").write_text("x", encoding="utf-8")
    (tmp_path / "notes.txt").write_text("t", encoding="utf-8")

    md = batch_ingest_files(tmp_path, "*.md")
    assert [p.name for p in md] == ["a.md", "b.md"]  # sorted; dot-dirs + txt excluded


def test_run_batch_ingest_is_strictly_sequential_in_order(tmp_path: Path) -> None:
    files = [tmp_path / f"{n}.md" for n in ("a", "b", "c")]
    seen: list[str] = []
    wiki_state: set[str] = set()  # stands in for the on-disk wiki

    def spawn_one(path: Path) -> IngestOutcome:
        # Dedup invariant: when file N+1 runs, file N's page is already there.
        if path.name == "b.md":
            assert "a.md" in wiki_state
        if path.name == "c.md":
            assert {"a.md", "b.md"} <= wiki_state
        seen.append(path.name)
        wiki_state.add(path.name)
        return IngestOutcome(source=str(path), ok=True)

    result = run_batch_ingest(files, spawn_one=spawn_one)
    assert seen == ["a.md", "b.md", "c.md"]
    assert result.total == 3 and result.ok == 3 and result.failures == []


def test_run_batch_ingest_records_failure_and_continues(tmp_path: Path) -> None:
    files = [tmp_path / f"{n}.md" for n in ("a", "b", "c")]

    def spawn_one(path: Path) -> IngestOutcome:
        if path.name == "b.md":
            raise RuntimeError("provider blew up")
        return IngestOutcome(source=str(path), ok=True)

    result = run_batch_ingest(files, spawn_one=spawn_one)
    assert result.total == 3
    assert result.ok == 2
    assert len(result.failures) == 1
    src, detail = result.failures[0]
    assert src.endswith("b.md") and "provider blew up" in detail


def test_run_batch_ingest_reports_progress(tmp_path: Path) -> None:
    files = [tmp_path / f"{n}.md" for n in ("a", "b")]
    progress: list[tuple[int, int, str]] = []

    run_batch_ingest(
        files,
        spawn_one=lambda p: IngestOutcome(source=str(p), ok=True),
        on_progress=lambda i, total, path: progress.append((i, total, path.name)),
    )
    assert progress == [(1, 2, "a.md"), (2, 2, "b.md")]


def test_summary_counts_and_failures() -> None:
    ok = BatchIngestResult(total=3, ok=3)
    assert "3" in ok.summary()
    bad = BatchIngestResult(total=3, ok=2, failures=[("x/b.md", "boom")])
    s = bad.summary()
    assert "2" in s and "b.md" in s


def test_kernel_imports_nothing_from_veles_cli() -> None:
    """Layering invariant: the module kernel stays leaf-ward of `veles.cli`."""
    import ast
    import inspect

    import veles.modules.wiki.ingest as kernel

    tree = ast.parse(inspect.getsource(kernel))
    offenders = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            offenders += [a.name for a in node.names if a.name.startswith("veles.cli")]
        elif isinstance(node, ast.ImportFrom) and (node.module or "").startswith("veles.cli"):
            offenders.append(node.module)
    assert offenders == []

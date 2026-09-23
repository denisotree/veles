"""M262 run B — does a known fact stay findable as the corpus grows around it?

Run A (`bench_recall.py`) answers "how fast". It cannot answer "how good":
its vectors are seeded pseudorandom, so the embedding of a question has no
semantic relationship to the embedding of its answer, and a recall@5 measured
there would be noise dressed as a metric.

This one uses real text. The corpus is the project's own documentation, which
is the only real prose the repository actually contains — **165 paragraphs**,
giving 137 probes. That is a small sample and the resolution is coarse (one
probe is worth ~0.7 percentage points); it is enough to see a fact sink, not
enough to argue about a two-point difference. Said here rather than discovered
later from a confident-looking table.

**The probe.** For each page, paragraph *i* is the query and paragraph *i+1*
is the target. They are lexically different and topically adjacent, which is
the closest stand-in for "a question phrased unlike the fact that answers it"
that can be built without a model in the loop. Success is the target landing
in the top 5 of a real `MemoryRouter.recall`, not of a raw SQL query — what
matters is whether the fact reaches the prompt after rerank, truncation and
every other collector competing for the same five slots.

**Padding.** The real corpus is then buried in synthetic rows (the same
generator run A uses) to 10k / 100k / 1M, because the question is not "can it
find this in 164 rows" but "does it still find it in a million".

**The vector half needs a local embedder.** `nomic-embed-text` through ollama,
or any other local adapter. Without one, the run still works and measures the
FTS path alone — and says so, because a recall@5 that silently excludes vector
recall is a different number from the one it looks like.

    uv run python -m tests.bench.bench_precision --sizes 10000,100000

**Run B2 — hit order.** For every probe that found its target, where the
target lands in the rendered block and whether the production truncation
budget removes it. This is the *structural* half of the experiment the plan
called for. The other half — whether a model attends more to the end of the
list, the "lost in the middle" effect — needs a live model and is deliberately
not decided here; measuring position first says whether there is anything to
compare.
"""

from __future__ import annotations

import argparse
import json
import random
import re
import statistics
import time
from dataclasses import asdict, dataclass
from itertools import pairwise
from pathlib import Path

from tests.bench.bench_recall import _DIM, _TOPICS
from tests.bench.bench_recall import seed as seed_synthetic

_MIN_PARAGRAPH_CHARS = 200
_QUERY_CHARS = 180
_TOP_K = 5


@dataclass(frozen=True, slots=True)
class Probe:
    query: str
    target_title: str


@dataclass(frozen=True, slots=True)
class SizeResult:
    rows: int
    probes: int
    recall_at_5: float
    median_position: float | None
    vectors_active: bool


def build_corpus(root: Path) -> list[tuple[str, int, str]]:
    """Paragraphs of the project's own docs: (page, index, text)."""
    files = [*sorted(root.glob("docs/en/**/*.md")), root / "README.md"]
    out: list[tuple[str, int, str]] = []
    for path in files:
        if not path.is_file():
            continue
        page = path.relative_to(root).as_posix()
        idx = 0
        for block in re.split(r"\n\s*\n", path.read_text(encoding="utf-8")):
            text = " ".join(block.split())
            if len(text) < _MIN_PARAGRAPH_CHARS:
                continue
            if text.startswith(("|", "```", "#", "<")):
                continue
            out.append((page, idx, text))
            idx += 1
    return out


def build_probes(corpus: list[tuple[str, int, str]]) -> list[Probe]:
    """Consecutive paragraphs of one page: the earlier asks, the later answers."""
    by_page: dict[str, list[tuple[int, str]]] = {}
    for page, idx, text in corpus:
        by_page.setdefault(page, []).append((idx, text))
    probes: list[Probe] = []
    for page, items in by_page.items():
        items.sort()
        for (_, query), (target_idx, _) in pairwise(items):
            probes.append(Probe(query=query[:_QUERY_CHARS], target_title=_title(page, target_idx)))
    return probes


def _title(page: str, idx: int) -> str:
    return f"{page}#{idx}"


def seed_real(db_path: Path, corpus: list[tuple[str, int, str]]) -> None:
    from veles.core.memory import SessionStore

    store = SessionStore(db_path)
    try:
        with store._conn:
            store._conn.executemany(
                "INSERT INTO insights(title, body, category, created_at) VALUES (?, ?, 'docs', ?)",
                [(_title(page, idx), text, time.time()) for page, idx, text in corpus],
            )
    finally:
        store.close()


def embed_corpus(project) -> bool:  # type: ignore[no-untyped-def]
    """Embed every insight through the LOCAL adapter. False when there is none —
    the run then measures the FTS path alone."""
    from veles.core.memory.insight_embeddings import backfill_insight_embeddings
    from veles.core.memory.store import local_connection
    from veles.modules.embedding import get_local_embedding_adapter

    adapter = get_local_embedding_adapter()
    if adapter is None:
        return False
    with local_connection(project) as conn:
        total = 0
        while True:
            n = backfill_insight_embeddings(conn, adapter, limit=256)
            total += n
            if n == 0:
                break
            print(f"  embedded {total}", end="\r", flush=True)
    print(f"  embedded {total}          ")
    return True


def measure(project, probes: list[Probe], *, rows: int, vectors: bool) -> SizeResult:  # type: ignore[no-untyped-def]
    from veles.core.memory import SessionStore
    from veles.core.memory.router import MemoryRouter

    store = SessionStore(project.memory_db_path)
    router = MemoryRouter(project, store=store)
    found = 0
    positions: list[int] = []
    try:
        for probe in probes:
            hits = router.recall(probe.query, limit=_TOP_K)
            titles = [h.title for h in hits]
            if probe.target_title in titles:
                found += 1
                positions.append(titles.index(probe.target_title) + 1)
    finally:
        store.close()
    return SizeResult(
        rows=rows,
        probes=len(probes),
        recall_at_5=round(found / len(probes), 4) if probes else 0.0,
        median_position=statistics.median(positions) if positions else None,
        vectors_active=vectors,
    )


# The production cap on the rendered block (`runtime/prompt.py`). B2 reports
# against the real number, not a stress value: "truncation loses it" means
# nothing if the budget was invented to make it true.
_PROD_BLOCK_CHARS = 4_000


def order_report(project, probes: list[Probe]) -> str:  # type: ignore[no-untyped-def]
    """Run B2: where the target lands in the rendered block, and whether the
    drop-to-fit truncation removes it at the production budget."""
    from veles.core.memory import SessionStore
    from veles.core.memory.injector import build_memory_context_block
    from veles.core.memory.router import MemoryRouter

    store = SessionStore(project.memory_db_path)
    router = MemoryRouter(project, store=store)
    last_slot = 0
    truncated_away = 0
    checked = 0
    try:
        for probe in probes:
            hits = router.recall(probe.query, limit=_TOP_K)
            titles = [h.title for h in hits]
            if probe.target_title not in titles:
                continue
            checked += 1
            if titles.index(probe.target_title) == len(titles) - 1:
                last_slot += 1
            block = build_memory_context_block(hits, probe.query, max_chars=_PROD_BLOCK_CHARS)
            if block is not None and probe.target_title not in block:
                truncated_away += 1
    finally:
        store.close()
    if not checked:
        return "Run B2: no probe found its target, nothing to say about ordering."
    return (
        f"Run B2 (hit order, {checked} found targets): the target sits in the **last** "
        f"slot for {last_slot} of them ({last_slot / checked:.0%}), and "
        f"the production {_PROD_BLOCK_CHARS}-char budget truncates it away in "
        f"{truncated_away} ({truncated_away / checked:.0%}). "
        "Hits are listed best-first and truncation drops from the end, so those are the "
        "ones a tighter budget loses first. Whether the end of the list is also the part "
        "a model attends to most is a live-model question this run does not answer."
    )


def _render(results: list[SizeResult], order: str) -> str:
    vectors = any(r.vectors_active for r in results)
    lines = [
        "# M262 — recall precision (run B: is a known fact still findable?)",
        "",
        f"Corpus: the project's own documentation, {results[0].probes} probes "
        "(paragraph *i* asks, paragraph *i+1* answers), buried in synthetic rows.",
        "",
        "| rows | recall@5 | median position |",
        "|---|---|---|",
    ]
    for r in results:
        pos = f"{r.median_position:.0f}" if r.median_position is not None else "—"
        lines.append(f"| {r.rows:,} | {r.recall_at_5:.1%} | {pos} |")
    if len(results) >= 2:
        first, last = results[0], results[-1]
        delta = last.recall_at_5 - first.recall_at_5
        probes_worth = abs(delta) * last.probes
        verdict = (
            f"Between {first.rows:,} and {last.rows:,} rows recall@5 moves by "
            f"{delta:+.1%} — {probes_worth:.0f} probe(s) out of {last.probes}. "
        )
        verdict += (
            "That is inside this sample's resolution, so it is not a trend; it is the "
            "absence of an obvious collapse."
            if probes_worth < 5
            else "That is past the noise floor: the fact is sinking as the corpus grows."
        )
        lines += ["", verdict]
    lines += ["", order, ""]
    if not vectors:
        lines += [
            "> **No local embedding adapter was configured, so this measures the FTS "
            "path alone.** Vector recall is skipped by the router without one "
            "(`router._local_query_vector`), which is also why run A's total excludes "
            "it. Install a local embedder and re-run before reading these numbers as "
            "the whole of recall.",
            "",
        ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--sizes", default="10000,100000")
    ap.add_argument("--workdir", default=None)
    ap.add_argument("--out", default=None)
    ap.add_argument("--repo", default=".", help="where to read the real corpus from")
    args = ap.parse_args(argv)

    from veles.core.project import init_project, load_project

    corpus = build_corpus(Path(args.repo).resolve())
    probes = build_probes(corpus)
    if not probes:
        print("no corpus found — nothing to measure")
        return 1
    print(f"corpus: {len(corpus)} paragraphs, {len(probes)} probes")

    workdir = Path(args.workdir) if args.workdir else Path.home() / ".tmp" / "veles-bench-precision"
    workdir.mkdir(parents=True, exist_ok=True)
    random.seed(20260921)

    results: list[SizeResult] = []
    order = ""
    for rows in [int(s) for s in args.sizes.split(",") if s.strip()]:
        root = workdir / f"n{rows}"
        db = root / ".veles" / "memory.db"
        print(f"[{rows:,} rows] {root}")
        if not db.exists():
            root.mkdir(parents=True, exist_ok=True)
            init_project(root, name="bench-precision")
            seed_real(db, corpus)
            seed_synthetic(db, max(0, rows - len(corpus)))
        else:
            print("  reusing existing database")
        project = load_project(root)
        vectors = embed_corpus(project)
        results.append(measure(project, probes, rows=rows, vectors=vectors))
        print(f"  recall@5 = {results[-1].recall_at_5:.1%}")
        if not order:
            order = order_report(project, probes)

    report = _render(results, order)
    print()
    print(report)
    if args.out:
        out = Path(args.out)
        out.mkdir(parents=True, exist_ok=True)
        stamp = time.strftime("%Y-%m-%d")
        (out / f"{stamp}-bench-precision.md").write_text(report + "\n", encoding="utf-8")
        (out / f"{stamp}-bench-precision.json").write_text(
            json.dumps([asdict(r) for r in results], indent=2) + "\n", encoding="utf-8"
        )
        print(f"\nwritten to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["Probe", "build_corpus", "build_probes", "main", "measure", "order_report"]

# `_TOPICS` and `_DIM` are imported so the synthetic padding matches run A's
# corpus exactly; referencing them here keeps that dependency visible.
assert _TOPICS and _DIM

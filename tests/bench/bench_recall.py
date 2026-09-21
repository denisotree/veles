"""M262 — the recall benchmark. The gate that decides whether M263b is needed.

This is a measuring instrument, not a test: it is excluded from `testpaths`
(`pyproject.toml` lists only `tests`, and this file lives under `tests/bench/`
with no `test_` prefix), so CI never pays for a 1M-row load. Run it by hand:

    uv run python -m tests.bench.bench_recall --sizes 10000,100000 --out docs/audit/

**Two runs, because one number would be a lie.**

*A (this module)* measures latency, resident memory and database size on
synthetic rows. Vectors are seeded pseudorandom, so they are meaningless as
*content* and perfectly adequate as *load*: they exercise exactly the bytes and
the arithmetic that a real vector would.

*B (`bench_precision.py`)* measures whether a known fact is still findable as
the corpus grows around it. That one needs real text through a real local
embedder, because a pseudorandom vector has no semantic relationship to the
question that should retrieve it — recall@5 measured here would be noise, and
"precision collapsed at 1M" would be read off a number that never existed.

The gate: 1M insights, p95 of the whole recall under 200 ms.

Why per-collector and not just the total: `MemoryRouter` fans out to six
sources, and the plan's hypothesis is that `insights-KNN` dies first (vectors
are stored as JSON text and every row is parsed on every query) while FTS5 is
fine to millions. A single total would confirm "slow" without saying what to
fix.
"""

from __future__ import annotations

import argparse
import gc
import json
import random
import resource
import statistics
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path

from veles.core.memory import SessionStore
from veles.core.memory.vector import ensure_embeddings_table

# nomic-embed-text, the default local embedder, emits 768 dimensions. The
# openai default is 1536; 768 is therefore the *optimistic* case, which is the
# right one to fail on.
_DIM = 768
_SEED = 20260921
_INSERT_BATCH = 5_000

_TOPICS = (
    "nginx worker connections",
    "postgres vacuum schedule",
    "redis session ttl",
    "kafka consumer lag",
    "terraform state locking",
    "docker layer caching",
    "grpc deadline propagation",
    "s3 multipart upload",
)


@dataclass(frozen=True, slots=True)
class CollectorTiming:
    name: str
    p50_ms: float
    p95_ms: float
    max_ms: float
    samples: int
    budget_exhausted: bool = False


@dataclass(frozen=True, slots=True)
class SizeResult:
    rows: int
    db_bytes: int
    peak_rss_delta_bytes: int
    collectors: list[CollectorTiming]
    total: CollectorTiming


def _peak_rss_bytes() -> int:
    """Peak RSS of this process. `ru_maxrss` is bytes on macOS and kilobytes on
    Linux — the benchmark has to run on both, so normalise here rather than
    reporting a number that is off by 1024 on one of them."""
    raw = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return raw if sys.platform == "darwin" else raw * 1024


def _timings(samples_ms: list[float], name: str, *, planned: int) -> CollectorTiming:
    ordered = sorted(samples_ms)
    idx = min(len(ordered) - 1, int(round(0.95 * (len(ordered) - 1))))
    return CollectorTiming(
        name=name,
        p50_ms=round(statistics.median(ordered), 3),
        p95_ms=round(ordered[idx], 3),
        max_ms=round(ordered[-1], 3),
        samples=len(ordered),
        budget_exhausted=len(ordered) < planned,
    )


def _sample(call, queries: list[str], *, budget_s: float) -> list[float]:
    """Time `call` over `queries`, stopping early once `budget_s` is spent.

    Without the budget the 1M run cannot finish: a single JSON-vector KNN query
    there is measured in minutes, and 200 of them would outlast any patience.
    A truncated sample is marked in the report rather than silently averaged in
    — a p95 over 4 samples is a different claim from a p95 over 200, and the
    reader has to see which one they are getting.
    """
    out: list[float] = []
    deadline = time.perf_counter() + budget_s
    for q in queries:
        t0 = time.perf_counter()
        call(q)
        out.append((time.perf_counter() - t0) * 1000.0)
        if time.perf_counter() > deadline:
            break
    return out


def seed(db_path: Path, rows: int, *, with_vectors: bool = True) -> None:
    """Fill `insights` (+ its FTS shadow, via the schema triggers) and
    `embeddings_blob` with `rows` synthetic entries.

    Vectors are **not** optional in practice: `embeddings_blob` does not exist
    in any live project, so a run that seeded only `insights` would measure FTS,
    find no vectors, and report KNN as free — the exact opposite of the
    hypothesis under test. The flag exists only to measure that difference
    deliberately.
    """
    rng = random.Random(_SEED)
    store = SessionStore(db_path)
    try:
        conn = store._conn
        ensure_embeddings_table(conn)
        now = time.time()
        for start in range(0, rows, _INSERT_BATCH):
            count = min(_INSERT_BATCH, rows - start)
            insights = []
            for i in range(start, start + count):
                topic = _TOPICS[i % len(_TOPICS)]
                insights.append(
                    (
                        f"{topic} note {i}",
                        f"{topic} tuned to value {i % 997} after incident {i}",
                        "synthetic",
                        now - i,
                    )
                )
            with conn:
                conn.executemany(
                    "INSERT INTO insights(title, body, category, created_at)"
                    " VALUES (?, ?, ?, ?)",
                    insights,
                )
            if not with_vectors:
                continue
            first_id = start + 1  # AUTOINCREMENT on a fresh table
            vectors = [
                (
                    "insight",
                    first_id + n,
                    _DIM,
                    json.dumps([round(rng.uniform(-1.0, 1.0), 6) for _ in range(_DIM)]),
                    now,
                )
                for n in range(count)
            ]
            with conn:
                conn.executemany(
                    "INSERT INTO embeddings_blob(ref_kind, ref_id, dim, vec_json, created_at)"
                    " VALUES (?, ?, ?, ?, ?)",
                    vectors,
                )
            print(f"  seeded {start + count}/{rows}", end="\r", flush=True)
        print(f"  seeded {rows}/{rows}          ")
    finally:
        store.close()


def _queries(n: int) -> list[str]:
    rng = random.Random(_SEED + 1)
    return [f"{rng.choice(_TOPICS)} {rng.randint(0, 996)}" for _ in range(n)]


def measure(db_path: Path, *, rows: int, samples: int, budget_s: float) -> SizeResult:
    """Time each recall collector separately, plus the whole router pass."""
    from veles.core.memory.router import MemoryRouter
    from veles.core.project import load_project

    # db_path is `<root>/.veles/memory.db`; the project root is two levels up.
    project_root = db_path.parent.parent
    project = load_project(project_root)
    if db_path != project.memory_db_path:
        raise SystemExit(f"seed path must be the project db: {project.memory_db_path}")

    queries = _queries(samples)
    store = SessionStore(db_path)
    router = MemoryRouter(project, store=store)
    query_vec = [0.5] * _DIM

    collectors: list[tuple[str, object]] = [
        ("insights-FTS", lambda q: store.search_insights(q, limit=5)),
        # The KNN probe ignores the query text on purpose: the vector is what
        # costs, and a seeded pseudorandom one is as expensive as a real one.
        ("insights-KNN", lambda _q: store.knn_insights(query_vec, limit=5)),
        ("turns", lambda q: store.search_turns(q, limit=5, since=None)),
        ("wiki", lambda q: router._collect_wiki(q, limit=5)),
        ("about", lambda q: router._collect_about_veles(q, limit=5)),
    ]

    gc.collect()
    rss_before = _peak_rss_bytes()
    timings: list[CollectorTiming] = []
    try:
        for name, call in collectors:
            samples_ms = _sample(call, queries, budget_s=budget_s)
            timings.append(_timings(samples_ms, name, planned=len(queries)))
            t = timings[-1]
            note = f"  (only {t.samples} samples — budget)" if t.budget_exhausted else ""
            print(f"  {name:<14} p95={t.p95_ms:9.2f} ms{note}")

        total_ms = _sample(lambda q: router.recall(q, limit=5), queries, budget_s=budget_s)
        total = _timings(total_ms, "recall-total", planned=len(queries))
        print(f"  {'recall-total':<14} p95={total.p95_ms:9.2f} ms")
    finally:
        store.close()

    return SizeResult(
        rows=rows,
        db_bytes=db_path.stat().st_size,
        peak_rss_delta_bytes=max(0, _peak_rss_bytes() - rss_before),
        collectors=timings,
        total=total,
    )


def _render(results: list[SizeResult], *, gate_ms: float) -> str:
    lines = [
        "# M262 — recall benchmark (run A: latency / memory / size)",
        "",
        f"Gate: p95 of the whole recall under {gate_ms:.0f} ms at 1M insights.",
        "",
        "| rows | db | peak RSS Δ | " + " | ".join(c.name for c in results[0].collectors) + " | total |",
        "|---" * (4 + len(results[0].collectors)) + "|",
    ]
    for r in results:
        cells = " | ".join(f"{c.p95_ms:.1f}" for c in r.collectors)
        lines.append(
            f"| {r.rows:,} | {r.db_bytes / 2**20:.0f} MB |"
            f" {r.peak_rss_delta_bytes / 2**20:.0f} MB | {cells} |"
            f" **{r.total.p95_ms:.1f}** |"
        )
    lines += ["", "All numbers are p95 in milliseconds.", ""]
    worst = results[-1]
    slowest = max(worst.collectors, key=lambda c: c.p95_ms)
    # The router only runs the KNN collector when a LOCAL embedding adapter is
    # registered (`router._local_query_vector`). On a machine without one the
    # total excludes KNN entirely — so a green total next to a red KNN is not a
    # pass, it is a measurement of the configuration, and the report has to say
    # so out loud or it reads as "everything is fine".
    knn = next((c for c in worst.collectors if c.name == "insights-KNN"), None)
    realistic_ms = worst.total.p95_ms
    if knn is not None and knn.p95_ms > worst.total.p95_ms:
        realistic_ms = worst.total.p95_ms + knn.p95_ms
    verdict = "PASS" if realistic_ms < gate_ms else "FAIL"
    lines.append(
        f"At {worst.rows:,} rows: **{verdict}** — "
        f"{realistic_ms:.1f} ms vs the {gate_ms:.0f} ms gate; "
        f"slowest collector `{slowest.name}` at {slowest.p95_ms:.1f} ms."
    )
    if knn is not None and realistic_ms != worst.total.p95_ms:
        lines += [
            "",
            f"> The measured total is **{worst.total.p95_ms:.1f} ms**, but it does *not*"
            " include `insights-KNN`: the router skips vector recall when no local"
            " embedding adapter is registered, and this machine has none. The verdict"
            " above adds the KNN cost back, because a project that configures"
            " embeddings pays it on every turn.",
        ]
    truncated = [c for r in results for c in [*r.collectors, r.total] if c.budget_exhausted]
    if truncated:
        lines += [
            "",
            "Budget-truncated samples (p95 over fewer queries than planned): "
            + ", ".join(f"`{c.name}` n={c.samples}" for c in truncated)
            + ".",
        ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--sizes", default="10000,100000", help="comma-separated row counts")
    ap.add_argument("--samples", type=int, default=200, help="queries per collector")
    ap.add_argument("--gate-ms", type=float, default=200.0)
    ap.add_argument(
        "--budget-s",
        type=float,
        default=30.0,
        help="wall-clock budget per collector; a truncated sample is flagged in the report",
    )
    ap.add_argument("--workdir", default=None, help="where to build the databases")
    ap.add_argument("--out", default=None, help="directory for the markdown + json report")
    args = ap.parse_args(argv)

    sizes = [int(s) for s in args.sizes.split(",") if s.strip()]
    workdir = Path(args.workdir) if args.workdir else Path.home() / ".tmp" / "veles-bench"
    workdir.mkdir(parents=True, exist_ok=True)

    results: list[SizeResult] = []
    for rows in sizes:
        root = workdir / f"n{rows}"
        db = root / ".veles" / "memory.db"
        print(f"[{rows:,} rows] {root}")
        if not db.exists():
            root.mkdir(parents=True, exist_ok=True)
            from veles.core.project import init_project

            init_project(root, name="bench")
            seed(db, rows)
        else:
            print("  reusing existing database")
        results.append(measure(db, rows=rows, samples=args.samples, budget_s=args.budget_s))

    report = _render(results, gate_ms=args.gate_ms)
    print()
    print(report)
    if args.out:
        out = Path(args.out)
        out.mkdir(parents=True, exist_ok=True)
        stamp = time.strftime("%Y-%m-%d")
        (out / f"{stamp}-bench-recall.md").write_text(report + "\n", encoding="utf-8")
        (out / f"{stamp}-bench-recall.json").write_text(
            json.dumps([asdict(r) for r in results], indent=2) + "\n", encoding="utf-8"
        )
        print(f"\nwritten to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

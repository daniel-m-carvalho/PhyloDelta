"""How the correspondence search scales with thread count.

Only one step of the build is parallel — the clade-correspondence search
(`native/src/correspondence.hpp`) — so this drives *that*, directly, rather
than timing whole builds around it. A full build would bury the effect under
parsing, reconciliation and the metric, which are single-threaded and would
make any speedup look smaller than it is.

Two things are measured at once, and the second matters more:

* **time** at each thread count, and
* **whether the answer changes.** Index i's result depends only on read-only
  inputs, so it must be bit-identical however many threads ran. A race in a
  search like this would not crash; it would quietly return a slightly wrong
  best match, which no timing number would reveal.

    uv run python tools/measure_thread_scaling.py <pair-id> [threads...]
"""

from __future__ import annotations

import importlib
import json
import os
import sys
import time
from pathlib import Path

import numpy as np

REPEATS = 3


def run(left, right, threads: int):
    """Time one correspondence at a pinned thread count."""
    os.environ["PHYLODELTA_THREADS"] = str(threads)
    # The count is read through config at call time, but re-import the module
    # that caches it so a stale binding cannot silently pin every run to the
    # first value.
    from phylodelta import config
    importlib.reload(config)
    from phylodelta.trees import correspondence as corr
    importlib.reload(corr)

    best = None
    result = None
    for _ in range(REPEATS):
        started = time.perf_counter()
        result = corr.compute_correspondence(left, right)
        elapsed = time.perf_counter() - started
        best = elapsed if best is None else min(best, elapsed)
    return best, result


def main() -> None:
    from phylodelta import config
    from phylodelta.trees.store import read_tree

    pair_id = sys.argv[1]
    counts = [int(a) for a in sys.argv[2:]] or [1, 2, 3, 4, 6, 8, 10]

    from phylodelta.trees.reconcile import reconcile

    store = Path(config.STORE_DIR)
    meta = json.loads((store / "pairs" / pair_id / "rf" / "meta.json").read_text())
    raw_left = read_tree(store / "trees" / meta["left"]).to_arrays()
    raw_right = read_tree(store / "trees" / meta["right"]).to_arrays()

    # The store holds the trees as ingested; the search requires a shared leaf
    # set, which the pipeline establishes first (pipeline.py: reconcile ->
    # compute_correspondence). Reconciling here keeps this measuring the same
    # input the build does, and it is done ONCE, outside the timed region,
    # because it is not the step under test.
    left, right, report = reconcile(raw_left, raw_right)
    print(
        f"{meta['left']} x {meta['right']} — {raw_left.n_leaves:,} / "
        f"{raw_right.n_leaves:,} leaves, {left.n_leaves:,} shared after reconciling\n"
    )
    print(f"{'threads':>8} {'best of 3':>11} {'speedup':>9} {'efficiency':>11} {'identical':>10}")

    baseline = None
    reference = None
    rows = []
    for threads in counts:
        elapsed, result = run(left, right, threads)
        if baseline is None:
            baseline = elapsed
            reference = (
                np.asarray(result.left.similarity).copy(),
                np.asarray(result.left.corresponds).copy(),
            )
            identical = True
        else:
            identical = bool(
                np.array_equal(np.asarray(result.left.similarity), reference[0], equal_nan=True)
                and np.array_equal(np.asarray(result.left.corresponds), reference[1])
            )
        speedup = baseline / elapsed
        rows.append({
            "threads": threads,
            "seconds": elapsed,
            "speedup": speedup,
            "efficiency": speedup / threads,
            "identical_to_single_thread": identical,
        })
        print(
            f"{threads:>8} {elapsed:>10.2f}s {speedup:>8.2f}x {speedup / threads:>10.0%} "
            f"{'yes' if identical else '**NO**':>10}"
        )

    out = Path(__file__).resolve().parents[2] / "bench" / "results" / "thread_scaling.json"
    out.write_text(json.dumps({
        "pair": pair_id, "leaves": int(left.n_leaves), "repeats": REPEATS, "rungs": rows,
    }, indent=2))
    print(f"\nwritten to {out}")


if __name__ == "__main__":
    main()

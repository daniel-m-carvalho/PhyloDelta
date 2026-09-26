"""What a panel actually asks for, and what comes back, at every tree size.

The direct evidence for the central mechanism. The browser measurements show
PhyloDelta flat at ~0.5 s from 1,000 to 564,640 leaves, but that is the
*consequence*; this is the cause — the response is sized by the viewport, not
by the data, so neither its latency nor its size tracks the tree.

Read-only: it issues the same GET the frontend issues and records how long it
took and how many bytes came back. Nothing is built or rebuilt.

    uv run python tools/measure_slice_latency.py [api-base]
"""

from __future__ import annotations

import json
import statistics
import sys
import time
import urllib.request
from pathlib import Path

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8010/api/v1"
#: Enough to have a median that is not one unlucky request; small enough that
#: this stays a two-minute job.
SAMPLES = 7
BUDGET = 50


def fetch(url: str) -> tuple[float, int]:
    started = time.perf_counter()
    with urllib.request.urlopen(url, timeout=300) as response:
        body = response.read()
    return (time.perf_counter() - started) * 1000, len(body)


def main() -> None:
    bench = Path(__file__).resolve().parents[2] / "bench" / "results"
    built = json.loads((bench / "server_build.json").read_text())
    out = []

    print(f"{'leaves':>9} {'median':>9} {'min':>8} {'max':>8} {'bytes':>9} {'displayed':>10}")
    for record in sorted(built, key=lambda r: r["leaves"]):
        if record["status"] != "ready":
            continue
        with urllib.request.urlopen(f"{BASE}/comparisons/{record['id']}", timeout=60) as r:
            left = json.load(r)["left"]
        url = (
            f"{BASE}/trees/{left}/slice?budget={BUDGET}"
            f"&compare={record['id']}&metric=rf"
        )

        fetch(url)  # warm-up: the first touch of a store memory-maps it
        timings, size = [], 0
        for _ in range(SAMPLES):
            ms, size = fetch(url)
            timings.append(ms)

        with urllib.request.urlopen(url, timeout=300) as r:
            body = json.load(r)

        row = {
            "leaves": record["leaves"],
            "median_ms": statistics.median(timings),
            "min_ms": min(timings),
            "max_ms": max(timings),
            "bytes": size,
            "displayed_leaves": body["displayed_leaves"],
            "total_leaves": body["total_leaves"],
        }
        out.append(row)
        print(
            f"{row['leaves']:>9,} {row['median_ms']:>8.1f}ms {row['min_ms']:>7.1f}ms "
            f"{row['max_ms']:>7.1f}ms {row['bytes']:>9,} {row['displayed_leaves']:>10,}"
        )

    (bench / "slice_latency.json").write_text(json.dumps(out, indent=2))
    print(f"\nwritten to {bench / 'slice_latency.json'}")


if __name__ == "__main__":
    main()

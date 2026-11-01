"""What a panel actually asks for, and what comes back, at every tree size.

The direct evidence for the central mechanism. The browser measurements show
PhyloDelta flat at ~0.5 s from 1,000 to 564,640 leaves, but that is the
*consequence*; this is the cause — the response is sized by the viewport, not
by the data, so neither its latency nor its size tracks the tree.

Read-only: it issues the same GET the frontend issues and records how long it
took and how many bytes came back. Nothing is built or rebuilt.

    uv run python tools/measure_slice_latency.py [api-base] [metric]

With a metric other than `rf` the results go to `slice_latency_<metric>.json`, so
Table 12's two columns cannot be mixed. A rung the metric was declined at is
recorded with the server's reason. `BENCH_BUILD_FILE` names the build to read
(default `server_build.json`).

`gzip_bytes` is the same body through zlib at level 6, the level `serve.mjs`
compresses at; it is computed here, not taken from the wire (Table 20 is that).
"""

from __future__ import annotations

import gzip
import json
import os
import statistics
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8010/api/v1"
METRIC = sys.argv[2] if len(sys.argv) > 2 else "rf"
BUILD_FILE = os.environ.get("BENCH_BUILD_FILE", "server_build.json")
OUT = "slice_latency.json" if METRIC == "rf" else f"slice_latency_{METRIC}.json"
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
    built = json.loads((bench / BUILD_FILE).read_text())
    out = []

    print(f"{'leaves':>9} {'median':>9} {'min':>8} {'max':>8} {'bytes':>9} {'displayed':>10}")
    for record in sorted(built, key=lambda r: r["leaves"]):
        if record["status"] != "ready":
            continue
        with urllib.request.urlopen(f"{BASE}/comparisons/{record['id']}", timeout=60) as r:
            left = json.load(r)["left"]
        url = (
            f"{BASE}/trees/{left}/slice?budget={BUDGET}"
            f"&compare={record['id']}&metric={METRIC}"
        )

        try:
            fetch(url)  # warm-up: the first touch of a store memory-maps it
        except urllib.error.HTTPError as refused:
            detail = json.load(refused).get("detail")
            out.append({"leaves": record["leaves"], "absent": detail})
            print(f"{record['leaves']:>9,} {METRIC} absent: {detail}")
            continue
        timings, size = [], 0
        for _ in range(SAMPLES):
            ms, size = fetch(url)
            timings.append(ms)

        with urllib.request.urlopen(url, timeout=300) as r:
            raw = r.read()
        body = json.loads(raw)

        row = {
            "leaves": record["leaves"],
            "median_ms": statistics.median(timings),
            "min_ms": min(timings),
            "max_ms": max(timings),
            "bytes": size,
            "gzip_bytes": len(gzip.compress(raw, compresslevel=6)),
            "metric": METRIC,
            "displayed_leaves": body["displayed_leaves"],
            "total_leaves": body["total_leaves"],
        }
        out.append(row)
        print(
            f"{row['leaves']:>9,} {row['median_ms']:>8.1f}ms {row['min_ms']:>7.1f}ms "
            f"{row['max_ms']:>7.1f}ms {row['bytes']:>9,} {row['displayed_leaves']:>10,}"
        )

    (bench / OUT).write_text(json.dumps(out, indent=2))
    print(f"\nwritten to {bench / OUT}")


if __name__ == "__main__":
    main()

"""Full build times at a pinned thread count, through the real upload path.

Table 8's figures used the default — one thread per hardware thread, ten here.
This re-measures the same builds with the count pinned, so the trade-off
between wall-clock time and cores taken is a measurement rather than an
extrapolation from the correspondence step alone.

The thread count is read from the environment by the **worker** process, so
the caller must start a worker with `PHYLODELTA_THREADS` already set; this
script only drives uploads against whatever API it is pointed at and records
what comes back.

Writes `thread_builds_<n>.json` — never `server_build.json`, whose comparison
ids the existing results depend on.

    uv run python tools/measure_thread_builds.py <ladder-dir> <api-base> <threads>
"""

from __future__ import annotations

import io
import json
import os
import statistics
import sys
import time
import urllib.request
import uuid
from pathlib import Path

from bench_build import verified_threads

LADDER = Path(sys.argv[1])
BASE = sys.argv[2]
THREADS = int(sys.argv[3])
#: What each upload asks for. Anything but the default goes to its own file, so
#: Table 8's two builds can never be read as one.
METRICS = sys.argv[4] if len(sys.argv) > 4 else "rf"
SUFFIX = "" if METRICS == "rf" else "_app"
#: Builds per rung (§34.24). `build_s` is their median, so every table that
#: read one build reads the median now; `builds_s` keeps each, for the
#: interquartile range. A build after the first is deleted once timed: the
#: store would otherwise hold every rung several times over, and nothing reads
#: those copies.
BUILDS = int(os.environ.get("BENCH_BUILDS", "1"))


def post(left: Path, right: Path, name: str) -> str:
    boundary = f"----thr{uuid.uuid4().hex}"
    buf = io.BytesIO()
    for key, value in (("name", name), ("metrics", METRICS)):
        buf.write(f"--{boundary}\r\n".encode())
        buf.write(f'Content-Disposition: form-data; name="{key}"\r\n\r\n{value}\r\n'.encode())
    for key, path in (("left_tree", left), ("right_tree", right)):
        buf.write(f"--{boundary}\r\n".encode())
        buf.write(
            f'Content-Disposition: form-data; name="{key}"; filename="{path.name}"\r\n'
            f"Content-Type: application/octet-stream\r\n\r\n".encode()
        )
        buf.write(path.read_bytes())
        buf.write(b"\r\n")
    buf.write(f"--{boundary}--\r\n".encode())
    request = urllib.request.Request(
        f"{BASE}/comparisons", data=buf.getvalue(), method="POST",
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )
    with urllib.request.urlopen(request, timeout=1800) as response:
        return json.load(response)["id"]


def delete(comparison_id: str) -> None:
    request = urllib.request.Request(f"{BASE}/comparisons/{comparison_id}", method="DELETE")
    with urllib.request.urlopen(request, timeout=600):
        pass


def build_once(left: Path, right: Path, leaves: int, attempt: int):
    started = time.perf_counter()
    comparison_id = post(left, right, f"thr{THREADS}-{leaves}-{attempt}")
    while True:
        with urllib.request.urlopen(f"{BASE}/comparisons/{comparison_id}/status", timeout=60) as r:
            record = json.load(r)
        if record["status"] in {"ready", "failed"}:
            break
        time.sleep(0.5)
    return comparison_id, time.perf_counter() - started, record


def main() -> None:
    rungs = sorted({int(p.name.split("-")[1]) for p in LADDER.glob("ladder-*-a.nwk")})
    out = []
    print(f"PHYLODELTA_THREADS={THREADS}\n")
    print(f"{'leaves':>9} {'build':>10}  status")
    for leaves in rungs:
        left = LADDER / f"ladder-{leaves:06d}-a.nwk"
        right = LADDER / f"ladder-{leaves:06d}-b.nwk"
        times, statuses = [], []
        for attempt in range(BUILDS):
            built, took, got = build_once(left, right, leaves, attempt)
            times.append(took)
            statuses.append(got["status"])
            if attempt == 0:
                comparison_id, record = built, got
            else:
                delete(built)
        elapsed = statistics.median(times)

        # What the worker ACTUALLY used, read back from the pair it just built.
        # Not a formality: a previous campaign recorded a run as "2 threads"
        # that had executed with one, and nothing caught it for three days —
        # `PHYLODELTA_THREADS` is read by the worker, which this script neither
        # starts nor controls, so the argument was only ever a filename.
        # Refusing here is the difference between a parameter that describes a
        # run and one that is checked against it.
        actual = (
            verified_threads(BASE, comparison_id, THREADS) if record["status"] == "ready" else None
        )

        out.append(
            {
                "leaves": leaves,
                "build_s": elapsed,
                "builds_s": times,
                "statuses": statuses,
                "status": record["status"] if all(x == "ready" for x in statuses) else "failed",
                "threads_verified": actual,
                "metrics_asked": METRICS.split(","),
                "metrics_ready": record.get("metrics_ready"),
                "metrics_failed": record.get("metrics_failed"),
            }
        )
        spread = f"  ({', '.join(f'{t:.1f}' for t in times)})" if BUILDS > 1 else ""
        print(f"{leaves:>9,} {elapsed:>9.1f}s  {record['status']}{spread}")
        target = Path(__file__).resolve().parents[2] / "bench" / "results" / f"thread_builds_{THREADS}{SUFFIX}.json"
        target.write_text(
            json.dumps(
                {"threads": THREADS, "metrics": METRICS.split(","), "builds": BUILDS, "rungs": out},
                indent=2,
            )
        )
    print(f"\nwritten to thread_builds_{THREADS}{SUFFIX}.json")


if __name__ == "__main__":
    main()

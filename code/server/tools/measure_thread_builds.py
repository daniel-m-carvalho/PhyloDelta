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
import sys
import time
import urllib.request
import uuid
from pathlib import Path

LADDER = Path(sys.argv[1])
BASE = sys.argv[2]
THREADS = int(sys.argv[3])


def post(left: Path, right: Path, name: str) -> str:
    boundary = f"----thr{uuid.uuid4().hex}"
    buf = io.BytesIO()
    for key, value in (("name", name), ("metrics", "rf")):
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


def main() -> None:
    rungs = sorted({int(p.name.split("-")[1]) for p in LADDER.glob("ladder-*-a.nwk")})
    out = []
    print(f"PHYLODELTA_THREADS={THREADS}\n")
    print(f"{'leaves':>9} {'build':>10}  status")
    for leaves in rungs:
        left = LADDER / f"ladder-{leaves:06d}-a.nwk"
        right = LADDER / f"ladder-{leaves:06d}-b.nwk"
        started = time.perf_counter()
        comparison_id = post(left, right, f"thr{THREADS}-{leaves}")
        while True:
            with urllib.request.urlopen(f"{BASE}/comparisons/{comparison_id}/status", timeout=60) as r:
                record = json.load(r)
            if record["status"] in {"ready", "failed"}:
                break
            time.sleep(0.5)
        elapsed = time.perf_counter() - started
        out.append({"leaves": leaves, "build_s": elapsed, "status": record["status"]})
        print(f"{leaves:>9,} {elapsed:>9.1f}s  {record['status']}")
        target = Path(__file__).resolve().parents[2] / "bench" / "results" / f"thread_builds_{THREADS}.json"
        target.write_text(json.dumps({"threads": THREADS, "rungs": out}, indent=2))
    print(f"\nwritten to thread_builds_{THREADS}.json")


if __name__ == "__main__":
    main()

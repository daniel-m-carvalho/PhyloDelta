"""Peak memory the server uses while building a comparison.

The cost ledger so far records the server's *time* and nothing about its
space. This fills that in, because "we moved the expensive step to a server"
invites the question of what that server needs, and an unmeasured answer is
not an answer.

Runs against a **throwaway store**: building into the benchmark store would
mint new comparison ids and break the link between `server_build.json` and
every result that references it. Nothing existing is touched.

The worker is a separate process, so its RSS is sampled directly rather than
inferred. Sampling is every 200 ms — a build takes seconds to minutes, so the
peak is unlikely to hide between samples the way a crashing browser's does.

    uv run python tools/measure_build_memory.py <ladder-dir> <api-base> <worker-pid>
"""

from __future__ import annotations

import io
import json
import subprocess
import sys
import threading
import time
import urllib.request
import uuid
from pathlib import Path

LADDER = Path(sys.argv[1])
BASE = sys.argv[2]
WORKER_PID = int(sys.argv[3])
SAMPLE_S = 0.2


def rss_mb(pid: int) -> float:
    try:
        out = subprocess.run(
            ["ps", "-o", "rss=", "-p", str(pid)], capture_output=True, text=True
        ).stdout.strip()
        return int(out) / 1024 if out else 0.0
    except Exception:
        return 0.0


def post(left: Path, right: Path, name: str) -> str:
    boundary = f"----mem{uuid.uuid4().hex}"
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
    with urllib.request.urlopen(request, timeout=900) as response:
        return json.load(response)["id"]


def main() -> None:
    rungs = sorted({int(p.name.split("-")[1]) for p in LADDER.glob("ladder-*-a.nwk")})
    baseline = rss_mb(WORKER_PID)
    target = Path(__file__).resolve().parents[2] / "bench" / "results" / "build_memory.json"
    print(f"worker pid {WORKER_PID}, idle RSS {baseline:,.0f} MB\n", flush=True)
    print(f"{'leaves':>9} {'build':>8} {'peak RSS':>11} {'over idle':>11}")

    out = []
    for leaves in rungs:
        left = LADDER / f"ladder-{leaves:06d}-a.nwk"
        right = LADDER / f"ladder-{leaves:06d}-b.nwk"

        peak = baseline
        stop = threading.Event()

        def watch():
            nonlocal peak
            while not stop.is_set():
                peak = max(peak, rss_mb(WORKER_PID))
                time.sleep(SAMPLE_S)

        sampler = threading.Thread(target=watch, daemon=True)
        sampler.start()
        started = time.perf_counter()
        comparison_id = post(left, right, f"mem-{leaves}")
        while True:
            with urllib.request.urlopen(f"{BASE}/comparisons/{comparison_id}/status", timeout=60) as r:
                record = json.load(r)
            if record["status"] in {"ready", "failed"}:
                break
            time.sleep(0.25)
        elapsed = time.perf_counter() - started
        stop.set()
        sampler.join(timeout=2)

        row = {
            "leaves": leaves,
            "build_s": elapsed,
            "peak_rss_mb": round(peak, 1),
            "over_idle_mb": round(peak - baseline, 1),
            "status": record["status"],
        }
        out.append(row)
        print(
            f"{leaves:>9,} {elapsed:>7.1f}s {peak:>10,.0f} MB {peak - baseline:>10,.0f} MB"
            + ("" if record["status"] == "ready" else f"  {record['status']}"),
            flush=True,
        )
        # After EVERY rung, like the other two measurement tools. Writing once
        # at the end made a healthy 40-minute run indistinguishable from a
        # stalled one: the output file kept its old timestamp throughout and
        # stdout was block-buffered, so there was no sign of progress at all
        # and the run was very nearly killed for nothing.
        target.write_text(json.dumps({"idle_rss_mb": round(baseline, 1), "rungs": out}, indent=2))

    print(f"\nwritten to {target}")


if __name__ == "__main__":
    main()

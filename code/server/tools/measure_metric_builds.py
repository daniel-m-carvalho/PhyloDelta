"""Does the chosen metric change what a build costs?

§9 claims it barely does: **correspondence is shared**, it is the O(n²) step, and
a metric runs once over trees that are already parsed and reconciled. So asking
for three metrics should cost about what asking for one costs. That is an
argument, not a measurement, and it is the kind of argument this project has
already been wrong about — so it is measured through the real upload path, the
same way the thread comparison was.

Three sets, at the deployment thread count:

    rf                        the built-in, in-process, per-clade
    rf, rf-treediff           adds one subprocess over a succinct representation
    rf, rf-treediff, triplet  adds a finer-grained distance

Each set is a **separate upload**, so each figure is a whole build: parse,
reconcile, correspondence, store, metrics. That is deliberate — the question is
what a user waits for, and the shared cost is exactly what makes the answer
interesting.

The metric *values* are recorded too, not just the times. `rf` and `rf-treediff`
compute the same quantity by different algorithms over different
representations, by different authors; if they disagree, one is wrong and that
matters more than either of their timings.

    uv run python tools/measure_metric_builds.py <ladder-dir> <api-base>
"""

from __future__ import annotations

import io
import json
import sys
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

LADDER = Path(sys.argv[1])
BASE = sys.argv[2]

#: Metric sets, each a separate build of the same pair.
SETS: list[list[str]] = [
    ["rf"],
    ["rf", "rf-treediff"],
    ["rf", "rf-treediff", "triplet"],
]

OUT = Path(__file__).resolve().parents[2] / "bench" / "results" / "metric_builds.json"


def post(left: Path, right: Path, name: str, metrics: list[str]) -> str:
    boundary = f"----met{uuid.uuid4().hex}"
    buf = io.BytesIO()
    # One comma-separated field, which is what `routes_uploads` declares and
    # `_validated_metrics` splits. Repeating the field instead would leave FastAPI
    # with only one of the values and quietly build fewer metrics than asked for.
    fields = [("name", name), ("metrics", ",".join(metrics))]
    for key, value in fields:
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
        f"{BASE}/comparisons",
        data=buf.getvalue(),
        method="POST",
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )
    with urllib.request.urlopen(request, timeout=3600) as response:
        return json.load(response)["id"]


def wait(comparison_id: str) -> dict:
    while True:
        with urllib.request.urlopen(
            f"{BASE}/comparisons/{comparison_id}/status", timeout=60
        ) as r:
            record = json.load(r)
        if record["status"] in {"ready", "failed"}:
            return record
        time.sleep(0.5)


def summary(comparison_id: str, metric: str) -> dict:
    """The metric's own scalars, or why they could not be had.

    A metric that failed is reported as failed rather than skipped: "triplet
    stops working above 10,000 leaves" is a finding about the metric, and a
    blank cell would read as "not tried".
    """
    url = f"{BASE}/comparisons/{comparison_id}?metric={metric}"
    try:
        with urllib.request.urlopen(url, timeout=120) as r:
            return {"ok": True, "summary": json.load(r)["summary"]}
    except urllib.error.HTTPError as failed:
        try:
            body = json.load(failed)
        except Exception:
            body = {"detail": failed.reason}
        return {"ok": False, "status": failed.code, "detail": body.get("detail")}


def main() -> None:
    rungs = sorted({int(p.name.split("-")[1]) for p in LADDER.glob("ladder-*-a.nwk")})
    rows: list[dict] = []
    print(f"api {BASE}\n")
    print(f"{'leaves':>9}  {'rf':>9}  {'rf+treediff':>12}  {'+triplet':>9}")

    for leaves in rungs:
        left = LADDER / f"ladder-{leaves:06d}-a.nwk"
        right = LADDER / f"ladder-{leaves:06d}-b.nwk"
        row: dict = {"leaves": leaves, "builds": []}

        for metrics in SETS:
            started = time.perf_counter()
            comparison_id = post(left, right, f"met{len(metrics)}-{leaves}", metrics)
            record = wait(comparison_id)
            elapsed = time.perf_counter() - started
            row["builds"].append(
                {
                    "metrics": metrics,
                    "build_s": round(elapsed, 2),
                    "status": record["status"],
                    "error": record.get("error"),
                    "id": comparison_id,
                    "values": {m: summary(comparison_id, m) for m in metrics},
                }
            )

        rows.append(row)
        cells = []
        for build in row["builds"]:
            cells.append(
                f"{build['build_s']:.1f}s" if build["status"] == "ready" else build["status"]
            )
        print(f"{leaves:>9,}  {cells[0]:>9}  {cells[1]:>12}  {cells[2]:>9}")
        # Written after every rung: a run this long is useless if being
        # interrupted loses it.
        OUT.write_text(json.dumps({"api": BASE, "sets": SETS, "rows": rows}, indent=2))
        sys.stdout.flush()

    print(f"\nwritten to {OUT.name}")


if __name__ == "__main__":
    main()

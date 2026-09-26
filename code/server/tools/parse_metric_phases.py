"""Split a build into shared work and per-metric work, from the worker's own log.

Comparing whole-build wall clock across metric sets does not answer the question
it looks like it answers. The three sets run in a fixed order, so the third is
always last, and the first pass showed "+triplet" at 1.7-2x the others at every
large rung — which is exactly the shape an ordering artefact has. That same trap
had already produced a wrong answer once today, when cached and uncached
navigation were measured in separate browsers (DECISIONS §34.14).

The worker already logs what is needed, per pair and unconfounded:

    <pair>  rf        rf=54,600 …  [exact]  553 KB  in 0.3 s
    <pair>  triplet   triplet=3.4e+12 …    1 KB    in 12.3 s
            shared work 14.8 s, correspondence 4,412 KB
    --- <pair> ready in 28.0 s

So the metric's cost is measured directly rather than inferred from a
difference of totals. Shared work is the thing every metric in a set pays once:
parse, reconcile, correspondence, store.

    uv run python tools/parse_metric_phases.py <worker-log>
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

LOG = Path(sys.argv[1])
BENCH = Path(__file__).resolve().parents[2] / "bench"
BUILDS = BENCH / "results" / "metric_builds.json"
OUT = BENCH / "results" / "metric_phases.json"

#: `<pair_id> <metric> … in <n> s` — a metric that produced something.
METRIC = re.compile(r"^(\S+__\S+)\s+(\S+)\s+.*\bin\s+([\d,.]+)\s+s\s*$")
#: The un-prefixed continuation line, so it belongs to the pair above it.
SHARED = re.compile(r"^\s+shared work\s+([\d,.]+)\s+s")
#: `--- <pair_id> ready in <n> s`
READY = re.compile(r"^---\s+(\S+__\S+)\s+ready in\s+([\d,.]+)\s+s")
#: A metric that refused. Recorded: absent is not the same as not asked for.
FAILED = re.compile(r"^(\S+__\S+)\s+(\S+)\s+failed:\s*(.*)$")


def number(text: str) -> float:
    return float(text.replace(",", ""))


def main() -> None:
    per_pair: dict[str, dict] = {}
    current: str | None = None

    for line in LOG.read_text(errors="replace").splitlines():
        ready = READY.match(line)
        if ready:
            pair, seconds = ready.group(1), number(ready.group(2))
            per_pair.setdefault(pair, {}).setdefault("metrics", {})
            per_pair[pair]["total_s"] = seconds
            current = pair
            continue

        failed = FAILED.match(line)
        if failed:
            pair, metric, why = failed.group(1), failed.group(2), failed.group(3)
            entry = per_pair.setdefault(pair, {}).setdefault("metrics", {})
            entry[metric] = {"failed": why.strip()[:200]}
            current = pair
            continue

        metric = METRIC.match(line)
        if metric:
            pair, name, seconds = metric.group(1), metric.group(2), number(metric.group(3))
            entry = per_pair.setdefault(pair, {}).setdefault("metrics", {})
            entry[name] = {"seconds": seconds}
            current = pair
            continue

        shared = SHARED.match(line)
        if shared and current is not None:
            per_pair[current]["shared_s"] = number(shared.group(1))
            continue

        # `--- <pair> claimed by …` opens a block; the shared-work line that
        # follows belongs to it even when no metric line came between.
        opened = re.match(r"^---\s+(\S+__\S+)\s+claimed", line)
        if opened:
            current = opened.group(1)
            per_pair.setdefault(current, {}).setdefault("metrics", {})

    builds = json.loads(BUILDS.read_text())
    rows = []
    for row in builds["rows"]:
        entry = {"leaves": row["leaves"], "builds": []}
        for build in row["builds"]:
            found = per_pair.get(build["id"], {})
            entry["builds"].append(
                {
                    "metrics": build["metrics"],
                    "wall_s": build["build_s"],
                    "total_s": found.get("total_s"),
                    "shared_s": found.get("shared_s"),
                    "per_metric": found.get("metrics", {}),
                }
            )
        rows.append(entry)

    OUT.write_text(json.dumps({"log": str(LOG), "rows": rows}, indent=2))

    print(f"{'leaves':>9}  {'shared':>8}  {'rf':>7}  {'treediff':>9}  {'triplet':>9}  {'total':>8}")
    for row in rows:
        widest = max(row["builds"], key=lambda b: len(b["metrics"]))
        per = widest["per_metric"]

        def cell(name):
            got = per.get(name)
            if got is None:
                return "—"
            if "failed" in got:
                return "FAILED"
            return f"{got['seconds']:.1f}s"

        # `is not None`, not truthiness: a genuine 0.0 s printed as "—", which
        # reads as "not measured" rather than "too fast to resolve".
        def secs(value):
            return f"{value:.1f}s" if value is not None else "—"

        print(
            f"{row['leaves']:>9,}  {secs(widest.get('shared_s')):>8}  "
            f"{cell('rf'):>7}  {cell('rf-treediff'):>9}  {cell('triplet'):>9}  "
            f"{secs(widest.get('total_s')):>8}"
        )
    print(f"\nwritten to {OUT.name}")


if __name__ == "__main__":
    main()

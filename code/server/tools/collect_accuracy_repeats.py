"""The same accuracy pair, run again: how much of Table 5 is one draw (§34.22).

phylo.io's comparison is not deterministic (§34.4): the same two trees give a
different set of missed clades on every run. The campaign's `accuracy` step runs
it once per size; its `accuracy_repeats` step runs 2,500 leaves four more times,
each to its own files, and this collects the five into `accuracy_repeats.json`:
every run's miss count and gaps, and how many clade scores each later run
shares with the first. The tables write the sentence from these numbers.

    uv run python tools/collect_accuracy_repeats.py <results-dir> <repeats-dir> [leaves]
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

RESULTS = Path(sys.argv[1])
REPEATS = Path(sys.argv[2])
LEAVES = int(sys.argv[3]) if len(sys.argv) > 3 else 2500

FIELDS = ("comparable", "exact_match", "worse", "gap_median", "gap_worst", "compare_ms")


def scores(path: Path) -> dict[str, float | None]:
    return {c["k"]: c["s"] for c in json.loads(path.read_text())["clades"]}


def main() -> None:
    first_accuracy = RESULTS / f"bcn_accuracy_{LEAVES}.json"
    first_scores = RESULTS / f"phyloio_scores_{LEAVES}.json"
    if not first_accuracy.exists() or not first_scores.exists():
        sys.exit(f"no campaign accuracy run at {LEAVES:,} leaves to repeat")
    repeats = sorted(REPEATS.glob("accuracy_*.json"), key=lambda p: int(p.stem.split("_")[1]))
    if not repeats:
        sys.exit(f"no repeats in {REPEATS}")

    first = json.loads(first_accuracy.read_text())
    runs = [{k: first.get(k) for k in FIELDS}]
    baseline = scores(first_scores)
    identical = []
    for path in repeats:
        run = json.loads(path.read_text())
        if run.get("pair") != first.get("pair"):
            sys.exit(f"{path.name} is pair {run.get('pair')}, not {first.get('pair')}")
        runs.append({k: run.get(k) for k in FIELDS})
        again = scores(REPEATS / f"scores_{path.stem.split('_')[1]}.json")
        identical.append(sum(1 for k, s in again.items() if k in baseline and baseline[k] == s))

    commit = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, check=False
    ).stdout.strip()
    out = RESULTS / "accuracy_repeats.json"
    out.write_text(json.dumps({
        "commit": commit,
        "leaves": LEAVES,
        "pair": first.get("pair"),
        "clades": len(baseline),
        "runs": runs,
        "scores_identical_to_first_run": identical,
    }, indent=1) + "\n")
    misses = ", ".join(str(r["worse"]) for r in runs)
    print(f"{LEAVES:,} leaves, {len(runs)} runs: missed {misses}; identical to the first {identical}")
    print(f"written to {out}")


if __name__ == "__main__":
    main()

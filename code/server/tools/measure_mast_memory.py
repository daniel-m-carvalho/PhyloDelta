"""What MAST itself costs in memory, against the estimate the budget uses (§50).

The worker declines MAST when its estimate of the agreement table exceeds a
budget (`metrics/runners.py`). That is only as good as the estimate, so this
measures the real thing: for each pair of the benchmark ladder, the peak memory
of the native MAST call over what the process held before it.

The call is measured in a process of its own that only loads the pair's
prepared inputs from disk. Parsing, reconciling and the correspondence search
peak higher than MAST does at small sizes, and a high-water mark cannot be
reset, so measured in one process they would hide it.

    uv run python tools/measure_mast_memory.py <ladder-dir> [max-leaves] [out.json]

Needs the native extension; sizes whose estimate is over 8 GB are skipped.
"""

from __future__ import annotations

import json
import platform
import resource
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import numpy as np

SKIP_ABOVE_BYTES = 8 * 2**30


def peak_rss_bytes() -> int:
    # Bytes on macOS, kilobytes on Linux.
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return peak if platform.system() == "Darwin" else peak * 1024


def current_rss_bytes() -> int:
    out = subprocess.run(["ps", "-o", "rss=", "-p", str(__import__("os").getpid())],
                         capture_output=True, text=True).stdout
    return int(out.strip()) * 1024


def prepare(left: Path, right: Path, out: Path) -> int:
    """Parse, reconcile and correspond the pair; save MAST's inputs. Returns leaves."""
    from phylodelta.metrics.plugins.mast.mast import _inputs
    from phylodelta.trees.correspondence import compute_correspondence
    from phylodelta.trees.newick import parse_newick_file
    from phylodelta.trees.reconcile import reconcile

    left_r, right_r, _ = reconcile(parse_newick_file(left, fast=True),
                                   parse_newick_file(right, fast=True))
    inputs = _inputs(left_r, right_r, compute_correspondence(left_r, right_r))
    np.savez(out, **inputs)
    return left_r.n_leaves


def measure(npz: Path) -> None:
    """In its own process: load, note the memory, run MAST, report the peak."""
    from phylodelta.metrics.plugins.mast.mast import internal_table_bytes
    from phylodelta.trees import native

    extension = native.extension()
    if extension is None:
        sys.exit("the native extension is not built (native/build.sh)")
    with np.load(npz) as stored:
        inputs = {name: np.ascontiguousarray(stored[name]) for name in stored.files}
    before = current_rss_bytes()
    started = time.perf_counter()
    kept = np.asarray(extension.mast(**inputs), dtype=bool)
    seconds = time.perf_counter() - started
    n_leaves = int((inputs["left_position"] >= 0).sum())
    print(json.dumps({
        "leaves": n_leaves,
        "left_nodes": len(inputs["left_end"]),
        "right_nodes": len(inputs["right_end"]),
        "estimate_bytes": internal_table_bytes(inputs["left_end"], inputs["right_end"], n_leaves),
        "before_bytes": before,
        "peak_bytes": peak_rss_bytes(),
        "mast_bytes": peak_rss_bytes() - before,
        "seconds": round(seconds, 2),
        "mast_size": int(kept.sum()),
    }))


def main() -> None:
    if len(sys.argv) >= 3 and sys.argv[1] == "--measure":
        measure(Path(sys.argv[2]))
        return
    ladder = Path(sys.argv[1])
    limit = int(sys.argv[2]) if len(sys.argv) > 2 else 10**9
    out = Path(sys.argv[3]) if len(sys.argv) > 3 else None

    rows = []
    with tempfile.TemporaryDirectory() as scratch:
        for left in sorted(ladder.glob("ladder-*-a.nwk")):
            leaves = int(left.name.split("-")[1])
            if leaves > limit:
                continue
            # The worst case for the table: two binary trees of n leaves.
            if (leaves - 1) ** 2 * (2 if leaves <= 0xFFFF else 4) > SKIP_ABOVE_BYTES:
                print(f"{leaves:>7,} leaves: skipped, the table would be over 8 GB", flush=True)
                continue
            npz = Path(scratch) / f"{leaves}.npz"
            prepare(left, left.with_name(left.name.replace("-a.", "-b.")), npz)
            done = subprocess.run([sys.executable, __file__, "--measure", str(npz)],
                                  capture_output=True, text=True, check=True)
            row = json.loads(done.stdout)
            rows.append(row)
            print(f"{row['leaves']:>7,} leaves: estimate {row['estimate_bytes'] / 2**20:8.1f} MiB, "
                  f"measured {row['mast_bytes'] / 2**20:8.1f} MiB "
                  f"({row['mast_bytes'] / max(row['estimate_bytes'], 1):.3f}x), "
                  f"{row['seconds']:.1f} s", flush=True)
    if out:
        out.write_text(json.dumps({"machine": platform.platform(), "rows": rows}, indent=2) + "\n")


if __name__ == "__main__":
    main()

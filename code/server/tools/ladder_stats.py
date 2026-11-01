"""What the ladder actually contains, read from the Newick files.

Three different figures for the trees' depth stood in three documents (443, 79
to 191, 79 to 474), all hand-written. This measures them once, for every rung,
and `make_tables.py` prints what it finds.

Deliberately reads the **text**, not the parser: the ladder is input to the
benchmark, so a check on it must not go through the code being measured.

* **leaves** — labels that follow `(` or `,`.
* **depth** — the deepest nesting of parentheses, so the edges from the root to
  the deepest leaf. An internal label or a branch length cannot change it.
* **clades** — internal nodes, one per `(`, root included.
* **shared** — leaves in both trees over leaves in either.

    uv run python tools/ladder_stats.py <ladder-dir> [out.json]
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

#: A leaf: a label straight after an opening bracket or a comma. An internal
#: node's label follows `)`, so it is never matched.
LEAF = re.compile(r"(?<=[(,])[^(),:;]+")


def measured(path: Path) -> dict:
    text = path.read_text()
    depth = deepest = 0
    for char in text:
        if char == "(":
            depth += 1
            deepest = max(deepest, depth)
        elif char == ")":
            depth -= 1
    if depth != 0:
        raise SystemExit(f"{path.name}: unbalanced parentheses")
    labels = LEAF.findall(text)
    return {
        "file": path.name,
        "bytes": path.stat().st_size,
        "sha256": hashlib.sha256(text.encode()).hexdigest(),
        "leaves": len(labels),
        "distinct_leaves": len(set(labels)),
        "clades": text.count("("),
        "max_depth": deepest,
        "labels": set(labels),
    }


def main() -> None:
    ladder = Path(sys.argv[1])
    rows = []
    print(f"{'rung':>9} {'leaves a':>9} {'leaves b':>9} {'shared':>9} {'depth a':>8} "
          f"{'depth b':>8} {'clades a':>9} {'clades b':>9}")
    for path in sorted(ladder.glob("ladder-*-a.nwk")):
        rung = int(path.name.split("-")[1])
        a = measured(path)
        b = measured(path.with_name(path.name.replace("-a.nwk", "-b.nwk")))
        left, right = a.pop("labels"), b.pop("labels")
        shared = len(left & right) / len(left | right)
        rows.append({"rung": rung, "shared_fraction": shared,
                     "shared_leaves": len(left & right), "a": a, "b": b})
        print(f"{rung:>9,} {a['leaves']:>9,} {b['leaves']:>9,} {shared:>8.4%} "
              f"{a['max_depth']:>8,} {b['max_depth']:>8,} {a['clades']:>9,} {b['clades']:>9,}")
    if len(sys.argv) > 2:
        Path(sys.argv[2]).write_text(json.dumps({"rungs": rows}, indent=1) + "\n")


if __name__ == "__main__":
    main()

"""Write a pair reconciled and stripped of branch lengths, for external tools.

The distance is only comparable across implementations if every implementation
is given the same two trees. For the real vibrio pair that means two steps the
pipeline does for itself and an outside tool does not:

  * **Reconcile** — restrict both to their shared leaf set and suppress the
    unary nodes that leaves behind. ST 211 is in the UPGMA tree and not the NJ
    one (§2.6), so the raw files are 17,646 leaves against 17,645, and a tool
    handed them compares two different taxon sets.
  * **Drop lengths** — `rf_postorder` prints a *weighted* distance when its
    input carries them, which is a different quantity wearing a similar label.

    uv run python tools/prepare_rf_input.py <left.nwk> <right.nwk> <out-dir>
"""

from __future__ import annotations

import sys
from pathlib import Path

from phylodelta.trees.newick import parse_newick_file
from phylodelta.trees.newick_writer import to_newick
from phylodelta.trees.reconcile import reconcile


def main(argv: list[str]) -> int:
    if len(argv) != 4:
        print(__doc__.strip().splitlines()[-1].strip(), file=sys.stderr)
        return 2
    left_path, right_path, out_dir = Path(argv[1]), Path(argv[2]), Path(argv[3])
    left, right, report = reconcile(
        parse_newick_file(left_path), parse_newick_file(right_path)
    )
    out_dir.mkdir(parents=True, exist_ok=True)
    for arrays, name in ((left, "a"), (right, "b")):
        (out_dir / f"{out_dir.name}-{name}.nwk").write_text(
            to_newick(arrays, include_lengths=False)
        )
    print(f"{report.shared:,} shared leaves; "
          f"dropped {report.dropped_left or '—'} from the left and "
          f"{report.dropped_right or '—'} from the right")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))

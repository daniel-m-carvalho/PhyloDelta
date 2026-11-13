"""The clade each rung's re-root benchmark roots above, one per rung (§34.24).

Both tools must re-root the **same clade**, and the same one in every run, so it
is chosen once here and written down: the left tree's internal node whose clade
is closest to a tenth of the tree's leaves, never the root or a child of the
root (both of which a re-root refuses, §56), ties to the smaller stored id.

PhyloDelta is told the clade's stored id. phylo.io holds its own copy of the
same Newick file, with its own node objects, so it is told the clade's leaves
and finds the node with exactly that leaf set. The store's canonical form
removes only unary nodes (§1.4), which change no clade, so the leaf set names
the same clade in both.

    PHYLODELTA_STORE=<store> uv run python tools/reroot_targets.py <results-dir>

Reads `server_build.json` from the results directory for the pair at each rung
and writes `reroot_targets.json` beside it.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

from phylodelta.trees import registry
from phylodelta.trees.newick import NO_PARENT

#: The clade's size, as a share of the tree's leaves.
SHARE = 0.10


def choose(arrays) -> int:
    n = arrays.n_nodes
    parent = np.asarray(arrays.parent)
    leaf_count = np.asarray(arrays.leaf_count, dtype=np.int64)
    index = np.arange(n)
    internal = np.asarray(arrays.subtree_end) != index + 1
    below_root_child = np.zeros(n, dtype=bool)
    has_parent = parent != NO_PARENT
    grand = np.full(n, NO_PARENT, dtype=np.uint32)
    grand[has_parent] = parent[parent[has_parent].astype(np.int64)]
    below_root_child[has_parent] = grand[has_parent] != NO_PARENT
    eligible = np.flatnonzero(internal & below_root_child)
    if not eligible.size:
        raise SystemExit("no node a re-root would accept")
    want = max(2, round(arrays.n_leaves * SHARE))
    distance = np.abs(leaf_count[eligible] - want)
    return int(eligible[np.lexsort((eligible, distance))[0]])


def main() -> None:
    results = Path(sys.argv[1])
    built = json.loads((results / "server_build.json").read_text())
    out = []
    for rung in sorted(built, key=lambda r: r["leaves"]):
        if rung.get("status") != "ready":
            continue
        left = rung["id"].split("__")[0]
        arrays = registry.get_tree(left).to_arrays()
        node = choose(arrays)
        end = int(arrays.subtree_end[node])
        labels = sorted(arrays.labels[i] for i in range(node, end) if arrays.is_leaf(i))
        out.append({
            "leaves": rung["leaves"],
            "pair": rung["id"],
            "tree": left,
            "node": node,
            "clade_leaves": len(labels),
            "depth": int(arrays.depth[node]),
            "labels": labels,
        })
        print(f"{rung['leaves']:>9,}  node {node:>8}  {len(labels):>7,} leaves  depth {arrays.depth[node]}")
    (results / "reroot_targets.json").write_text(json.dumps(out, indent=1))
    print(f"written to {results / 'reroot_targets.json'}")


if __name__ == "__main__":
    main()

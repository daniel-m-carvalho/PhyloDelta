"""Triplet distance, and where in the tree it comes from (§54).

The triplet distance counts the sets of three leaves the two trees group
differently. Each such set is **decided** at one node of a tree: the smallest
clade holding all three, where two of them sit under one child and the third
under the other. So the distance splits exactly over the nodes, and every clade
can say how much of it lies inside: that is this metric's own correspondence.

TreeDiff's `trip_sht` already computes, at every node, how many of the triples
decided there both trees resolve alike, and prints only their sum.
`trip_sht_nodes` (built by `native/build_treediff.sh` with
`native/patch_trip_sht_nodes.py`) also writes each node's count. It is run
once each way, for both trees' nodes, as a separate program (GPL-3.0).

Per node
--------
* ``similarity``: the share of the triples **inside** the clade that both trees
  resolve alike, ``1 - D(A) / C(|A|, 3)``. ``D(A)`` is the triplet distance
  between the two trees restricted to the clade's leaves: the disagreements
  decided at nodes of its subtree. At the root it is 1 minus the normalised
  distance in the header. A clade of fewer than three leaves holds no triple,
  and is 1.
* ``corresponds``: the smallest clade of the other tree holding the clade's
  leaves, where all of its triples are decided there. A leaf, itself.

Checked before relying on it: on 320 random pairs of 3–10 leaves, every node's
count equals a brute-force count; on the ladder, the counts sum to the
original program's distance at every rung.
"""

from __future__ import annotations

import re
import subprocess
import tempfile
from pathlib import Path

import numpy as np

from .... import config
from ....trees.correspondence import Correspondence, _aggregate, _Lca, _leaf_index
from ....trees.newick import TreeArrays
from ...contract import MetricResult, MetricSide
from ...runners import MetricFailed
from ..spr.spr import _newick


def program() -> str:
    return str(config.NATIVE_DIR / "TreeDiff" / "trip_sht_nodes")


def _choose3(n: np.ndarray) -> np.ndarray:
    n = n.astype(np.int64)
    return n * (n - 1) * (n - 2) // 6


def _children(arrays: TreeArrays) -> tuple[np.ndarray, np.ndarray]:
    """Each internal node's two children; refuses any other number by name."""
    end = np.asarray(arrays.subtree_end, dtype=np.int64)
    n = arrays.n_nodes
    first = np.arange(n) + 1
    internal = end != first
    second = np.full(n, -1, dtype=np.int64)
    second[internal] = end[first[internal]]
    if np.any(end[second[internal]] != end[internal]):
        raise MetricFailed(
            "the triplet counts are computed for binary trees; this tree has a node "
            "with more than two children"
        )
    return np.where(internal, first, -1), second


def _run(first: Path, second: Path, out: Path) -> int:
    try:
        done = subprocess.run(
            [program(), str(first), str(second), str(out)],
            capture_output=True, text=True, check=False,
        )
    except OSError as exc:
        raise MetricFailed(
            f"trip_sht_nodes could not be run ({exc}); build it with native/build_treediff.sh"
        ) from None
    found = re.search(r"Triplets distance is:\s*(\d+)", done.stdout)
    if done.returncode != 0 or found is None:
        raise MetricFailed(
            f"trip_sht_nodes exited with {done.returncode}: "
            f"{(done.stderr or done.stdout).strip()[:200]}"
        )
    return int(found.group(1))


def _side(
    this: TreeArrays, other: TreeArrays, agree: np.ndarray, this_in_other: np.ndarray
) -> tuple[dict[str, np.ndarray], int]:
    n = this.n_nodes
    if len(agree) != n:
        raise MetricFailed(f"trip_sht_nodes wrote {len(agree):,} counts for {n:,} nodes")
    end = np.asarray(this.subtree_end, dtype=np.int64)
    leaves = np.asarray(this.leaf_count, dtype=np.int64)
    left, right = _children(this)
    internal = left >= 0
    s1 = np.where(internal, leaves[np.maximum(left, 0)], 0)
    s2 = np.where(internal, leaves[np.maximum(right, 0)], 0)
    decided = s1 * (s1 - 1) // 2 * s2 + s2 * (s2 - 1) // 2 * s1
    disagree = decided - agree
    if np.any(disagree < 0):
        raise MetricFailed("trip_sht_nodes reported more agreeing triples than a node decides")

    running = np.concatenate(([0], np.cumsum(disagree, dtype=np.int64)))
    inside = running[end] - running[np.arange(n)]
    total = _choose3(leaves)
    similarity = np.where(
        total > 0, 1.0 - inside / np.maximum(total, 1), 1.0
    ).astype(np.float32)

    lo, hi, _ = _aggregate(this, np.asarray(this_in_other, dtype=np.int64))
    _, other_leaf_node = _leaf_index(other)
    corresponds = _Lca(other).query(other_leaf_node[lo], other_leaf_node[hi]).astype(np.uint32)
    return {"similarity": similarity, "corresponds": corresponds}, int(inside[0])


def compute(left: TreeArrays, right: TreeArrays, correspondence: Correspondence) -> MetricResult:
    labels = [left.labels[i] for i in range(left.n_nodes) if left.subtree_end[i] == i + 1]
    # Renamed, like rspr's input: `_` is how trip_sht marks an unnamed node.
    token = {label: f"L{k}" for k, label in enumerate(labels)}
    with tempfile.TemporaryDirectory(prefix="triplet-") as work:
        here = Path(work)
        (here / "left.nwk").write_text(_newick(left, token))
        (here / "right.nwk").write_text(_newick(right, token))
        distance = _run(here / "left.nwk", here / "right.nwk", here / "left.txt")
        swapped = _run(here / "right.nwk", here / "left.nwk", here / "right.txt")
        left_agree = np.loadtxt(here / "left.txt", dtype=np.int64, ndmin=1)
        right_agree = np.loadtxt(here / "right.txt", dtype=np.int64, ndmin=1)

    left_side, left_total = _side(left, right, left_agree, correspondence.left_to_right)
    right_side, right_total = _side(right, left, right_agree, correspondence.right_to_left)
    # The counts must add up to the distance the program printed, both ways.
    if not distance == swapped == left_total == right_total:
        raise MetricFailed(
            f"the per-node counts do not add up: distance {distance:,} / {swapped:,}, "
            f"sums {left_total:,} / {right_total:,}"
        )
    n = len(labels)
    possible = int(_choose3(np.array([n]))[0])
    return MetricResult(
        name="triplet",
        summary={
            "triplet": distance,
            "triplet_normalised": distance / possible if possible else 0.0,
            "n_leaves": n,
        },
        left=MetricSide(columns=left_side),
        right=MetricSide(columns=right_side),
    )

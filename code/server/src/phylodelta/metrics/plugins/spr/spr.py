"""SPR distance and its agreement forest, by rspr (§53).

The **rooted SPR distance** is the fewest prune-and-regraft moves that turn one
rooted tree into the other. It equals the size of a **maximum agreement
forest** minus one (Bordewich & Semple): cut both trees into the fewest blocks
of leaves that each tree arranges identically, and every block but the root's
is one move. So the forest is also the picture: which leaves moved *together*.

Why a range
-----------
Exact rooted SPR is NP-hard, and the exact search grows exponentially with the
distance. On the demo pair it is in the thousands, and the exact search did
not finish in 600 s even at 1,000 leaves. rspr also gives a linear-time
3-approximation: a forest with ``a`` blocks beyond the root's, where
``d <= a <= 3d``. So the metric reports what is known — ``ceil(a/3)`` to the
best ``a`` found — and the exact value only when the exact search finishes
within ``EXACT_BUDGET_S``. On the demo pair: 1,905 to 5,653, in 0.23 s.

How rspr is used
----------------
As a separate program (GPL-3.0; built by ``native/build_rspr.sh``), on rooted
binary Newick of the reconciled trees. Leaves are relabelled ``L0..Ln`` so no
label can collide with Newick syntax or with ``p``, which is how rspr prints
the root when the root ends up in a block of its own. The root's block is the
one holding ``p``, else the first printed — checked against an exact
agreement-forest search on 1,020 small forests, every one valid.

Per node, for the view
----------------------
* ``moved``: how many of the clade's leaves are outside the forest's largest
  block — 1 or 0 at a leaf. SPR moves every block but one; which one is a
  matter of where the root is put, and rspr's approximation often leaves the
  root in a block of its own (on the demo pair it did, so every leaf would be
  "moved"). The largest block is the backbone the view keeps, and the count of
  moves is the summary's, not this column's.
* ``similarity``: how intact the clade is, ``1 - (pieces - 1) / (leaves - 1)``,
  where ``pieces`` is how many blocks its leaves fall into: 1 in one piece, 0
  with every leaf in a block of its own. A leaf is 1. The blocks of an
  agreement forest are vertex-disjoint in each tree, so at most one block
  crosses the branch above a clade: ``pieces`` is the blocks rooted inside it,
  plus one if any of its leaves belong to a block rooted above it.
* ``corresponds``: the smallest clade of the other tree holding the clade's
  leaves. A leaf is linked to itself.
"""

from __future__ import annotations

import math
import re
import subprocess

import numpy as np

from .... import config
from ....trees.correspondence import Correspondence, _aggregate, _Lca, _leaf_index
from ....trees.newick import TreeArrays
from ...contract import MetricResult, MetricSide
from ...runners import MetricFailed

#: How long the exact search may run before the approximation is reported.
#: Small distances finish in milliseconds; large ones never finish at all.
EXACT_BUDGET_S = 10.0

#: Above this lower bound the exact search is not attempted: it is exponential
#: in the distance, and did not finish in 600 s at a lower bound of 147 (§53).
EXACT_TRY_UP_TO = 100

#: Measured peak of `rspr -approx` per leaf: 3.1 GB at 564,640 (§53).
BYTES_PER_LEAF = 6_000

_LEAF = re.compile(r"[^(),;\s]+")


def program() -> str:
    return str(config.NATIVE_DIR / "rspr" / "rspr")


def memory_bytes(left: TreeArrays, right: TreeArrays) -> int:
    """The estimate the runner checks against the deployment's budget (§50)."""
    return int(left.n_leaves) * BYTES_PER_LEAF


def _newick(arrays: TreeArrays, token: dict[str, str]) -> str:
    """Topology only, leaves renamed: what rspr reads.

    Iterative, from pre-order: a node opens a bracket, a leaf writes its name,
    and every subtree that ends at the next node closes one. Trees run to
    thousands of levels deep, too deep for recursion.
    """
    end = np.asarray(arrays.subtree_end, dtype=np.int64)
    out: list[str] = []
    open_ends: list[int] = []
    for node in range(arrays.n_nodes):
        if open_ends and out[-1] != "(":
            out.append(",")
        if end[node] == node + 1:
            out.append(token[arrays.labels[node]])
        else:
            out.append("(")
            open_ends.append(int(end[node]))
        while open_ends and open_ends[-1] == node + 1:
            out.append(")")
            open_ends.pop()
    return "".join(out) + ";"


def _run(args: list[str], trees: str, timeout: float | None) -> str | None:
    try:
        done = subprocess.run(
            [program(), *args], input=trees, capture_output=True, text=True,
            timeout=timeout, check=False,
        )
    except subprocess.TimeoutExpired:
        return None
    except OSError as exc:
        raise MetricFailed(f"rspr could not be run ({exc}); build it with native/build_rspr.sh") from None
    if done.returncode != 0:
        raise MetricFailed(f"rspr exited with {done.returncode}: {done.stderr.strip()[:200]}")
    return done.stdout


def _forest(output: str, prefix: str) -> tuple[int, list[list[str]]]:
    """The distance and the blocks rspr printed, the root's block first."""
    distance = None
    line = None
    for row in output.splitlines():
        if row.startswith(prefix + " drSPR="):
            distance = int(row.split("=", 1)[1])
        if row.startswith(("approx F1:", "F1:")):
            line = row
    if distance is None or line is None:
        raise MetricFailed(f"rspr printed no {prefix!r} forest")
    blocks = [_LEAF.findall(part) for part in line.split(":", 1)[1].split()]
    home = next((i for i, block in enumerate(blocks) if "p" in block), 0)
    blocks.insert(0, blocks.pop(home))
    blocks[0] = [leaf for leaf in blocks[0] if leaf != "p"]
    return distance, blocks


def _side(
    this: TreeArrays,
    other: TreeArrays,
    block_of_label: dict[str, int],
    this_in_other: np.ndarray,
) -> dict[str, np.ndarray]:
    n = this.n_nodes
    end = np.asarray(this.subtree_end, dtype=np.int64)
    is_leaf = end == np.arange(n) + 1
    leaves = np.asarray(this.leaf_count, dtype=np.int64)

    block = np.full(n, -1, dtype=np.int64)
    for i in np.flatnonzero(is_leaf):
        block[i] = block_of_label[this.labels[i]]

    def per_clade(value: np.ndarray) -> np.ndarray:
        running = np.concatenate(([0], np.cumsum(value, dtype=np.int64)))
        return running[end] - running[np.arange(n)]

    # Each block's root in this tree: the LCA of its first and last leaf.
    position, node_of_position = _leaf_index(this)
    count = int(block.max()) + 1
    first = np.full(count, np.iinfo(np.int64).max, dtype=np.int64)
    last = np.full(count, -1, dtype=np.int64)
    size = np.zeros(count, dtype=np.int64)
    leaf_nodes = np.flatnonzero(is_leaf)
    np.minimum.at(first, block[leaf_nodes], position[leaf_nodes])
    np.maximum.at(last, block[leaf_nodes], position[leaf_nodes])
    np.add.at(size, block[leaf_nodes], 1)
    present = size > 0
    largest = int(np.argmax(size))
    outside = is_leaf & (block != largest)
    moved = per_clade(outside).astype(np.float32)
    # Moved together or alone: a block of one leaf is a leaf SPR moved on its
    # own, which is what MAST would also have said; a larger one moved as a
    # group, which only SPR says. Disjoint, so they add up to `moved`.
    block_size = np.where(is_leaf, size[np.maximum(block, 0)], 0)
    alone = per_clade(outside & (block_size == 1)).astype(np.float32)
    grouped = per_clade(outside & (block_size > 1)).astype(np.float32)
    roots = _Lca(this).query(node_of_position[first[present]], node_of_position[last[present]])

    rooted_here = np.zeros(n, dtype=np.int64)
    leaves_rooted_here = np.zeros(n, dtype=np.int64)
    np.add.at(rooted_here, roots, 1)
    np.add.at(leaves_rooted_here, roots, size[present])
    inside = per_clade(rooted_here)
    crossing = (leaves - per_clade(leaves_rooted_here)) > 0
    pieces = inside + crossing
    similarity = np.where(
        leaves > 1, 1.0 - (pieces - 1) / np.maximum(leaves - 1, 1), 1.0
    ).astype(np.float32)

    lo, hi, _ = _aggregate(this, np.asarray(this_in_other, dtype=np.int64))
    _, other_leaf_node = _leaf_index(other)
    corresponds = _Lca(other).query(other_leaf_node[lo], other_leaf_node[hi]).astype(np.uint32)
    return {
        "moved": moved, "grouped": grouped, "alone": alone,
        "similarity": similarity, "corresponds": corresponds,
    }


def compute(left: TreeArrays, right: TreeArrays, correspondence: Correspondence) -> MetricResult:
    labels = [left.labels[i] for i in range(left.n_nodes) if left.subtree_end[i] == i + 1]
    token = {label: f"L{k}" for k, label in enumerate(labels)}
    label_of = {t: label for label, t in token.items()}
    trees = _newick(left, token) + "\n" + _newick(right, token) + "\n"

    approx_out = _run(["-approx", "-q"], trees, None)
    approx, _ = _forest(approx_out, "approx")
    best_out = _run(["-approx", "-cc", "-q"], trees, None)
    best, blocks = _forest(best_out, "approx")
    if approx < best:
        best, blocks = _forest(approx_out, "approx")

    exact = None
    if math.ceil(approx / 3) <= EXACT_TRY_UP_TO:
        exact_out = _run(["-q"], trees, EXACT_BUDGET_S)
        if exact_out is not None:
            exact, blocks = _forest(exact_out, "total exact")

    lower = exact if exact is not None else math.ceil(approx / 3)
    upper = exact if exact is not None else best

    block_of_label = {label_of[t]: k for k, block in enumerate(blocks) for t in block}
    if len(block_of_label) != len(labels):
        raise MetricFailed(
            f"rspr's forest holds {len(block_of_label):,} of the {len(labels):,} leaves"
        )
    left_side = _side(left, right, block_of_label, correspondence.left_to_right)
    right_side = _side(right, left, block_of_label, correspondence.right_to_left)
    moved = int(left_side["moved"][0])
    return MetricResult(
        name="spr",
        summary={
            "spr_lower": int(lower),
            "spr_upper": int(upper),
            "exact": exact is not None,
            "blocks": len(blocks),
            "moved": moved,
            "n_leaves": len(labels),
        },
        left=MetricSide(columns=left_side),
        right=MetricSide(columns=right_side),
    )

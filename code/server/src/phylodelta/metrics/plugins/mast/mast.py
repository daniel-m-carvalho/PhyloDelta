"""Moved leaves: the maximum agreement subtree of two rooted binary trees (§46).

The **maximum agreement subtree** (MAST) is the largest set of leaves that both
trees arrange identically — restricted to those leaves, the two trees are the
same tree. Every other leaf has *moved*. This is what the supervisor's R script
calls the trace, computed there with ``phangorn::mast``.

Why not phangorn
----------------
Measured on subsamples of the real pair, phangorn keeps a list of labels for
every pair of nodes in R: 4.9 GB at 10,000 leaves, and at the demo pair's
17,645 it crashed after 47 minutes inside ``mast.fit``. The same recurrence
storing one integer per pair of *internal* nodes is a few hundred MB and
seconds. phangorn stays as the oracle the tests compare against.

The recurrence (Steel & Warnow, 1993)
-------------------------------------
For internal ``u`` (children ``u1, u2``) and internal ``v`` (``v1, v2``)::

    M[u, v] = max(M[u1, v1] + M[u2, v2],  M[u1, v2] + M[u2, v1],
                  M[u, v1], M[u, v2],     M[u1, v],  M[u2, v])

A pair involving a leaf needs no table: a leaf agrees with a clade exactly when
the clade contains it, which the leaf-order intervals answer in O(1). So the
table is internal × internal only.

The agreement set is recovered by walking back from the roots and re-asking
which term won, in that fixed order. Where several sets are equally large the
first term wins, so the moved set is deterministic — and can differ from
phangorn's choice, though never in size.
"""

from __future__ import annotations

import numpy as np

from ....trees.correspondence import Correspondence, _aggregate, _leaf_index
from ....trees.newick import TreeArrays
from ...contract import MetricResult, MetricSide
from ...runners import MetricFailed

#: Without the native extension the Python recurrence runs instead, and it is
#: quadratic in interpreted code: fine for a test, hours for a real tree. Above
#: this the metric declines and says what would make it run.
PYTHON_MAX_LEAVES = 2_000


def _check_binary(arrays: TreeArrays, side: str) -> None:
    """Refuse a node with other than two children, by name.

    The recurrence pairs two children with two children; a polytomy needs a
    matching over its children instead, which is not implemented.
    """
    end = np.asarray(arrays.subtree_end, dtype=np.int64)
    n = arrays.n_nodes
    for i in range(n):
        if end[i] == i + 1:
            continue
        children, child = 0, i + 1
        while child < end[i]:
            children += 1
            child = int(end[child])
        if children != 2:
            label = arrays.labels[i] or "unnamed"
            raise MetricFailed(
                f"MAST is implemented for binary trees; node {i} ({label}) of the "
                f"{side} tree has {children} children"
            )


def _inputs(left: TreeArrays, right: TreeArrays, correspondence: Correspondence) -> dict:
    """The arrays both implementations take, all indexed by pre-order node."""
    l_pos, _ = _leaf_index(left)
    r_pos, _ = _leaf_index(right)
    l_lo, l_hi, _ = _aggregate(left, l_pos)
    r_lo, r_hi, _ = _aggregate(right, r_pos)
    as64 = lambda a: np.ascontiguousarray(a, dtype=np.int64)  # noqa: E731
    return {
        "left_end": as64(left.subtree_end),
        "right_end": as64(right.subtree_end),
        # Where each leaf sits in the OTHER tree's leaf order; -1 at internal nodes.
        "left_in_right": as64(correspondence.left_to_right),
        "right_in_left": as64(correspondence.right_to_left),
        # Each node's leaves, as an interval of its OWN tree's leaf order.
        "left_lo": as64(l_lo), "left_hi": as64(l_hi),
        "right_lo": as64(r_lo), "right_hi": as64(r_hi),
        "left_position": as64(l_pos),
    }


def agreement_python(
    left_end, right_end, left_in_right, right_in_left,
    left_lo, left_hi, right_lo, right_hi, left_position,
) -> np.ndarray:
    """The reference implementation: which left leaf positions the MAST keeps.

    Returned as a boolean mask over the left tree's leaf order. Plain loops,
    written to be read against the recurrence rather than to be fast; the
    native version is checked against it.
    """
    n_left, n_right = len(left_end), len(right_end)
    left_internal = [u for u in range(n_left) if left_end[u] != u + 1]
    right_internal = [v for v in range(n_right) if right_end[v] != v + 1]
    row = {u: k for k, u in enumerate(left_internal)}
    col = {v: k for k, v in enumerate(right_internal)}
    table = np.zeros((len(left_internal), len(right_internal)), dtype=np.int64)

    def children(end, i):
        return i + 1, int(end[i + 1])

    def value(u: int, v: int) -> int:
        if left_end[u] == u + 1:  # a left leaf agrees with v iff v contains it
            return int(right_lo[v] <= left_in_right[u] <= right_hi[v])
        if right_end[v] == v + 1:  # a right leaf agrees with u iff u contains it
            return int(left_lo[u] <= right_in_left[v] <= left_hi[u])
        return int(table[row[u], col[v]])

    def terms(u: int, v: int) -> list[tuple[int, list[tuple[int, int]]]]:
        u1, u2 = children(left_end, u)
        v1, v2 = children(right_end, v)
        return [
            (value(u1, v1) + value(u2, v2), [(u1, v1), (u2, v2)]),
            (value(u1, v2) + value(u2, v1), [(u1, v2), (u2, v1)]),
            (value(u, v1), [(u, v1)]),
            (value(u, v2), [(u, v2)]),
            (value(u1, v), [(u1, v)]),
            (value(u2, v), [(u2, v)]),
        ]

    # Children follow their parent in pre-order, so walking both trees
    # backwards fills every cell a cell depends on before the cell itself.
    for u in reversed(left_internal):
        for v in reversed(right_internal):
            table[row[u], col[v]] = max(total for total, _ in terms(u, v))

    kept = np.zeros(int(left_hi[0]) + 1, dtype=bool)
    stack = [(0, 0)]
    while stack:
        u, v = stack.pop()
        if left_end[u] == u + 1:
            if value(u, v):
                kept[left_position[u]] = True
            continue
        if right_end[v] == v + 1:
            if value(u, v):
                kept[right_in_left[v]] = True
            continue
        best = value(u, v)
        if best == 0:
            continue
        for total, pairs in terms(u, v):
            if total == best:  # the first term that reaches it, as the fill took
                stack.extend(pairs)
                break
    return kept


def agreement(inputs: dict, n_leaves: int) -> np.ndarray:
    """Native if built, else the Python reference within its size."""
    from ....trees import native

    extension = native.extension()
    if extension is not None and hasattr(extension, "mast"):
        try:
            return np.asarray(extension.mast(**inputs), dtype=bool)
        except MemoryError:
            # The table did not fit. Said by name, so the reason reaches the
            # person who asked rather than a worker log.
            raise MetricFailed(
                f"declined: the agreement table for {n_leaves:,} leaves does not fit "
                "in this machine's memory"
            ) from None
    if n_leaves > PYTHON_MAX_LEAVES:
        raise MetricFailed(
            f"declined: {n_leaves:,} leaves needs the native extension "
            f"(native/build.sh); without it MAST runs only up to {PYTHON_MAX_LEAVES:,}"
        )
    return agreement_python(**inputs)


def _per_node(arrays: TreeArrays, moved_leaf: np.ndarray) -> np.ndarray:
    """Moved leaves under every node: a leaf's own 0/1, a clade's sum.

    A clade is a contiguous pre-order range, so one prefix sum over the nodes
    answers every clade at once.
    """
    end = np.asarray(arrays.subtree_end, dtype=np.int64)
    running = np.concatenate(([0], np.cumsum(moved_leaf, dtype=np.int64)))
    return (running[end] - running[np.arange(arrays.n_nodes)]).astype(np.float32)


def compute(
    left: TreeArrays, right: TreeArrays, correspondence: Correspondence
) -> MetricResult:
    """The agreement subtree, as moved-leaf counts on both trees."""
    _check_binary(left, "left")
    _check_binary(right, "right")

    inputs = _inputs(left, right, correspondence)
    kept_positions = agreement(inputs, left.n_leaves)

    left_position = inputs["left_position"]
    left_is_leaf = left_position >= 0
    left_moved = np.zeros(left.n_nodes, dtype=np.int64)
    left_moved[left_is_leaf] = ~kept_positions[left_position[left_is_leaf]]

    # The right tree's leaves, read through where each sits on the left: the
    # same leaf is moved in both trees or in neither.
    right_in_left = inputs["right_in_left"]
    right_is_leaf = right_in_left >= 0
    right_moved = np.zeros(right.n_nodes, dtype=np.int64)
    right_moved[right_is_leaf] = ~kept_positions[right_in_left[right_is_leaf]]

    moved_labels_left = {left.labels[i] for i in np.flatnonzero(left_moved)}
    moved_labels_right = {right.labels[i] for i in np.flatnonzero(right_moved)}
    if moved_labels_left != moved_labels_right:
        raise AssertionError(
            f"the two trees disagree on which leaves moved: "
            f"{len(moved_labels_left)} vs {len(moved_labels_right)}"
        )

    n_leaves = left.n_leaves
    mast_size = int(kept_positions.sum())
    moved = n_leaves - mast_size
    return MetricResult(
        name="mast",
        summary={
            "mast_size": mast_size,
            "moved": moved,
            "moved_fraction": moved / n_leaves if n_leaves else 0.0,
            "n_leaves": n_leaves,
        },
        left=MetricSide(columns={"moved": _per_node(left, left_moved)}),
        right=MetricSide(columns={"moved": _per_node(right, right_moved)}),
    )

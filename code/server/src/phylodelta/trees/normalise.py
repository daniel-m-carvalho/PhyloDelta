"""Canonicalise a parsed tree before it enters the store.

The store's contract is a **rooted binary tree**: ``n_nodes == 2 * n_leaves - 1``,
every internal node with exactly two children. The rest of the backend leans on
that. Real files do not always arrive that way, so they are normalised once at
ingest rather than defended against on every request.

Found in the data, not anticipated: ``vibrio-nj-tree.nwk`` is written as ``(X);``
-- a root with a single child. A unary node is not harmless.

* It **duplicates a bipartition.** A node's cluster is the leaf set beneath it;
  a unary node's cluster is identical to its only child's. Robinson-Foulds is
  defined over the *set* of bipartitions, so a duplicate either inflates a
  naive count or silently collapses, depending on the implementation -- exactly
  the kind of off-by-one that makes two RF implementations disagree.
* It **wastes a slice entry**, and shows the user a branch point that is not one.

Suppression is the standard fix and is topology-preserving: the node is removed
and its branch length is added to its child's, so root-to-leaf distances are
unchanged. Chains of unary nodes collapse in one pass.

This is recorded in ``meta.json`` as ``suppressed_unary``, because it means the
stored node indices are *our canonical form* and not offsets into the source
file. Since node identity is defined as the pre-order index in this store, that
is the intended reading -- but it has to be stated, not assumed.
"""

from __future__ import annotations

import numpy as np

from .newick import NO_PARENT, TreeArrays


def child_counts(arrays: TreeArrays) -> np.ndarray:
    counts = np.zeros(arrays.n_nodes, dtype=np.int64)
    parent = np.asarray(arrays.parent)
    has_parent = parent != NO_PARENT
    np.add.at(counts, parent[has_parent].astype(np.int64), 1)
    return counts


def suppress_unary(arrays: TreeArrays) -> tuple[TreeArrays, int]:
    """Remove internal nodes with exactly one child. Returns the new tree and a count."""
    result, removed, _ = suppress_unary_with_map(arrays)
    return result, removed


def suppress_unary_with_map(arrays: TreeArrays) -> tuple[TreeArrays, int, np.ndarray]:
    """As ``suppress_unary``, and also the source index of each surviving node.

    The mapping matters because anything computed on the canonicalised tree --
    a comparison, for instance -- is indexed by the NEW pre-order positions, and
    has to be placed back onto the original tree before it can be served under
    the original tree's node ids.
    """
    n = arrays.n_nodes
    index = np.arange(n, dtype=np.uint32)
    is_leaf = np.asarray(arrays.subtree_end) == index + 1
    counts = child_counts(arrays)

    keep = is_leaf | (counts != 1)
    removed = int(n - keep.sum())
    if removed == 0:
        return arrays, 0, index.astype(np.int64)

    parent = np.asarray(arrays.parent)
    branch = np.asarray(arrays.branch_len, dtype=np.float64)

    # Forward passes: a parent always precedes its children in pre-order, so one
    # sweep resolves both the nearest surviving ancestor and the branch length
    # accumulated across a chain of suppressed nodes.
    surviving_parent = np.full(n, NO_PARENT, dtype=np.uint32)
    carried = np.zeros(n, dtype=np.float64)  # length owed to a node by dead ancestors
    for i in range(n):
        p = parent[i]
        if p == NO_PARENT:
            continue
        if keep[p]:
            surviving_parent[i] = p
            carried[i] = 0.0
        else:
            surviving_parent[i] = surviving_parent[p]
            dead_len = branch[p]
            carried[i] = carried[p] + (0.0 if np.isnan(dead_len) else dead_len)

    # A suppressed node's length passes to its child. NaN means "no length
    # given": a tree with no lengths at all must not acquire them, so NaN with
    # nothing carried stays NaN. If a dead ancestor did carry a length, that
    # distance is real and is kept rather than discarded.
    new_branch = np.where(
        np.isnan(branch),
        np.where(carried == 0.0, np.nan, carried),
        branch + carried,
    )

    # Re-index. Removal preserves pre-order, so the new index of a kept node is
    # simply how many kept nodes precede it -- and a subtree stays contiguous,
    # which is what lets the interval encoding survive the rewrite.
    prefix = np.zeros(n + 1, dtype=np.uint32)
    np.cumsum(keep, dtype=np.uint32, out=prefix[1:])
    kept_idx = np.flatnonzero(keep)

    new_n = len(kept_idx)
    new_parent = np.empty(new_n, dtype=np.uint32)
    survivors = surviving_parent[kept_idx]
    has_parent = survivors != NO_PARENT
    new_parent[~has_parent] = NO_PARENT
    new_parent[has_parent] = prefix[survivors[has_parent].astype(np.int64)]

    new_end = prefix[np.asarray(arrays.subtree_end)[kept_idx].astype(np.int64)]

    new_depth = np.zeros(new_n, dtype=np.uint16)
    for i in range(1, new_n):
        new_depth[i] = new_depth[new_parent[i]] + 1

    result = TreeArrays(
        parent=new_parent,
        subtree_end=new_end.astype(np.uint32),
        depth=new_depth,
        leaf_count=np.asarray(arrays.leaf_count)[kept_idx].astype(np.uint32),
        branch_len=new_branch[kept_idx].astype(np.float32),
        labels=[arrays.labels[i] for i in kept_idx],
    )
    return result, removed, kept_idx.astype(np.int64)


def resolve_trifurcating_root(arrays: TreeArrays) -> tuple[TreeArrays, bool]:
    """Make a root with exactly three children binary. Returns the tree and whether it did.

    Found in the data, like the unary root above: ``aureus-rapidnj-tree.nwk``
    ends ``...,'10103':0,'9630':3.48);`` -- a clade and two leaves under one
    root. That is how neighbour-joining tools (rapidNJ, most NJ implementations)
    write an **unrooted** tree: the root is only where the file had to start,
    and three children is the unrooted degree.

    Rejecting it would discard a real dataset over a formatting convention,
    the same argument as unary suppression. So the root is resolved: the
    child on the **longest branch** stays a child of the root, and the other
    two are joined under a new node with a zero-length branch. Longest, not
    first, so the result does not depend on which clade the tool happened to
    write first -- and it roots on the branch that most separates one part of
    the tree from the rest, which is the usual choice when nothing better is
    known. NaN lengths count as shorter than any length; ties go to file order.

    **This adds one clade the source did not assert** (the two joined
    children), so a rooted metric can differ by one from a comparison against
    some other rooting. It is recorded as ``resolved_root`` in ``meta.json``
    for that reason. Only a root of degree three is resolved: four or more
    children, or a multifurcation below the root, is a real polytomy and not a
    convention, and ``assert_rooted_binary`` refuses it. See DECISIONS.md §32.
    """
    n = arrays.n_nodes
    if n == 0:
        return arrays, False
    end = np.asarray(arrays.subtree_end).astype(np.int64)
    children = []
    child = 1
    while child < end[0]:
        children.append(child)
        child = int(end[child])
    if len(children) != 3:
        return arrays, False

    branch = np.asarray(arrays.branch_len, dtype=np.float64)
    lengths = [(-np.inf if np.isnan(branch[c]) else branch[c]) for c in children]
    kept = children[int(np.argmax(lengths))]  # argmax takes the first on a tie
    joined = [c for c in children if c != kept]

    def span(c: int) -> np.ndarray:
        return np.arange(c, end[c], dtype=np.int64)

    # The new node is -1 in `source`. If the kept child is first it stays
    # first; otherwise the joined pair comes first, in file order, and the kept
    # child follows. Either way every subtree is still one contiguous range.
    new = np.array([-1], dtype=np.int64)
    head = [span(kept)] if kept == children[0] else []
    tail = [] if kept == children[0] else [span(kept)]
    source = np.concatenate([np.array([0])] + head + [new] + [span(c) for c in joined] + tail)
    new_pos = int(np.flatnonzero(source == -1)[0])

    position = np.empty(n, dtype=np.int64)
    old = source != -1
    position[source[old]] = np.flatnonzero(old)
    in_joined = np.zeros(n, dtype=bool)
    for c in joined:
        in_joined[c:end[c]] = True

    parent = np.asarray(arrays.parent)
    new_parent = np.empty(n + 1, dtype=np.uint32)
    new_end = np.empty(n + 1, dtype=np.uint32)
    new_depth = np.empty(n + 1, dtype=np.uint16)
    new_leaf = np.empty(n + 1, dtype=np.uint32)
    new_branch = np.empty(n + 1, dtype=np.float32)

    for k, i in enumerate(source):
        if i == -1:
            new_parent[k] = 0
            new_end[k] = k + 1 + sum(int(end[c] - c) for c in joined)
            new_depth[k] = 1
            new_leaf[k] = sum(int(arrays.leaf_count[c]) for c in joined)
            # A tree given with no lengths must not acquire one (see above).
            new_branch[k] = np.nan if np.isnan(branch).all() else 0.0
            continue
        if i == 0:
            new_parent[k] = NO_PARENT
            new_end[k] = n + 1
        else:
            p = int(parent[i])
            new_parent[k] = new_pos if (p == 0 and i in joined) else position[p]
            new_end[k] = position[i] + (end[i] - i)
        new_depth[k] = int(arrays.depth[i]) + (1 if in_joined[i] else 0)
        new_leaf[k] = arrays.leaf_count[i]
        new_branch[k] = branch[i]

    labels = [arrays.labels[i] if i != -1 else "" for i in source]
    return (
        TreeArrays(
            parent=new_parent,
            subtree_end=new_end,
            depth=new_depth,
            leaf_count=new_leaf,
            branch_len=new_branch,
            labels=labels,
        ),
        True,
    )


class NotRootedBinary(ValueError):
    """The tree breaks the store's contract in a way canonicalisation cannot fix.

    Worded for the person who uploaded the file: they know their tree, not our
    pre-order numbering.
    """


def assert_rooted_binary(arrays: TreeArrays) -> None:
    """The invariant the store promises its readers."""
    counts = child_counts(arrays)
    index = np.arange(arrays.n_nodes, dtype=np.uint32)
    internal = np.asarray(arrays.subtree_end) != index + 1
    bad = np.flatnonzero(internal & (counts != 2))
    if bad.size:
        below_root = int((bad != 0).sum())
        parts = []
        if bad[0] == 0:
            parts.append(
                f"its root has {int(counts[0])} children (3 is the unrooted form "
                "and is accepted; more than that needs a rooting only you can choose)"
            )
        if below_root:
            parts.append(
                f"{below_root} node(s) below the root have more than two children "
                "(polytomies)"
            )
        raise NotRootedBinary(
            "it is not a binary tree: " + "; ".join(parts)
            + ". Resolve or root it before uploading."
        )
    if arrays.n_nodes != 2 * arrays.n_leaves - 1:
        raise NotRootedBinary(
            f"{arrays.n_nodes} nodes for {arrays.n_leaves} leaves; "
            f"a rooted binary tree has {2 * arrays.n_leaves - 1}"
        )


class RerootRefused(ValueError):
    """A re-root that cannot be done, or would change nothing, said by name (§56)."""


def reroot(arrays: TreeArrays, node: int) -> TreeArrays:
    """The tree rooted on the branch above ``node``, at the branch's midpoint (§56).

    The new root splits the branch above ``node`` in two: ``node`` keeps half
    its length, and the other half leads to its old parent. Every node on the
    path from there to the old root has its parent pointer reversed, so each
    takes, as its new branch, the length of the edge that used to lead down to
    it. The old root is left with one child and is removed as §1.4 removes any
    unary node, its two edges joined into one: ``suppress_unary`` adds the
    lengths, and keeps NaN — "no length given" — as NaN rather than inventing
    a zero. Half of NaN is NaN, so a tree without lengths gains none.

    Every leaf-to-leaf path length is unchanged: the only edges touched are
    the one split in two, the old root's two edges joined into one, and the
    reversed edges, which keep their lengths. Labels stay with their nodes.

    Linear in the number of nodes and iterative: the trees here are hundreds
    of levels deep, and a recursive rebuild would follow every one.

    Refused by name, never adjusted to something nearby:

    * the root itself has no branch above it;
    * a child of the root: rooting on its branch splits the root's two edges
      differently but gives the same rooted topology — the same clades — so
      every metric would answer as before;
    * an id outside the tree.
    """
    n = arrays.n_nodes
    if not 0 <= node < n:
        raise RerootRefused(f"node {node} is not in this tree, which has nodes 0 to {n - 1}")
    parent = np.asarray(arrays.parent)
    if parent[node] == NO_PARENT:
        raise RerootRefused(
            f"node {node} is the root; a tree is re-rooted on the branch above a node, "
            "and the root has none"
        )
    if parent[parent[node]] == NO_PARENT:
        raise RerootRefused(
            f"node {node} is a child of the root. Rooting on its branch gives the same "
            "rooted topology — the same clades, only the root's two edges split "
            "differently — so every metric would give the same answer"
        )

    # Children in their stored order, as CSR: one pass, no Python lists per node.
    # Pre-order lists every child after its parent and siblings left to right,
    # so a stable sort of the non-roots by parent keeps that order.
    non_root = np.flatnonzero(parent != NO_PARENT)
    by_parent = non_root[np.argsort(parent[non_root], kind="stable")]
    starts = np.zeros(n + 1, dtype=np.int64)
    np.add.at(starts, parent[non_root].astype(np.int64) + 1, 1)
    np.cumsum(starts, out=starts)

    lengths = np.asarray(arrays.branch_len, dtype=np.float64)

    # The path from `node` up to the old root, and what each node's parent is now.
    path = [node]
    while parent[path[-1]] != NO_PARENT:
        path.append(int(parent[path[-1]]))
    # On the path, p[i+1] becomes a child of p[i] for i >= 1, carrying the
    # length of the edge that ran p[i] -> p[i+1] the other way: p[i]'s own.
    came_from = {path[i]: path[i - 1] for i in range(1, len(path))}
    new_length = {path[i + 1]: float(lengths[path[i]]) for i in range(1, len(path) - 1)}
    half = float(lengths[node]) / 2.0  # NaN stays NaN
    new_length[node] = half
    new_length[path[1]] = half

    root = n  # the new root's id while building; it is renumbered with the rest

    def children(v: int) -> list[int]:
        if v == root:
            return [node, path[1]]
        own = [int(c) for c in by_parent[starts[v]:starts[v + 1]]]
        if v in came_from:
            # A node on the path: its old parent becomes its last child, and the
            # child it was reached from is no longer below it.
            own = [c for c in own if c != came_from[v]]
            if parent[v] != NO_PARENT:
                own.append(int(parent[v]))
        return own

    # Iterative pre-order over the new shape.
    order: list[int] = []
    new_parent: list[int] = []
    stack: list[tuple[int, int]] = [(root, -1)]
    while stack:
        v, up = stack.pop()
        position = len(order)
        order.append(v)
        new_parent.append(up)
        for child in reversed(children(v)):
            stack.append((child, position))

    m = len(order)
    out_parent = np.array([NO_PARENT if p < 0 else p for p in new_parent], dtype=np.uint32)
    out_len = np.empty(m, dtype=np.float64)
    labels: list[str] = []
    for i, v in enumerate(order):
        if v == root:
            out_len[i] = np.nan
            labels.append("")
        else:
            out_len[i] = new_length.get(v, float(lengths[v]))
            labels.append(arrays.labels[v])

    rebuilt = _from_preorder_parents(out_parent, out_len, labels)
    # The old root now has one child; remove it and join its two edges (§1.4).
    rebuilt, _ = suppress_unary(rebuilt)
    return rebuilt


def _from_preorder_parents(parent: np.ndarray, lengths: np.ndarray, labels: list[str]) -> TreeArrays:
    """Rebuild every derived column from parents given in pre-order. Linear."""
    m = parent.shape[0]
    depth = np.zeros(m, dtype=np.uint16)
    for i in range(1, m):
        depth[i] = depth[parent[i]] + 1
    subtree_end = np.arange(1, m + 1, dtype=np.int64)
    is_leaf = np.ones(m, dtype=bool)
    is_leaf[parent[1:].astype(np.int64)] = False
    leaf_count = is_leaf.astype(np.int64)
    # Children follow their parent in pre-order, so a backward sweep finishes
    # every subtree before its parent reads it.
    for i in range(m - 1, 0, -1):
        p = parent[i]
        leaf_count[p] += leaf_count[i]
        if subtree_end[i] > subtree_end[p]:
            subtree_end[p] = subtree_end[i]
    return TreeArrays(
        parent=parent.astype(np.uint32),
        subtree_end=subtree_end.astype(np.uint32),
        depth=depth,
        leaf_count=leaf_count.astype(np.uint32),
        branch_len=lengths.astype(np.float32),
        labels=labels,
    )

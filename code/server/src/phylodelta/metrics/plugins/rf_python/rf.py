"""Robinson-Foulds distance.

Only the distance. Clade correspondence — the Jaccard gradient and the best
corresponding node — lives in ``trees.correspondence`` and is computed once per
pair for every metric to share. This file is what remains when that is taken
out, and it is a good deal less than it used to be: of ~275 lines, ~180 were
general machinery and ~95 were actually Robinson-Foulds.

The verdict is derived, not recomputed
--------------------------------------
A clade is present in the other tree iff the clade best matching it has
**exactly** the same leaf set — which is ``similarity == 1.0``. Jaccard is 1
only when intersection equals union, and that is set equality. So RF's
per-clade ``exact`` column falls out of correspondence with no second traversal,
and a native implementation of this metric needs to return only a number.

That equivalence is asserted, not assumed: ``test_similarity_never_contradicts_
the_exact_verdict`` checks it holds on every one of the 35,289 and 35,291 nodes
of the real pair.

Cross-checked against a second mechanism
----------------------------------------
The shared-clade count is also computed by Day's interval test, which decides
membership with no LCA and no best-match search at all, and the two must agree.
Three of the five RF implementations examined for this project return wrong
answers on real input, all of them silently, so an assertion between two
mechanisms sharing no machinery is cheap insurance against joining them.
"""

from __future__ import annotations

import numpy as np

from ....trees.correspondence import Correspondence, _aggregate, _leaf_index
from ....trees.newick import TreeArrays
from ...contract import MetricResult, MetricSide


def _internal_mask(arrays: TreeArrays) -> np.ndarray:
    end = np.asarray(arrays.subtree_end)
    return end != np.arange(arrays.n_nodes) + 1


def _shared_by_day(
    left: TreeArrays, right: TreeArrays, left_to_right_position: np.ndarray
) -> int:
    """Count shared clades by Day's interval test, using no correspondence at all.

    A left clade is a right clade iff its taxa occupy a *contiguous* run of the
    right tree's leaf order AND that exact run is one of the right tree's
    clades. Independent of the best-match machinery, so it is a genuine
    cross-check rather than a restatement.
    """
    lo, hi, count = _aggregate(left, left_to_right_position)
    left_internal = _internal_mask(left)

    r_position_of_node, _ = _leaf_index(right)
    r_lo, r_hi, _ = _aggregate(right, r_position_of_node)
    right_internal = _internal_mask(right)

    stride = right.n_leaves + 1
    right_codes = np.unique(r_lo[right_internal] * stride + r_hi[right_internal])

    contiguous = left_internal & (hi - lo + 1 == count)
    codes = lo[contiguous] * stride + hi[contiguous]
    return int(np.isin(codes, right_codes).sum())


def compute(
    left: TreeArrays, right: TreeArrays, correspondence: Correspondence
) -> MetricResult:
    """Robinson-Foulds distance, and the per-clade exact-match verdict."""
    left_internal = _internal_mask(left)
    right_internal = _internal_mask(right)

    left_exact = np.isclose(correspondence.left.similarity, 1.0)
    right_exact = np.isclose(correspondence.right.similarity, 1.0)

    shared_left = int(left_exact[left_internal].sum())
    shared_right = int(right_exact[right_internal].sum())
    if shared_left != shared_right:
        raise AssertionError(
            f"clade sharing is not symmetric: {shared_left} vs {shared_right}"
        )

    by_day = _shared_by_day(left, right, correspondence.left_to_right)
    if by_day != shared_left:
        raise AssertionError(
            f"correspondence and Day's interval test disagree: {shared_left} vs {by_day}"
        )

    internal_left = left.n_leaves - 1
    internal_right = right.n_leaves - 1
    # The paper's Algorithm 2: internal-node counts stand in for the number of
    # non-singleton clades (valid only because unary nodes were suppressed,
    # §1.4/§2.4).
    #
    # **The full symmetric difference, not half of it** (§2.6, §34.19). This
    # used to be halved, following TreeDiff; DendroPy and ETE3 both report it
    # whole, and so does the definition — |C(T1)\C(T2)| + |C(T2)\C(T1)|.
    # TreeDiff still returns the halved value, so `rf-treediff` is now a
    # different quantity by a factor of two and says so in its manifest.
    #
    # Worth knowing why the halved number looked so plausible: it is *also*
    # exactly the one-sided count |C(T1)\C(T2)|, because after reconciliation
    # both trees are rooted binary over the same leaf set and therefore have
    # the same internal-node count, making the two exclusive counts equal. The
    # coincidence is a property of this pipeline's inputs, not of RF.
    rf = internal_left + internal_right - 2 * shared_left

    # The maximum the numerator can reach for *these two trees*: no clade
    # shared, so every counted cluster on each side is exclusive. Counted
    # clusters are the internal nodes excluding each root — the root's clade is
    # all taxa and is shared by construction, so it can never contribute, and
    # leaving it in the denominator would cap the ratio below 1. Single leaves
    # are excluded too: RF judges only internal branches.
    #
    # This matches ETE3's own `max_rf` (35,286 for the 17,645-leaf pair) and
    # DendroPy's rooted maximum. The previous version divided the *halved* RF by
    # this *full* maximum, which could never exceed 0.5 — and a test asserting
    # `> 0.49` for two near-maximally-different trees had pinned that ceiling in
    # place (DECISIONS, Corrections).
    max_rf = max(internal_left + internal_right - 2, 1)

    # The thesis's own definition of RF, computed from the similarity column
    # instead of from the shared count: a clade is absent from the other tree
    # exactly when its best match is not an exact one. Two routes to one number,
    # so a change to either side has to break this.
    exclusive_left = internal_left - shared_left
    exclusive_right = internal_right - shared_right
    if rf != exclusive_left + exclusive_right:
        raise AssertionError(
            f"rf {rf} is not the count of non-matching clades "
            f"({exclusive_left} + {exclusive_right})"
        )

    return MetricResult(
        name="rf",
        summary={
            "rf": rf,
            "rf_normalised": rf / max_rf,
            "shared_clusters": shared_left,
            "clusters_left": internal_left,
            "clusters_right": internal_right,
            "n_leaves": left.n_leaves,
        },
        left=MetricSide(columns={"exact": left_exact}),
        right=MetricSide(columns={"exact": right_exact}),
    )

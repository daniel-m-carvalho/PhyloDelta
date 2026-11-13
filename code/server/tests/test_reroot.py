"""Re-rooting a stored tree on the branch above a node (§56).

The promises being tested, each the property a re-rooted comparison rests on:
every leaf-to-leaf distance is unchanged, the result is a rooted binary tree
the store accepts, going back gives the original clades, a tree without
lengths gains none, and what cannot be done is refused by name.
"""

from __future__ import annotations

import itertools
import math
import random
import time

import numpy as np
import pytest

from phylodelta.trees.newick import NO_PARENT, TreeArrays, parse_newick, parse_newick_file
from phylodelta.trees.normalise import (
    RerootRefused,
    assert_rooted_binary,
    reroot,
    resolve_trifurcating_root,
    suppress_unary,
)


def _random_tree(n_leaves: int, rng: random.Random, lengths: bool = True) -> str:
    nodes = [f"L{i}" + (f":{rng.uniform(0.1, 5):.3f}" if lengths else "") for i in range(n_leaves)]
    while len(nodes) > 1:
        a = nodes.pop(rng.randrange(len(nodes)))
        b = nodes.pop(rng.randrange(len(nodes)))
        nodes.append(f"({a},{b})" + (f":{rng.uniform(0.1, 5):.3f}" if lengths else ""))
    return nodes[0] + ";"


def _leaf_distances(t: TreeArrays) -> dict[frozenset[str], float]:
    """Every leaf pair's path length, through the root-distance identity."""
    parent = t.parent
    lengths = np.nan_to_num(np.asarray(t.branch_len, dtype=np.float64))
    to_root = np.zeros(t.n_nodes)
    for i in range(1, t.n_nodes):
        to_root[i] = to_root[parent[i]] + lengths[i]
    ancestors = []
    for i in range(t.n_nodes):
        chain, v = set(), i
        while v != NO_PARENT:
            chain.add(int(v))
            v = parent[v]
        ancestors.append(chain)
    leaves = [i for i in range(t.n_nodes) if t.is_leaf(i)]
    out = {}
    for a, b in itertools.combinations(leaves, 2):
        common = ancestors[a] & ancestors[b]
        lca = max(common, key=lambda v: t.depth[v])
        out[frozenset((t.labels[a], t.labels[b]))] = to_root[a] + to_root[b] - 2 * to_root[lca]
    return out


def _clades(t: TreeArrays) -> set[frozenset[str]]:
    leaves = [t.labels[i] if t.is_leaf(i) else None for i in range(t.n_nodes)]
    return {
        frozenset(x for x in leaves[i:t.subtree_end[i]] if x is not None)
        for i in range(t.n_nodes)
    }


def _node_with_leaves(t: TreeArrays, wanted: frozenset[str]) -> int:
    leaves = [t.labels[i] if t.is_leaf(i) else None for i in range(t.n_nodes)]
    for i in range(t.n_nodes):
        if frozenset(x for x in leaves[i:t.subtree_end[i]] if x is not None) == wanted:
            return i
    raise AssertionError(f"no clade {sorted(wanted)}")


def _rerootable(t: TreeArrays) -> list[int]:
    p = t.parent
    return [i for i in range(t.n_nodes) if p[i] != NO_PARENT and p[p[i]] != NO_PARENT]


@pytest.mark.parametrize("seed", range(6))
def test_every_leaf_to_leaf_path_length_is_preserved(seed):
    rng = random.Random(seed)
    t = parse_newick(_random_tree(14, rng))
    before = _leaf_distances(t)
    for node in _rerootable(t):
        after = _leaf_distances(reroot(t, node))
        assert after.keys() == before.keys()
        for pair, d in before.items():
            assert after[pair] == pytest.approx(d, abs=1e-4), (node, sorted(pair))


@pytest.mark.parametrize("seed", range(4))
def test_the_result_is_a_rooted_binary_tree_the_store_accepts(seed):
    t = parse_newick(_random_tree(25, random.Random(seed)))
    for node in _rerootable(t):
        r = reroot(t, node)
        assert_rooted_binary(r)
        assert r.n_nodes == 2 * r.n_leaves - 1
        assert r.n_leaves == t.n_leaves
        assert sorted(r.labels[i] for i in range(r.n_nodes) if r.is_leaf(i)) == sorted(
            t.labels[i] for i in range(t.n_nodes) if t.is_leaf(i)
        )
        # The node re-rooted on is now one of the root's two children.
        children = [i for i in range(r.n_nodes) if r.parent[i] == 0]
        assert len(children) == 2


def test_the_store_round_trip_keeps_the_rerooted_tree_as_it_is():
    """Re-ingest of a re-rooted tree changes nothing: it is already canonical."""
    from phylodelta.trees.newick_writer import to_newick

    t = parse_newick(_random_tree(30, random.Random(9)))
    r = reroot(t, _rerootable(t)[5])
    again, suppressed = suppress_unary(parse_newick(to_newick(r)))
    again, resolved = resolve_trifurcating_root(again)
    assert (suppressed, resolved) == (0, False)
    assert again.labels == r.labels
    assert np.array_equal(again.parent, r.parent)
    assert np.allclose(again.branch_len, r.branch_len, equal_nan=True)


@pytest.mark.parametrize("seed", range(4))
def test_rerooting_back_gives_the_original_clades(seed):
    t = parse_newick(_random_tree(20, random.Random(seed)))
    original = _clades(t)
    root_children = [i for i in range(t.n_nodes) if t.parent[i] == 0]
    for node in _rerootable(t):
        r = reroot(t, node)
        # Back on the old root's edge: above whichever of its two clades is
        # still a clade (the new root sits inside the other one) — unless it
        # is now a child of the new root, which would mean nothing moved.
        rooted_back = False
        for clade_root in root_children:
            wanted = _clades_of(t, clade_root)
            if wanted not in _clades(r):
                continue
            target = _node_with_leaves(r, wanted)
            if r.parent[r.parent[target]] == NO_PARENT:
                assert _clades(r) == original
            else:
                assert _clades(reroot(r, target)) == original
            rooted_back = True
        assert rooted_back, "neither of the old root's clades survived the re-root"


def _clades_of(t: TreeArrays, node: int) -> frozenset[str]:
    return frozenset(t.labels[i] for i in range(node, t.subtree_end[node]) if t.is_leaf(i))


def test_the_branch_is_split_at_its_midpoint():
    t = parse_newick("(((A:1,B:2)x:3,C:4)y:5,(D:6,E:7)z:8)r;")
    r = reroot(t, t.labels.index("x"))
    by_label = {r.labels[i]: float(r.branch_len[i]) for i in range(r.n_nodes)}
    assert by_label["x"] == pytest.approx(1.5)
    assert by_label["y"] == pytest.approx(1.5)
    # The old root is gone and its two edges, 5 and 8, are one edge of 13.
    assert "r" not in r.labels
    assert by_label["z"] == pytest.approx(13)


def test_a_tree_without_lengths_gains_none():
    """The pruned ladder rungs carry no lengths: NaN must stay NaN, split or summed."""
    t = parse_newick(_random_tree(40, random.Random(3), lengths=False))
    assert np.isnan(t.branch_len).all()
    for node in _rerootable(t)[::5]:
        assert np.isnan(reroot(t, node).branch_len).all()


def test_a_missing_length_beside_a_present_one_keeps_the_one_given():
    t = parse_newick("(((A:1,B:2)x,C:4)y:5,(D:6,E:7)z)r;")
    r = reroot(t, t.labels.index("x"))
    by_label = {r.labels[i]: float(r.branch_len[i]) for i in range(r.n_nodes)}
    assert math.isnan(by_label["x"]) and math.isnan(by_label["y"])  # half of nothing
    assert by_label["z"] == pytest.approx(5)  # 5 + no length is 5, not NaN


@pytest.mark.parametrize(
    ("node", "says"),
    [
        (0, "is the root"),
        (1, "same rooted topology"),
        (6, "same rooted topology"),
        (9, "not in this tree"),
        (-1, "not in this tree"),
    ],
)
def test_what_cannot_be_done_is_refused_by_name(node, says):
    t = parse_newick("(((A:1,B:2)x:3,C:4)y:5,(D:6,E:7)z:8)r;")
    with pytest.raises(RerootRefused, match=says):
        reroot(t, node)


def test_it_is_linear_in_the_number_of_nodes():
    """Twice the nodes, about twice the time; a quadratic step would show as four."""
    def timed(n):
        t = parse_newick(_random_tree(n, random.Random(1)))
        deepest = int(np.argmax(t.depth))
        best = math.inf
        for _ in range(3):
            started = time.perf_counter()
            reroot(t, deepest)
            best = min(best, time.perf_counter() - started)
        return best

    small, large = timed(20_000), timed(80_000)
    assert large / small < 8, f"{small:.3f}s -> {large:.3f}s for 4x the leaves"


def test_the_real_vibrio_tree_reroots_and_keeps_its_distances(datasets_dir):
    t, _ = suppress_unary(parse_newick_file(datasets_dir / "gen_trees" / "vibrio-nj-tree.nwk"))
    deepest = int(np.argmax(t.depth))
    r = reroot(t, deepest)
    assert_rooted_binary(r)
    assert r.n_leaves == t.n_leaves

    # Distances through the root, on a sample of leaf pairs.
    def to_root(tree):
        out = np.zeros(tree.n_nodes)
        lengths = np.nan_to_num(np.asarray(tree.branch_len, dtype=np.float64))
        for i in range(1, tree.n_nodes):
            out[i] = out[tree.parent[i]] + lengths[i]
        return out

    def distance(tree, dist, index, a, b):
        x, y = index[a], index[b]
        seen = set()
        while x != NO_PARENT:
            seen.add(int(x))
            x = tree.parent[x]
        while int(y) not in seen:
            y = tree.parent[y]
        return dist[index[a]] + dist[index[b]] - 2 * dist[int(y)]

    tl, rl = to_root(t), to_root(r)
    ti = {t.labels[i]: i for i in range(t.n_nodes) if t.is_leaf(i)}
    ri = {r.labels[i]: i for i in range(r.n_nodes) if r.is_leaf(i)}
    rng = random.Random(0)
    names = sorted(ti)
    for _ in range(300):
        a, b = rng.sample(names, 2)
        assert distance(r, rl, ri, a, b) == pytest.approx(distance(t, tl, ti, a, b), rel=1e-5, abs=1e-5)

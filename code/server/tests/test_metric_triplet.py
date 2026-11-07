"""Triplet distance, and its own correspondence (§54).

What is promised, and tested here:

* the distance is TreeDiff's, unchanged;
* every clade's score is the share of the triples inside it that both trees
  resolve alike, which at the root is 1 minus the normalised distance —
  checked against a brute-force count on random pairs;
* the counts add up to the distance both ways, or the metric refuses;
* the patch applies to TreeDiff's source as pinned, by name if it ever stops.
"""

from __future__ import annotations

import itertools
import random
import subprocess
import sys
from pathlib import Path

import pytest

from phylodelta.metrics import registry
from phylodelta.metrics.contract import validate_result
from phylodelta.metrics.plugins.triplet_treediff import triplet as triplet_module
from phylodelta.metrics.runners import is_available
from phylodelta.trees.correspondence import compute_correspondence
from phylodelta.trees.newick import parse_newick
from phylodelta.trees.reconcile import reconcile

NATIVE = Path(__file__).resolve().parents[1] / "native"

built = pytest.mark.skipif(
    not is_available(registry.discover()["triplet"]),
    reason="trip_sht_nodes not built (native/build_treediff.sh)",
)


def _pair(left: str, right: str):
    left_r, right_r, _ = reconcile(parse_newick(left), parse_newick(right))
    return left_r, right_r, compute_correspondence(left_r, right_r)


def _random_tree(labels: list[str], rng: random.Random) -> str:
    nodes = labels[:]
    while len(nodes) > 1:
        a, b = nodes.pop(rng.randrange(len(nodes))), nodes.pop(rng.randrange(len(nodes)))
        nodes.append(f"({a},{b})")
    return nodes[0] + ";"


def _leaves(arrays, node: int) -> set[str]:
    end = arrays.subtree_end
    return {arrays.labels[i] for i in range(node, int(end[node])) if end[i] == i + 1}


def _together(arrays, trio: set[str]) -> frozenset[str]:
    """The two of three leaves a tree groups together: those under its smallest clade of two."""
    best = None
    for node in range(arrays.n_nodes):
        inside = _leaves(arrays, node) & trio
        if len(inside) == 2 and (best is None or len(_leaves(arrays, node)) < best[0]):
            best = (len(_leaves(arrays, node)), frozenset(inside))
    return best[1]


@built
def test_one_moved_leaf_disagrees_on_the_triples_it_changes():
    left, right, corr = _pair("((((A,B),C),D),E);", "((((A,B),D),C),E);")
    result = triplet_module.compute(left, right, corr)
    validate_result(result, registry.discover()["triplet"])
    # ACD and BCD are grouped differently; every other triple alike.
    assert result.summary["triplet"] == 2
    assert result.summary["triplet_normalised"] == pytest.approx(2 / 10)
    score = result.left.columns["similarity"]
    assert score[0] == pytest.approx(1 - 2 / 10)
    clade_abcd = next(i for i in range(left.n_nodes) if _leaves(left, i) == {"A", "B", "C", "D"})
    assert score[clade_abcd] == pytest.approx(1 - 2 / 4)


@built
def test_every_clade_scores_its_own_triples_on_random_pairs():
    rng = random.Random(54)
    labels = [f"t{i}" for i in range(9)]
    for _ in range(20):
        left, right, corr = _pair(_random_tree(labels, rng), _random_tree(labels, rng))
        result = triplet_module.compute(left, right, corr)
        for this, other, side in ((left, right, result.left), (right, left, result.right)):
            for node in range(this.n_nodes):
                inside = _leaves(this, node)
                trios = [set(t) for t in itertools.combinations(sorted(inside), 3)]
                if not trios:
                    assert side.columns["similarity"][node] == 1.0
                    continue
                alike = sum(_together(this, t) == _together(other, t) for t in trios)
                assert side.columns["similarity"][node] == pytest.approx(alike / len(trios), abs=1e-6)
                counterpart = int(side.columns["corresponds"][node])
                assert inside <= _leaves(other, counterpart)


@built
def test_counts_that_do_not_add_up_are_refused(monkeypatch):
    left, right, corr = _pair("((((A,B),C),D),E);", "((((A,B),D),C),E);")
    real = triplet_module._run

    def off_by_one(first, second, out):
        distance = real(first, second, out)
        return distance + 1

    monkeypatch.setattr(triplet_module, "_run", off_by_one)
    with pytest.raises(triplet_module.MetricFailed, match="do not add up"):
        triplet_module.compute(left, right, corr)


def test_a_tree_that_is_not_binary_is_refused_by_name():
    arrays = parse_newick("((A,B,C),D);")
    with pytest.raises(triplet_module.MetricFailed, match="more than two children"):
        triplet_module._children(arrays)


def test_the_patch_applies_and_says_where_it_failed_when_it_does_not(tmp_path):
    source = tmp_path / "trip_sht.cpp"
    # The four places the patch touches, with TreeDiff's CRLF endings.
    source.write_bytes(
        b"using namespace sdsl;\r\n"
        b"        dist = values2[0];\r\n"
        b"        dist = values2[0];\r\n"
        b"    triplets_onlyleaves_2(vec_1, vec_2, code, 0, triplets_equal, size);\r\n"
        b'    cout << "Triplets distance is: " << 0;\r\n'
    )
    target = tmp_path / "trip_sht_nodes.cpp"
    script = NATIVE / "patch_trip_sht_nodes.py"
    done = subprocess.run([sys.executable, str(script), str(source), str(target)], capture_output=True, text=True)
    assert done.returncode == 0, done.stderr
    patched = target.read_bytes()
    assert patched.count(b"agree_at[current - 1] = values2[0];\r\n") == 2
    assert b"\n" not in patched.replace(b"\r\n", b"")  # still CRLF throughout

    source.write_bytes(b"using namespace sdsl;\r\n")
    refused = subprocess.run([sys.executable, str(script), str(source), str(target)], capture_output=True, text=True)
    assert refused.returncode != 0
    assert "expected 2 of" in refused.stderr

"""SPR distance and its agreement forest, by rspr (§53).

What is promised, and tested here:

* the distance is exact where rspr's exact search finishes, and otherwise a
  range that holds the true value: a third of the 3-approximation, rounded up,
  to the best forest found;
* every block of the forest it draws is arranged identically by both trees —
  checked here, not taken from rspr;
* per node, "moved" counts the leaves outside the largest block, "similarity"
  is how intact the clade is, and the counterpart is the smallest clade of the
  other tree holding its leaves;
* without rspr the metric is listed as unavailable, and the demo has one
  comparison per metric.
"""

from __future__ import annotations

import io
import math
import random
import re

import numpy as np
import pytest
from fastapi.testclient import TestClient

from phylodelta import config, db
from phylodelta.api.app import create_app
from phylodelta.api.identity import AUTH_HEADER
from phylodelta.metrics import registry, registry_pairs
from phylodelta.metrics.contract import validate_result
from phylodelta.metrics.plugins.spr import spr as spr_module
from phylodelta.metrics.runners import is_available
from phylodelta.trees.correspondence import compute_correspondence
from phylodelta.trees.newick import parse_newick
from phylodelta.trees.reconcile import reconcile

ALICE = {AUTH_HEADER: "alice"}

built = pytest.mark.skipif(
    not is_available(registry.discover()["spr"]),
    reason="rspr not built (native/build_rspr.sh)",
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


def _leaves(arrays, node: int) -> frozenset[str]:
    end = arrays.subtree_end
    return frozenset(arrays.labels[i] for i in range(node, int(end[node])) if end[i] == i + 1)


def _clusters(arrays, within: frozenset[str]) -> set[frozenset[str]]:
    """The tree restricted to `within`, as its clusters."""
    out = set()
    for node in range(arrays.n_nodes):
        kept = _leaves(arrays, node) & within
        if 1 < len(kept) < len(within):
            out.add(kept)
    return out


@built
@pytest.mark.parametrize(
    ("left", "right", "spr"),
    [
        ("((((A,B),C),D),E);", "((((A,B),C),D),E);", 0),
        ("((((A,B),C),D),E);", "((((A,B),D),C),E);", 1),
        # Checked by breadth-first search over every SPR move (DECISIONS §53).
        ("((((A,B),C),(D,E)),F);", "((((A,F),E),(D,C)),B);", 3),
    ],
)
def test_small_distances_are_exact(left, right, spr):
    result = spr_module.compute(*_pair(left, right))
    validate_result(result, registry.discover()["spr"])
    assert result.summary["exact"] is True
    assert result.summary["spr_lower"] == result.summary["spr_upper"] == spr
    assert result.summary["blocks"] >= spr + 1


@built
def test_a_large_distance_is_a_range_that_holds_the_exact_value(monkeypatch):
    """Forcing the approximation where the exact value is known."""
    left, right = "((((A,B),C),(D,E)),F);", "((((A,F),E),(D,C)),B);"
    monkeypatch.setattr(spr_module, "EXACT_TRY_UP_TO", -1)
    summary = spr_module.compute(*_pair(left, right)).summary
    assert summary["exact"] is False
    assert summary["spr_lower"] <= 3 <= summary["spr_upper"]


@built
def test_on_random_pairs_the_forest_and_every_node_say_what_they_promise(monkeypatch):
    monkeypatch.setattr(spr_module, "EXACT_TRY_UP_TO", -1)  # the approximation's path
    seen: dict[str, list[list[str]]] = {}
    forest = spr_module._forest

    def keep(output, prefix):
        distance, blocks = forest(output, prefix)
        seen["blocks"] = blocks
        return distance, blocks

    monkeypatch.setattr(spr_module, "_forest", keep)
    rng = random.Random(53)
    labels = [f"t{i}" for i in range(16)]
    for _ in range(25):
        left, right, corr = _pair(_random_tree(labels, rng), _random_tree(labels, rng))
        result = spr_module.compute(left, right, corr)
        token = {f"L{k}": lab for k, lab in enumerate(
            left.labels[i] for i in range(left.n_nodes) if left.subtree_end[i] == i + 1
        )}
        blocks = [frozenset(token[t] for t in b) for b in seen["blocks"] if b]
        assert sorted(x for b in blocks for x in b) == sorted(labels)
        for block in blocks:
            # The agreement forest's promise, checked rather than trusted.
            assert _clusters(left, block) == _clusters(right, block)
        summary = result.summary
        assert summary["spr_lower"] <= summary["spr_upper"] <= len(labels) - 1
        largest = max(blocks, key=len)
        for this, other, side in ((left, right, result.left), (right, left, result.right)):
            for node in range(this.n_nodes):
                leaves = _leaves(this, node)
                assert side.columns["moved"][node] == len(leaves - largest)
                alone = sum(len(b & leaves) for b in blocks if len(b) == 1 and b != largest)
                assert side.columns["alone"][node] == alone
                assert side.columns["grouped"][node] == len(leaves - largest) - alone
                pieces = sum(1 for b in blocks if b & leaves)
                expected = 1.0 if len(leaves) == 1 else 1 - (pieces - 1) / (len(leaves) - 1)
                assert side.columns["similarity"][node] == pytest.approx(expected)
                counterpart = int(side.columns["corresponds"][node])
                assert leaves <= _leaves(other, counterpart)
                children = [
                    c for c in range(counterpart + 1, int(other.subtree_end[counterpart]))
                    if other.parent[c] == counterpart
                ]
                assert not any(leaves <= _leaves(other, c) for c in children)


@built
def test_the_lower_bound_is_a_third_of_the_approximation(monkeypatch):
    monkeypatch.setattr(spr_module, "EXACT_TRY_UP_TO", -1)
    rng = random.Random(7)
    labels = [f"t{i}" for i in range(30)]
    left, right, corr = _pair(_random_tree(labels, rng), _random_tree(labels, rng))
    trees = (
        spr_module._newick(left, {lab: lab for lab in labels})
        + "\n"
        + spr_module._newick(right, {lab: lab for lab in labels})
        + "\n"
    )
    approx = int(re.search(r"approx drSPR=(\d+)", spr_module._run(["-approx", "-q"], trees, None)).group(1))
    assert spr_module.compute(left, right, corr).summary["spr_lower"] == math.ceil(approx / 3)


def test_a_label_rspr_could_misread_is_never_sent_to_it():
    """`p` is how rspr prints the root, and Newick has its own syntax: labels go as L0..Ln."""
    left, _, _ = _pair("((p,A),(B,C));", "((p,B),(A,C));")
    token = {lab: f"L{k}" for k, lab in enumerate(["p", "A", "B", "C"])}
    assert spr_module._newick(left, token) == "((L0,L1),(L2,L3));"


def test_without_rspr_it_is_listed_as_unavailable(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "NATIVE_DIR", tmp_path)
    assert is_available(registry.discover()["spr"]) is False


def test_the_shipped_manifest_declares_its_range_and_its_two_colourings():
    manifest = registry.discover()["spr"]
    assert manifest.correspondence == "self"
    assert (manifest.headline.key, manifest.headline.to) == ("spr_lower", "spr_upper")
    assert [p.name for p in manifest.presentations] == ["branches", "leaves"]
    # Four kinds of leaf: the largest block, moved with others, moved alone,
    # and (drawn by the client) only in one tree.
    leaves = manifest.presentations[1]
    assert leaves.columns == ("grouped", "alone")
    assert len(leaves.categories) == 3
    assert manifest.raw["requires"] == ["${native}/rspr/rspr"]


def test_the_demo_is_one_comparison_per_metric(monkeypatch):
    from phylodelta.precompute import pipeline

    assert pipeline.DEMO_METRICS == ["rf", "mast", "spr", "triplet"]
    asked = {}
    monkeypatch.setattr(pipeline, "ingest_trees", lambda: 0)
    monkeypatch.setattr(pipeline, "ingest_isolates_all", lambda: 0)
    monkeypatch.setattr(
        pipeline, "compute_pairs", lambda **kw: asked.update(kw) or 0
    )
    assert pipeline.build_all() == 0
    assert asked["only"] == "vibrio-nj__vibrio-upgma"
    assert set(asked["metrics"]) <= set(pipeline.DEMO_METRICS)


# --- through an upload ----------------------------------------------------------------


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("PHYLODELTA_STORE", str(tmp_path))
    for name, sub in (
        ("STORE_DIR", ""), ("TREES_DIR", "trees"), ("PAIRS_DIR", "pairs"),
        ("ISOLATES_DIR", "isolates"),
    ):
        monkeypatch.setattr(config, name, tmp_path / sub if sub else tmp_path)
    monkeypatch.setenv("PHYLODELTA_AUTH", "header")
    from phylodelta.trees import registry as tree_registry

    db.reset()
    with db.using_store(tmp_path):
        db.create_schema()
        tree_registry.reset_cache()
        registry_pairs.reset_cache()
        yield TestClient(create_app(), raise_server_exceptions=False)
    registry_pairs.reset_cache()


@built
def test_an_upload_by_spr_is_its_own_comparison_coloured_by_its_forest(client):
    from phylodelta.precompute.jobs import process_next

    response = client.post(
        "/api/v1/comparisons",
        files={
            "left_tree": ("l.nwk", io.BytesIO(b"((((A,B),C),(D,E)),F);")),
            "right_tree": ("r.nwk", io.BytesIO(b"((((A,F),E),(D,C)),B);")),
        },
        data={"metrics": "spr"},
        headers=ALICE,
    )
    assert response.status_code == 202, response.text
    pair = response.json()["id"]
    assert process_next("w1") is True

    listed = [p for p in client.get("/api/v1/datasets", headers=ALICE).json()["pairs"] if p["id"] == pair]
    assert [(p["metric"], p["status"]) for p in listed] == [("spr", "ready")]

    summary = client.get(f"/api/v1/comparisons/{pair}?metric=spr", headers=ALICE).json()["summary"]
    assert summary["spr_lower"] == summary["spr_upper"] == 3

    body = client.get(
        f"/api/v1/trees/{pair.split('__')[0]}/slice",
        params={"budget": 50, "compare": pair, "metric": "spr", "correspondence": "metric"},
        headers=ALICE,
    ).json()
    values = body["comparison"]
    assert values["correspondence"] == "spr"
    assert set(values["columns"]) == {"moved", "grouped", "alone"}
    root = body["nodes"]["id"].index(0)
    assert values["similarity"][root] == pytest.approx(1 - 3 / 5)
    assert np.isclose(values["columns"]["moved"][root], 3.0)

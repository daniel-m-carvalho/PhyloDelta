"""Moved leaves: the maximum agreement subtree (§46).

What is promised, and tested here:

* the MAST is the largest set of leaves both trees arrange identically — its
  size matches phangorn, the tool the supervisor's script uses;
* the native and Python implementations keep exactly the same leaves, ties
  included;
* each node carries how many of its leaves moved, and a node outside the
  compared pair says "not measured", not zero;
* what cannot be computed is declined by name: a polytomy, a pair above the
  manifest's limit, a table that does not fit, a large pair without the
  native extension.
"""

from __future__ import annotations

import io
import random
import shutil
import subprocess
from pathlib import Path

import numpy as np
import pytest
from fastapi.testclient import TestClient

from phylodelta import config, db
from phylodelta.api.app import create_app
from phylodelta.api.identity import AUTH_HEADER
from phylodelta.metrics import registry
from phylodelta.metrics.contract import Limits, MetricManifest
from phylodelta.metrics.plugins.mast import mast as mast_module
from phylodelta.metrics.plugins.mast.mast import _inputs, agreement_python, compute
from phylodelta.metrics.runners import MetricFailed, make_runner
from phylodelta.trees import native
from phylodelta.trees.correspondence import compute_correspondence
from phylodelta.trees.newick import parse_newick
from phylodelta.trees.reconcile import reconcile

SERVER = Path(__file__).resolve().parents[1]
ORACLE = SERVER / "tools" / "mast_phangorn.R"


def _pair(left: str, right: str):
    left_r, right_r, _ = reconcile(parse_newick(left), parse_newick(right))
    return left_r, right_r, compute_correspondence(left_r, right_r)


def _moved(arrays, column) -> set[str]:
    return {
        arrays.labels[i]
        for i in range(arrays.n_nodes)
        if arrays.subtree_end[i] == i + 1 and column[i] == 1
    }


@pytest.fixture(params=["native", "python"])
def implementation(request, monkeypatch):
    """Every behavioural test runs on both implementations."""
    if request.param == "native":
        if not (native.available() and hasattr(native.extension(), "mast")):
            pytest.skip("native extension not built")
    else:
        monkeypatch.setattr(native, "extension", lambda: None)
    return request.param


# --- what it computes ------------------------------------------------------


def test_one_leaf_moved(implementation):
    left, right, corr = _pair("((((A,B),C),D),(E,F));", "((((A,B),D),C),(E,F));")
    result = compute(left, right, corr)
    assert result.summary["mast_size"] == 5
    assert result.summary["moved"] == 1
    # C or D: either one, removed, makes the trees agree. The fixed tie order
    # takes the first term, which keeps D.
    assert _moved(left, result.left.columns["moved"]) == {"C"}
    assert _moved(right, result.right.columns["moved"]) == {"C"}


def test_identical_trees_move_nothing(implementation):
    tree = "(((A,B),(C,D)),((E,F),G));"
    result = compute(*_pair(tree, tree))
    assert result.summary == {"mast_size": 7, "moved": 0, "moved_fraction": 0.0, "n_leaves": 7}
    assert not result.left.columns["moved"].any()


def test_a_ladder_against_its_reverse_keeps_two(implementation):
    # Every three leaves are grouped oppositely, so no three agree.
    result = compute(*_pair("(((((A,B),C),D),E),F);", "(((((F,E),D),C),B),A);"))
    assert result.summary["mast_size"] == 2


def test_each_node_counts_the_moved_leaves_beneath_it(implementation):
    left, right, corr = _pair(
        "(((A,B),(C,D)),((E,F),(G,H)));", "(((A,C),(B,D)),((E,F),(G,H)));"
    )
    result = compute(left, right, corr)
    column = result.left.columns["moved"]
    assert column.dtype == np.float32
    end = np.asarray(left.subtree_end)
    for i in range(left.n_nodes):
        leaves = [j for j in range(i, int(end[i])) if end[j] == j + 1]
        assert column[i] == sum(column[j] for j in leaves)
    assert column[0] == result.summary["moved"]
    assert result.summary["mast_size"] == 6


def test_a_polytomy_is_refused_by_name():
    # Reconciliation already refuses a tree that is not rooted binary
    # (trees/normalise.py), so a polytomy cannot reach the metric through the
    # pipeline; the check is the metric's own, for any other caller.
    polytomy, binary = parse_newick("(A,B,C);"), parse_newick("((A,B),C);")
    with pytest.raises(MetricFailed, match="binary trees; node 0 .* left tree has 3 children"):
        compute(polytomy, binary, None)


# --- the two implementations agree ------------------------------------------


def _random_shape(labels, rng):
    nodes = list(labels)
    while len(nodes) > 1:
        i, j = sorted(rng.sample(range(len(nodes)), 2))
        b, a = nodes.pop(j), nodes.pop(i)
        nodes.append((a, b))
    return nodes[0]


def _render(shape, name=lambda x: x) -> str:
    if isinstance(shape, tuple):
        return f"({_render(shape[0], name)},{_render(shape[1], name)})"
    return name(shape)


def _random_pairs(count: int, sizes, seed: int):
    """Unrelated pairs and lightly shuffled copies, so the MAST is both small and large."""
    rng = random.Random(seed)
    for k in range(count):
        n = rng.choice(sizes)
        labels = [f"L{i}" for i in range(n)]
        shape = _random_shape(labels, rng)
        if k % 2:
            swap = {x: x for x in labels}
            for _ in range(max(1, n // 8)):
                i, j = rng.sample(labels, 2)
                swap[i], swap[j] = swap[j], swap[i]
            other = _render(shape, lambda x, swap=swap: swap[x])
        else:
            other = _render(_random_shape(labels, rng))
        yield _render(shape) + ";", other + ";"


@pytest.mark.skipif(
    not (native.available() and hasattr(native.extension(), "mast")),
    reason="native extension not built",
)
def test_native_keeps_exactly_the_leaves_python_keeps():
    for left_text, right_text in _random_pairs(150, [2, 3, 5, 12, 40, 120], seed=3):
        inputs = _inputs(*_pair(left_text, right_text))
        expected = agreement_python(**inputs)
        actual = np.asarray(native.extension().mast(**inputs), dtype=bool)
        assert np.array_equal(actual, expected), (left_text, right_text)


# --- against phangorn, the supervisor's tool ----------------------------------


def _phangorn_available() -> bool:
    if shutil.which("Rscript") is None:
        return False
    probe = subprocess.run(
        ["Rscript", "-e", "quit(status = !requireNamespace('phangorn', quietly = TRUE))"],
        capture_output=True,
    )
    return probe.returncode == 0


needs_phangorn = pytest.mark.skipif(
    not _phangorn_available(), reason="Rscript with phangorn is not installed"
)


def _phangorn_size(tmp_path, left_text, right_text) -> int:
    (tmp_path / "l.nwk").write_text(left_text)
    (tmp_path / "r.nwk").write_text(right_text)
    out = subprocess.run(
        ["Rscript", str(ORACLE), str(tmp_path / "l.nwk"), str(tmp_path / "r.nwk")],
        capture_output=True, text=True, check=True,
    ).stdout
    return int(out.splitlines()[0].split("\t")[1])


@needs_phangorn
def test_the_agreement_is_as_large_as_phangorns(tmp_path):
    for left_text, right_text in _random_pairs(20, [10, 30, 80, 200], seed=11):
        ours = compute(*_pair(left_text, right_text)).summary["mast_size"]
        assert ours == _phangorn_size(tmp_path, left_text, right_text), (left_text, right_text)


@needs_phangorn
def test_phangorns_default_reports_every_leaf_as_moved(tmp_path):
    """The bug in the supervisor's script, kept as evidence (§46).

    `mast()` returns a tree unless told `tree = FALSE`, and `setdiff` of the
    leaf labels against a tree object leaves every label.
    """
    (tmp_path / "l.nwk").write_text("((((A,B),C),D),(E,F));")
    (tmp_path / "r.nwk").write_text("((((A,B),D),C),(E,F));")
    script = (
        "suppressPackageStartupMessages(library(phangorn));"
        f"t1 <- read.tree('{tmp_path / 'l.nwk'}'); t2 <- read.tree('{tmp_path / 'r.nwk'}');"
        "cat(length(setdiff(t1$tip.label, mast(t1, t2))))"
    )
    as_written = subprocess.run(["Rscript", "-e", script], capture_output=True, text=True, check=True)
    assert as_written.stdout.strip() == "6", "the script's form reports all six leaves as moved"


# --- declining by name ------------------------------------------------------------


def test_the_python_path_declines_a_large_pair(monkeypatch):
    monkeypatch.setattr(native, "extension", lambda: None)
    monkeypatch.setattr(mast_module, "PYTHON_MAX_LEAVES", 4)
    with pytest.raises(MetricFailed, match="needs the native extension"):
        compute(*_pair("(((A,B),(C,D)),(E,F));", "(((A,B),(C,D)),(E,F));"))


def test_a_table_that_does_not_fit_is_declined(monkeypatch):
    class OutOfMemory:
        def mast(self, **_):
            raise MemoryError

    pair = _pair("((A,B),C);", "((A,C),B);")
    monkeypatch.setattr(native, "extension", lambda: OutOfMemory())
    with pytest.raises(MetricFailed, match="does not fit in this machine's memory"):
        compute(*pair)


def test_limits_are_parsed():
    assert Limits.from_json({"max_leaves": 10}, "m").max_leaves == 10
    assert Limits.from_json({}, "m").max_leaves is None


@pytest.mark.parametrize(
    "raw, says",
    [
        ({"max_leafs": 10}, "unknown limit"),
        ({"max_leaves": 0}, "positive integer"),
        ({"max_leaves": "10"}, "positive integer"),
        ({"max_leaves": True}, "positive integer"),
        ([10], "must be an object"),
    ],
)
def test_a_malformed_limit_is_refused_by_name(raw, says):
    with pytest.raises(ValueError, match=says):
        Limits.from_json(raw, "m")


def test_a_pair_above_the_limit_is_declined_before_it_runs():
    manifest = registry.discover()["mast"]
    small = MetricManifest.from_json({**manifest.raw, "limits": {"max_leaves": 3}})
    run = make_runner(small)

    class Prepared:
        left, right, correspondence = _pair("((A,B),(C,D));", "((A,C),(B,D));")
        files = None

    with pytest.raises(MetricFailed, match="declined: 4 shared leaves, above this metric's limit of 3"):
        run(Prepared())


def test_the_shipped_manifest_has_a_limit_and_says_where_it_comes_from():
    manifest = registry.discover()["mast"]
    assert manifest.limits.max_leaves == 40_000
    assert "PhyloDelta's own implementation" in manifest.reference.citation
    assert "Steel" in manifest.reference.citation
    assert manifest.reference.doi == "10.1016/0020-0190(93)90181-8"


# --- through an upload ------------------------------------------------------------


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("PHYLODELTA_STORE", str(tmp_path))
    for name, sub in (
        ("STORE_DIR", ""), ("TREES_DIR", "trees"), ("PAIRS_DIR", "pairs"),
        ("ISOLATES_DIR", "isolates"), ("SCRATCH_DIR", "scratch"),
    ):
        monkeypatch.setattr(config, name, tmp_path / sub if sub else tmp_path)
    monkeypatch.setenv("PHYLODELTA_AUTH", "header")
    from phylodelta.metrics import registry_pairs
    from phylodelta.trees import registry as tree_registry

    db.reset()
    with db.using_store(tmp_path):
        db.create_schema()
        tree_registry.reset_cache()
        registry_pairs.reset_cache()
        yield TestClient(create_app(), raise_server_exceptions=False)


def _upload(client, left: bytes, right: bytes, metrics: str) -> str:
    response = client.post(
        "/api/v1/comparisons",
        files={"left_tree": ("l.nwk", io.BytesIO(left)), "right_tree": ("r.nwk", io.BytesIO(right))},
        data={"metrics": metrics},
        headers={AUTH_HEADER: "alice"},
    )
    assert response.status_code == 202, response.text
    return response.json()["id"]


def test_an_upload_gets_moved_leaves_and_a_leaf_only_one_tree_has_is_not_measured(client):
    from phylodelta.precompute.jobs import process_next

    # E is only on the left: left out of the comparison, so not "kept" and not "moved".
    pair = _upload(
        client, b"(((((A,B),C),D),E),F);", b"((((A,B),D),C),F);", "rf,mast"
    )
    assert process_next("w1") is True
    status = client.get(f"/api/v1/comparisons/{pair}/status", headers={AUTH_HEADER: "alice"}).json()
    assert status["status"] == "ready"
    assert status["metrics_ready"] == ["mast", "rf"]

    summary = client.get(
        f"/api/v1/comparisons/{pair}?metric=mast", headers={AUTH_HEADER: "alice"}
    ).json()["summary"]
    assert summary["n_leaves"] == 5 and summary["moved"] == 1

    left_id = pair.split("__")[0]
    sliced = client.get(
        f"/api/v1/trees/{left_id}/slice?budget=50&compare={pair}&metric=mast",
        headers={AUTH_HEADER: "alice"},
    ).json()
    by_label = dict(zip(sliced["nodes"]["label"], sliced["comparison"]["columns"]["moved"], strict=True))
    assert by_label["E"] is None, "a leaf only one tree has must read as not measured"
    assert by_label["C"] == 1 and by_label["A"] == 0


def test_a_declined_mast_is_named_and_the_comparison_is_still_ready(client, monkeypatch):
    from phylodelta.precompute.jobs import process_next

    shipped = registry.discover()

    def small_limit(plugins_dir=None):
        found = dict(shipped)
        found["mast"] = MetricManifest.from_json(
            {**shipped["mast"].raw, "limits": {"max_leaves": 3}},
            directory=shipped["mast"].directory,
        )
        return found

    monkeypatch.setattr(registry, "discover", small_limit)
    pair = _upload(client, b"((A,B),(C,D));", b"((A,C),(B,D));", "rf,mast")
    assert process_next("w1") is True
    status = client.get(f"/api/v1/comparisons/{pair}/status", headers={AUTH_HEADER: "alice"}).json()
    assert status["status"] == "ready"
    assert status["metrics_ready"] == ["rf"]
    assert "above this metric's limit of 3" in status["metrics_failed"]["mast"]

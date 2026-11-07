"""Each metric declares its correspondence (§52).

What is promised, and tested here:

* a manifest says which correspondence colours its metric — the shared Jaccard
  search by default, or ``self`` — and anything else is refused by name;
* ``self`` means the metric returns ``similarity`` and ``corresponds`` with the
  shared one's types, and no other metric may use those names;
* MAST's own correspondence is the agreement subtree: a clade's share of kept
  leaves, linked to where those leaves meet in the other tree;
* a request chooses with ``correspondence=shared|metric``. ``shared`` is the
  default and serves exactly what was served before; ``metric`` serves the
  metric's own and says so;
* the claim itself: a metric nobody wrote server code for — a directory with a
  manifest and a function — brings its own correspondence through the same
  routes, ordering included.
"""

from __future__ import annotations

import io
import json
import random
import shutil

import numpy as np
import pytest
from fastapi.testclient import TestClient

from phylodelta import config, db
from phylodelta.api.app import create_app
from phylodelta.api.identity import AUTH_HEADER
from phylodelta.metrics import registry, registry_pairs, store
from phylodelta.metrics.contract import (
    MetricManifest,
    MetricResult,
    MetricSide,
    validate_result,
)
from phylodelta.metrics.plugins.mast.mast import compute as mast
from phylodelta.trees import native
from phylodelta.trees.correspondence import _leaf_index, compute_correspondence
from phylodelta.trees.newick import parse_newick
from phylodelta.trees.reconcile import reconcile

ALICE = {AUTH_HEADER: "alice"}


# --- the manifest ---------------------------------------------------------------


def _manifest(**extra) -> dict:
    return {"name": "m", "title": "M", "kind": "python", "entrypoint": "x:y", **extra}


def _own(similarity="float32", corresponds="uint32", **extra) -> dict:
    return _manifest(
        correspondence="self",
        outputs={"columns": [
            {"name": "similarity", "dtype": similarity, "semantics": "ratio"},
            {"name": "corresponds", "dtype": corresponds, "semantics": "index"},
        ]},
        **extra,
    )


def test_the_shared_correspondence_is_the_default():
    assert MetricManifest.from_json(_manifest()).correspondence == "jaccard"


def test_a_metric_may_declare_its_own():
    assert MetricManifest.from_json(_own()).correspondence == "self"


def test_an_unknown_correspondence_is_refused_by_name():
    with pytest.raises(ValueError, match=r"unknown correspondence 'own'.*'jaccard', 'self'"):
        MetricManifest.from_json(_manifest(correspondence="own"))


def test_its_own_correspondence_needs_both_columns():
    raw = _own()
    raw["outputs"]["columns"].pop()
    with pytest.raises(ValueError, match="needs a column 'corresponds'"):
        MetricManifest.from_json(raw)


def test_its_own_columns_must_be_stored_as_the_shared_ones_are():
    with pytest.raises(ValueError, match="'corresponds' must be uint32"):
        MetricManifest.from_json(_own(corresponds="int64"))


def test_only_a_metric_with_its_own_correspondence_may_use_the_names():
    raw = _manifest(outputs={"columns": [
        {"name": "similarity", "dtype": "float32", "semantics": "ratio"},
    ]})
    with pytest.raises(ValueError, match=r"\['similarity'\] are reserved"):
        MetricManifest.from_json(raw)


def test_the_shipped_metrics_declare_what_colours_them():
    declared = {name: m.correspondence for name, m in registry.discover().items()}
    assert declared == {
        "rf": "jaccard", "rf-treediff": "jaccard", "triplet": "self", "mast": "self",
        "spr": "self",
    }


# --- MAST's own correspondence -----------------------------------------------------


def _pair(left: str, right: str):
    left_r, right_r, _ = reconcile(parse_newick(left), parse_newick(right))
    return left_r, right_r, compute_correspondence(left_r, right_r)


def _leaves(arrays, node: int) -> set[str]:
    end = arrays.subtree_end
    return {
        arrays.labels[i] for i in range(node, int(end[node])) if end[i] == i + 1
    }


def _random_tree(labels: list[str], rng: random.Random) -> str:
    nodes = labels[:]
    rng.shuffle(nodes)
    while len(nodes) > 1:
        a, b = nodes.pop(rng.randrange(len(nodes))), nodes.pop(rng.randrange(len(nodes)))
        nodes.append(f"({a},{b})")
    return nodes[0] + ";"


@pytest.fixture
def python_mast(monkeypatch):
    """The reference implementation: these trees are small, and it needs no build."""
    monkeypatch.setattr(native, "extension", lambda: None)


def test_one_moved_leaf_is_named_by_the_agreement_subtree(python_mast):
    left, right, corr = _pair("((((A,B),C),D),E);", "((((A,B),D),C),E);")
    result = mast(left, right, corr)
    validate_result(result, registry.discover()["mast"])
    side = result.left.columns
    by_label = {left.labels[i]: i for i in range(left.n_nodes) if left.labels[i]}
    moved = {lab for lab, i in by_label.items() if side["moved"][i] == 1}
    assert len(moved) == 1
    for label, i in by_label.items():
        # A leaf is linked to itself, kept or moved; only its score differs.
        assert right.labels[int(side["corresponds"][i])] == label
        assert side["similarity"][i] == (0.0 if label in moved else 1.0)
    assert side["similarity"][0] == pytest.approx(4 / 5)


def test_identical_trees_correspond_node_for_node(python_mast):
    newick = "(((A,B),(C,D)),E);"
    left, right, corr = _pair(newick, newick)
    side = mast(left, right, corr).left.columns
    assert np.all(side["similarity"] == 1.0)
    assert side["corresponds"].tolist() == list(range(left.n_nodes))


def test_on_random_pairs_each_clade_points_at_the_smallest_clade_holding_its_kept_leaves(
    python_mast,
):
    rng = random.Random(52)
    labels = [f"t{i}" for i in range(14)]
    for _ in range(60):
        left, right, corr = _pair(_random_tree(labels, rng), _random_tree(labels, rng))
        result = mast(left, right, corr)
        for this, other, side in ((left, right, result.left), (right, left, result.right)):
            moved = side.columns["moved"]
            moved_leaves = {
                this.labels[i] for i in range(this.n_nodes)
                if this.subtree_end[i] == i + 1 and moved[i] == 1
            }
            for node in range(this.n_nodes):
                leaves = _leaves(this, node)
                kept = leaves - moved_leaves
                assert side.columns["similarity"][node] == pytest.approx(len(kept) / len(leaves))
                target = kept or leaves
                counterpart = int(side.columns["corresponds"][node])
                assert target <= _leaves(other, counterpart)
                children = [
                    c for c in range(counterpart + 1, int(other.subtree_end[counterpart]))
                    if other.parent[c] == counterpart
                ]
                assert not any(target <= _leaves(other, c) for c in children), (
                    "not the smallest clade holding them"
                )


# --- through the API -------------------------------------------------------------


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


def _computed(client, left: bytes, right: bytes, metrics: str) -> str:
    from phylodelta.precompute.jobs import process_next

    response = client.post(
        "/api/v1/comparisons",
        files={"left_tree": ("l.nwk", io.BytesIO(left)), "right_tree": ("r.nwk", io.BytesIO(right))},
        data={"metrics": metrics},
        headers=ALICE,
    )
    assert response.status_code == 202, response.text
    assert process_next("w1") is True
    return response.json()["id"]


LEFT = b"(((((A,B),C),D),E),(F,G));"
RIGHT = b"((((A,B),D),(F,C)),(G,E));"


def _slice(client, pair: str, **params) -> dict:
    left = pair.split("__")[0]
    got = client.get(
        f"/api/v1/trees/{left}/slice",
        params={"budget": 50, "compare": pair, **params},
        headers=ALICE,
    )
    assert got.status_code == 200, got.text
    return got.json()


def test_the_shared_correspondence_is_still_what_a_slice_serves_by_default(python_mast, client):
    pair = _computed(client, LEFT, RIGHT, "rf,mast")
    before = _slice(client, pair, metric="mast")
    assert before["comparison"]["correspondence"] == "jaccard"
    assert _slice(client, pair, metric="mast", correspondence="shared") == before
    assert _slice(client, pair, metric="rf")["comparison"]["similarity"] == (
        before["comparison"]["similarity"]
    )


def test_asking_for_the_metrics_own_serves_and_names_it(python_mast, client):
    pair = _computed(client, LEFT, RIGHT, "rf,mast")
    shared = _slice(client, pair, metric="mast")["comparison"]
    body = _slice(client, pair, metric="mast", correspondence="metric")
    own = body["comparison"]
    assert own["correspondence"] == "mast"
    assert own["similarity"] != shared["similarity"]
    # Served in the two fields, never again as columns.
    assert set(own["columns"]) == {"moved"}

    right = pair.split("__")[1]
    other = client.get(
        f"/api/v1/trees/{right}/slice", params={"budget": 50}, headers=ALICE
    ).json()["nodes"]
    label_of = dict(zip(other["id"], other["label"], strict=True))
    nodes = body["nodes"]
    for k in range(len(nodes["id"])):
        is_leaf = k not in nodes["parent"]
        if is_leaf and own["corresponds"][k] is not None:
            assert label_of[own["corresponds"][k]] == nodes["label"][k]
        if own["columns"]["moved"][k] is not None and is_leaf:
            assert own["similarity"][k] == 1.0 - own["columns"]["moved"][k]


def test_a_metric_that_declares_the_shared_one_serves_it_when_asked_for_its_own(
    python_mast, client
):
    pair = _computed(client, LEFT, RIGHT, "rf,mast")
    asked = _slice(client, pair, metric="rf", correspondence="metric")["comparison"]
    assert asked["correspondence"] == "jaccard"
    assert asked == _slice(client, pair, metric="rf")["comparison"]


def test_the_comparison_slice_route_takes_the_same_choice(python_mast, client):
    pair = _computed(client, LEFT, RIGHT, "rf,mast")
    left = pair.split("__")[0]
    params = {"tree": left, "budget": 50, "metric": "mast", "correspondence": "metric"}
    got = client.get(f"/api/v1/comparisons/{pair}/slice", params=params, headers=ALICE).json()
    assert got["nodes"] == _slice(client, pair, metric="mast", correspondence="metric")["comparison"]


def test_an_unknown_choice_is_refused(python_mast, client):
    pair = _computed(client, LEFT, RIGHT, "rf,mast")
    left = pair.split("__")[0]
    got = client.get(
        f"/api/v1/trees/{left}/slice",
        params={"compare": pair, "metric": "mast", "correspondence": "own"},
        headers=ALICE,
    )
    assert got.status_code == 422


def test_metrics_say_which_correspondence_is_theirs(client):
    metrics = {m["name"]: m for m in client.get("/api/v1/metrics", headers=ALICE).json()}
    assert metrics["mast"]["correspondence"] == "self"
    assert metrics["rf"]["correspondence"] == "jaccard"
    columns = {c["name"]: c for c in metrics["mast"]["outputs"]["columns"]}
    assert columns["similarity"]["label"], "a legend needs to say what the score means"


def test_a_result_computed_before_it_had_its_own_correspondence_is_refused_by_name(
    python_mast, client, tmp_path
):
    pair = _computed(client, LEFT, RIGHT, "rf,mast")
    directory = tmp_path / "pairs" / pair / "mast"
    header = json.loads((directory / "meta.json").read_text())
    for side in ("left", "right"):
        for name in ("similarity", "corresponds"):
            header["schema"][side].pop(name)
    (directory / "meta.json").write_text(json.dumps(header))
    registry_pairs.reset_cache()

    got = client.get(
        f"/api/v1/trees/{pair.split('__')[0]}/slice",
        params={"compare": pair, "metric": "mast", "correspondence": "metric"},
        headers=ALICE,
    )
    assert got.status_code == 409, got.text
    body = got.json()
    assert body["code"] == "correspondence_not_computed"
    assert "--metric mast" in body["detail"]
    # The shared one is untouched.
    assert _slice(client, pair, metric="mast")["comparison"]["correspondence"] == "jaccard"


# --- the claim: a metric nobody wrote server code for ---------------------------------


def toy(left, right, correspondence):
    """A metric that is nothing but its own correspondence.

    Every leaf is linked to its namesake and scores 1 if its label sorts
    before "D", else 0; a clade scores the mean of its leaves and is linked to
    the other tree's root. Meaningless as biology, and exactly what a test
    needs: values no shared correspondence would produce.
    """

    def side(this, other, this_in_other):
        _, other_leaf_node = _leaf_index(other)
        end = np.asarray(this.subtree_end)
        is_leaf = end == np.arange(this.n_nodes) + 1
        score = np.array([float(lab < "D") if leaf else 0.0
                          for lab, leaf in zip(this.labels, is_leaf, strict=True)])
        running = np.concatenate(([0.0], np.cumsum(score * is_leaf)))
        similarity = (running[end] - running[np.arange(this.n_nodes)]) / np.asarray(
            this.leaf_count, dtype=float
        )
        corresponds = np.zeros(this.n_nodes, dtype=np.uint32)
        corresponds[is_leaf] = other_leaf_node[np.asarray(this_in_other)[is_leaf]]
        return MetricSide(columns={
            "similarity": similarity.astype(np.float32), "corresponds": corresponds,
        })

    return MetricResult(
        name="toy",
        summary={"value": 1},
        left=side(left, right, correspondence.left_to_right),
        right=side(right, left, correspondence.right_to_left),
    )


@pytest.fixture
def toy_plugins(tmp_path, monkeypatch):
    """The shipped plugins plus one more, added the way anyone would add one."""
    plugins = tmp_path / "plugins"
    shutil.copytree(registry.PLUGINS_DIR, plugins, ignore=shutil.ignore_patterns("__pycache__"))
    (plugins / "toy").mkdir()
    (plugins / "toy" / "metric.json").write_text(json.dumps({
        "name": "toy", "title": "Toy", "kind": "python",
        "entrypoint": "test_correspondence_per_metric:toy",
        "correspondence": "self",
        "outputs": {"columns": [
            {"name": "similarity", "dtype": "float32", "semantics": "ratio",
             "label": "Share of leaves before D", "render": "gradient"},
            {"name": "corresponds", "dtype": "uint32", "semantics": "index", "render": "link"},
        ]},
    }))
    monkeypatch.setattr(registry, "PLUGINS_DIR", plugins)
    monkeypatch.setattr(store, "_declared", None)
    registry_pairs.reset_cache()
    yield plugins
    store._declared = None
    registry_pairs.reset_cache()


def test_a_new_metric_brings_its_own_correspondence_with_no_server_code(toy_plugins, client):
    metrics = {m["name"]: m for m in client.get("/api/v1/metrics", headers=ALICE).json()}
    assert metrics["toy"]["correspondence"] == "self"

    pair = _computed(client, LEFT, RIGHT, "rf,toy")
    status = client.get(f"/api/v1/comparisons/{pair}/status", headers=ALICE).json()
    assert status["metrics_ready"] == ["rf", "toy"], status

    body = _slice(client, pair, metric="toy", correspondence="metric")
    own = body["comparison"]
    assert own["correspondence"] == "toy"
    nodes = body["nodes"]
    for k, label in enumerate(nodes["label"]):
        if label and own["similarity"][k] is not None:
            assert own["similarity"][k] == float(label < "D")
    assert own["similarity"][0] == pytest.approx(3 / 7)

    # "Most different first" follows the toy's own notion of different.
    ordered = _slice(client, pair, metric="toy", correspondence="metric",
                     order="difference", budget=2)
    assert ordered["comparison"]["correspondence"] == "toy"


# --- one comparison, one metric ----------------------------------------------------


def test_a_metric_declares_how_it_can_colour_the_trees():
    raw = _own()
    raw["outputs"]["columns"].append({"name": "moved", "dtype": "float32", "semantics": "count"})
    raw["presentations"] = [
        {"name": "branches", "label": "Share kept", "kind": "gradient"},
        {"name": "leaves", "label": "Kept or moved", "kind": "categories",
         "column": "moved", "categories": ["Kept", "Moved"]},
    ]
    manifest = MetricManifest.from_json(raw)
    assert [p.name for p in manifest.presentations] == ["branches", "leaves"]
    assert manifest.presentations[1].categories == ("Kept", "Moved")


def test_more_kinds_of_leaf_are_one_column_each_and_one_label_more():
    raw = _own()
    for name in ("moved", "alone"):
        raw["outputs"]["columns"].append({"name": name, "dtype": "float32", "semantics": "count"})
    raw["presentations"] = [
        {"name": "leaves", "label": "Kept, moved or alone", "kind": "categories",
         "columns": ["moved", "alone"], "categories": ["Kept", "Moved", "Alone"]},
    ]
    shown = MetricManifest.from_json(raw).presentations[0]
    assert shown.columns == ("moved", "alone")
    assert shown.column == "moved"  # what a client reading one column gets
    assert shown.categories == ("Kept", "Moved", "Alone")


def test_a_gradient_says_below_what_size_its_score_says_nothing():
    # The shared one: a leaf always matches itself, so its branch is grey.
    assert MetricManifest.from_json(_manifest()).presentations[0].min_leaves == 2
    shipped = registry.discover()
    assert shipped["triplet"].presentations[0].min_leaves == 3  # no triple in two leaves
    assert shipped["spr"].presentations[0].min_leaves == 2  # a leaf is always one piece
    assert shipped["mast"].presentations[0].min_leaves == 1  # a leaf is kept or moved


def test_a_metric_that_declares_none_is_drawn_by_its_correspondence():
    assert [p.label for p in MetricManifest.from_json(_manifest()).presentations] == ["Divergence"]
    own = _own()
    own["outputs"]["columns"][0]["label"] = "Share kept"
    assert [p.label for p in MetricManifest.from_json(own).presentations] == ["Share kept"]


@pytest.mark.parametrize(
    ("presentation", "says"),
    [
        ({"name": "x", "label": "X", "kind": "pie"}, "has kind 'pie'"),
        ({"name": "x", "label": "X", "kind": "categories", "column": "similarity",
          "categories": ["a", "b"]}, "semantics 'count'"),
        ({"name": "x", "label": "X", "kind": "categories", "column": "moved"}, "needs 'categories'"),
        ({"label": "X", "kind": "gradient"}, "needs a 'name'"),
        ({"name": "x", "label": "X", "kind": "gradient", "min_leaves": 0}, "at least 1"),
        ({"name": "x", "label": "X", "kind": "gradient", "min_leaves": "2"}, "min_leaves"),
        ({"name": "x", "label": "X", "kind": "categories", "columns": ["moved"],
          "categories": ["a", "b", "c"]}, "2 labels"),
        ({"name": "x", "label": "X", "kind": "categories", "columns": ["moved", "moved"],
          "categories": ["a", "b", "c"]}, "repeats a column"),
        ({"name": "x", "label": "X", "kind": "categories"}, "paints by 'column'"),
    ],
)
def test_a_malformed_presentation_is_refused_by_name(presentation, says):
    raw = _own()
    raw["outputs"]["columns"].append({"name": "moved", "dtype": "float32", "semantics": "count"})
    raw["presentations"] = [presentation]
    with pytest.raises(ValueError, match=says):
        MetricManifest.from_json(raw)


def test_two_presentations_may_not_share_a_name():
    raw = _manifest(presentations=[
        {"name": "x", "label": "A", "kind": "gradient"},
        {"name": "x", "label": "B", "kind": "gradient"},
    ])
    with pytest.raises(ValueError, match="names repeat"):
        MetricManifest.from_json(raw)


def test_mast_offers_its_two_colourings_and_its_number(client):
    metrics = {m["name"]: m for m in client.get("/api/v1/metrics", headers=ALICE).json()}
    assert [p["name"] for p in metrics["mast"]["presentations"]] == ["branches", "leaves"]
    assert metrics["mast"]["headline"] == {"key": "moved", "of": "n_leaves", "to": ""}
    assert [p["name"] for p in metrics["rf"]["presentations"]] == ["divergence"]


def _listed(client) -> list[dict]:
    return client.get("/api/v1/datasets", headers=ALICE).json()["pairs"]


def test_a_pair_computed_with_two_metrics_is_two_comparisons(python_mast, client):
    pair = _computed(client, LEFT, RIGHT, "rf,mast")
    entries = [p for p in _listed(client) if p["id"] == pair]
    assert [(p["metric"], p["status"]) for p in entries] == [("rf", "ready"), ("mast", "ready")]


def test_a_metric_that_declined_is_listed_as_its_failed_comparison(python_mast, client, monkeypatch):
    from phylodelta.metrics.plugins.mast import mast as mast_module
    from phylodelta.metrics.runners import MetricFailed

    def declined(*_):
        raise MetricFailed("declined: for this test")

    monkeypatch.setattr(mast_module, "agreement", declined)
    pair = _computed(client, LEFT, RIGHT, "rf,mast")
    entries = {p["metric"]: p for p in _listed(client) if p["id"] == pair}
    assert entries["rf"]["status"] == "ready"
    assert entries["mast"]["status"] == "failed"
    assert "declined: for this test" in entries["mast"]["error"]


def test_removing_one_metrics_comparison_keeps_the_others(python_mast, client, tmp_path):
    pair = _computed(client, LEFT, RIGHT, "rf,mast")
    gone = client.delete(f"/api/v1/comparisons/{pair}", params={"metric": "mast"}, headers=ALICE)
    assert gone.status_code == 200, gone.text
    assert gone.json()["datasets_removed"] == []
    assert [p["metric"] for p in _listed(client) if p["id"] == pair] == ["rf"]
    assert not (tmp_path / "pairs" / pair / "mast").exists()
    # The rest still opens.
    assert _slice(client, pair, metric="rf")["comparison"]["correspondence"] == "jaccard"

    # The last one takes the trees with it, as deleting a comparison always did.
    last = client.delete(f"/api/v1/comparisons/{pair}", params={"metric": "rf"}, headers=ALICE)
    assert last.status_code == 200
    assert sorted(last.json()["datasets_removed"]) == sorted(pair.split("__"))
    assert [p for p in _listed(client) if p["id"] == pair] == []


def test_removing_a_metric_the_comparison_lacks_is_refused_by_name(python_mast, client):
    pair = _computed(client, LEFT, RIGHT, "rf,mast")
    got = client.delete(f"/api/v1/comparisons/{pair}", params={"metric": "triplet"}, headers=ALICE)
    assert got.status_code == 404
    assert got.json()["code"] == "metric_not_computed"
    assert len([p for p in _listed(client) if p["id"] == pair]) == 2

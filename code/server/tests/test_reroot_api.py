"""Re-rooting a comparison through the API, end to end (§56).

Each test drives the real path — POST the re-root, run the worker, read the
result — because the promises are about what the user sees afterwards: a new
comparison with new ids, its own metrics, the same typing data, and an original
that is kept, marked, or replaced exactly as asked, and untouched if the build
fails.
"""

from __future__ import annotations

import io
import random

import pytest
from fastapi.testclient import TestClient

from phylodelta import config, db
from phylodelta.api.app import create_app
from phylodelta.api.identity import AUTH_HEADER
from phylodelta.precompute import jobs
from phylodelta.trees.newick import NO_PARENT, parse_newick

ALICE = {AUTH_HEADER: "alice"}
BOB = {AUTH_HEADER: "bob"}


def _random_tree(n: int, seed: int) -> str:
    rng = random.Random(seed)
    nodes = [f"{i}:{rng.uniform(0.1, 2):.3f}" for i in range(1, n + 1)]
    while len(nodes) > 1:
        a = nodes.pop(rng.randrange(len(nodes)))
        b = nodes.pop(rng.randrange(len(nodes)))
        nodes.append(f"({a},{b}):{rng.uniform(0.1, 2):.3f}")
    return nodes[0] + ";"


TREE = _random_tree(24, 7)
TABLE = "ST\tcountry\tsource\n" + "".join(
    f"{i}\t{['PT', 'ES', 'FR'][i % 3]}\t{['Human', 'Food'][i % 2]}\n"
    for i in range(1, 25)
    for _ in range(1 + i % 3)  # one to three isolates per ST
)


def _deep_node(newick: str) -> int:
    """A node far from the root: re-rooting there changes many clades."""
    t = parse_newick(newick)
    candidates = [
        i for i in range(t.n_nodes)
        if t.parent[i] != NO_PARENT and t.parent[t.parent[i]] != NO_PARENT and not t.is_leaf(i)
    ]
    return max(candidates, key=lambda i: t.depth[i])


@pytest.fixture
def store(tmp_path, monkeypatch):
    monkeypatch.setenv("PHYLODELTA_STORE", str(tmp_path))
    monkeypatch.setattr(config, "STORE_DIR", tmp_path)
    monkeypatch.setattr(config, "TREES_DIR", tmp_path / "trees")
    monkeypatch.setattr(config, "PAIRS_DIR", tmp_path / "pairs")
    monkeypatch.setattr(config, "ISOLATES_DIR", tmp_path / "isolates")
    monkeypatch.setenv("PHYLODELTA_AUTH", "header")
    db.reset()
    with db.using_store(tmp_path):
        db.create_schema()
        yield tmp_path


@pytest.fixture
def client(store):
    from phylodelta.isolates import registry as isolate_registry
    from phylodelta.metrics import registry_pairs
    from phylodelta.trees import registry

    registry.reset_cache()
    registry_pairs.reset_cache()
    isolate_registry.reset_cache()
    return TestClient(create_app(), raise_server_exceptions=False)


def _built(client, left: str, right: str, table: str | None = None, metrics: str = "rf") -> str:
    files = {
        "left_tree": ("left.nwk", io.BytesIO(left.encode())),
        "right_tree": ("right.nwk", io.BytesIO(right.encode())),
    }
    data = {"metrics": metrics}
    if table is not None:
        files["left_isolates"] = ("isolates.tsv", io.BytesIO(table.encode()))
        data["isolates_shared"] = "true"
    response = client.post("/api/v1/comparisons", files=files, data=data, headers=ALICE)
    assert response.status_code == 202, response.text
    comparison = response.json()["id"]
    assert jobs.process_next("test") is True
    assert _status(client, comparison)["status"] == "ready", _status(client, comparison)
    return comparison


def _status(client, comparison: str, headers=ALICE) -> dict:
    return client.get(f"/api/v1/comparisons/{comparison}/status", headers=headers).json()


def _rf(client, comparison: str) -> int:
    body = client.get(f"/api/v1/comparisons/{comparison}", params={"metric": "rf"}, headers=ALICE)
    assert body.status_code == 200, body.text
    return body.json()["summary"]["rf"]


def _reroot(client, comparison: str, headers=ALICE, **body):
    return client.post(f"/api/v1/comparisons/{comparison}/reroot", json=body, headers=headers)


def _rebuilt(client, comparison: str, **body) -> str:
    response = _reroot(client, comparison, **body)
    assert response.status_code == 202, response.text
    new = response.json()["id"]
    assert jobs.process_next("test") is True
    return new


def test_a_reroot_builds_a_new_comparison_with_new_ids(client):
    original = _built(client, TREE, TREE)
    assert _rf(client, original) == 0
    new = _rebuilt(client, original, side="left", node=_deep_node(TREE))

    status = _status(client, new)
    assert status["status"] == "ready"
    assert new != original
    assert set(new.split("__")).isdisjoint(original.split("__")), "no tree id may be reused"
    assert status["rerooted_from"] == original
    assert status["reroot"]["side"] == "left"
    assert status["reroot"]["before"]["rf"]["rf"] == 0
    assert status["metrics_ready"] == ["rf"]
    # Rooted RF sees the new root: the same tree, rooted elsewhere, disagrees.
    assert _rf(client, new) > 0


def test_the_unchanged_tree_is_an_independent_copy_with_the_same_node_ids(client):
    original = _built(client, TREE, TREE)
    new = _rebuilt(client, original, side="left", node=_deep_node(TREE))
    old_right, new_right = original.split("__")[1], new.split("__")[1]
    a = client.get(f"/api/v1/trees/{old_right}/slice", params={"budget": 100}, headers=ALICE).json()
    b = client.get(f"/api/v1/trees/{new_right}/slice", params={"budget": 100}, headers=ALICE).json()
    assert a["nodes"] == b["nodes"]


def test_by_default_the_original_is_kept_and_marked(client):
    original = _built(client, TREE, TREE)
    new = _rebuilt(client, original, side="left", node=_deep_node(TREE))
    assert _status(client, original)["superseded_by"] == new
    listed = {p["id"]: p for p in client.get("/api/v1/datasets", headers=ALICE).json()["pairs"]}
    assert listed[original]["superseded_by"] == new
    assert listed[new]["rerooted_from"] == original
    # Still fully readable.
    assert _rf(client, original) == 0


def test_replace_deletes_the_original_and_its_owner_is_told_where_it_went(client):
    original = _built(client, TREE, TREE)
    new = _rebuilt(client, original, side="left", node=_deep_node(TREE), replace=True)

    gone = client.get(f"/api/v1/comparisons/{original}/status", headers=ALICE)
    assert gone.status_code == 410
    assert gone.json()["code"] == "comparison_rerooted"
    assert gone.json()["moved_to"] == new
    summary = client.get(f"/api/v1/comparisons/{original}", headers=ALICE)
    assert (summary.status_code, summary.json().get("moved_to")) == (410, new)
    # Anyone else: the same 404 as for an id that never existed (§22).
    assert client.get(f"/api/v1/comparisons/{original}/status", headers=BOB).status_code == 404
    # Its stores went too: replaced means deleted.
    for tree in original.split("__"):
        assert not (config.TREES_DIR / tree).exists()

    # Deleting the replacement removes the record: then it is an ordinary 404.
    assert client.delete(f"/api/v1/comparisons/{new}", headers=ALICE).status_code == 200
    assert client.get(f"/api/v1/comparisons/{original}/status", headers=ALICE).status_code == 404


def test_replacing_a_replacement_leads_old_links_to_the_latest(client):
    first = _built(client, TREE, TREE)
    second = _rebuilt(client, first, side="left", node=_deep_node(TREE), replace=True)
    third = _rebuilt(client, second, side="right", node=_deep_node(TREE), replace=True)
    for old in (first, second):
        gone = client.get(f"/api/v1/comparisons/{old}/status", headers=ALICE)
        assert (gone.status_code, gone.json()["moved_to"]) == (410, third)


def test_another_owner_cannot_reroot_or_learn_it_exists(client):
    original = _built(client, TREE, TREE)
    response = _reroot(client, original, headers=BOB, side="left", node=_deep_node(TREE))
    assert response.status_code == 404
    assert response.json()["code"] == "comparison_not_found"


@pytest.mark.parametrize(
    ("node", "says"),
    [(0, "is the root"), (1, "same rooted topology"), (10_000, "not in this tree")],
)
def test_what_cannot_be_done_is_refused_by_name(client, node, says):
    original = _built(client, TREE, TREE)
    response = _reroot(client, original, side="left", node=node)
    assert response.status_code == 400
    assert response.json()["code"] == "reroot_refused"
    assert says in response.json()["detail"]
    assert db.comparisons_for("alice")[0].id == original  # nothing was queued


def test_a_bad_side_or_a_missing_node_is_refused_by_name(client):
    original = _built(client, TREE, TREE)
    assert "side must be" in _reroot(client, original, side="middle", node=5).json()["detail"]
    missing = _reroot(client, original, side="left")
    assert missing.status_code == 422  # `node` is required by the request schema


def test_typing_data_gives_the_same_counts_after_a_reroot(client):
    original = _built(client, TREE, TREE, table=TABLE)
    new = _rebuilt(client, original, side="left", node=_deep_node(TREE))
    leaves = [str(i) for i in range(1, 25)]
    for old_tree, new_tree in zip(original.split("__"), new.split("__"), strict=True):
        for segment in ("country", "source"):
            for filters in ({}, {"source": ["Human"]}):
                ask = {"leaves": leaves, "segment_by": segment, "filter": filters}
                a = client.post(f"/api/v1/isolates/{old_tree}/compositions", json=ask, headers=ALICE)
                b = client.post(f"/api/v1/isolates/{new_tree}/compositions", json=ask, headers=ALICE)
                assert a.status_code == b.status_code == 200, (a.text, b.text)
                assert a.json()["leaves"] == b.json()["leaves"]
        assert client.get(f"/api/v1/isolates/{new_tree}/keys", headers=ALICE).json()["species"] == new_tree
    # And the join report travelled with the data.
    assert _status(client, new)["isolates"] == _status(client, original)["isolates"]


def test_deleting_either_comparison_leaves_the_other_whole(client):
    original = _built(client, TREE, TREE, table=TABLE)
    new = _rebuilt(client, original, side="left", node=_deep_node(TREE))
    assert client.delete(f"/api/v1/comparisons/{original}", headers=ALICE).status_code == 200
    assert _status(client, new)["status"] == "ready"
    assert _rf(client, new) > 0
    ask = {"leaves": ["1", "2"], "segment_by": "country", "filter": {}}
    for tree in new.split("__"):
        assert client.post(f"/api/v1/isolates/{tree}/compositions", json=ask, headers=ALICE).status_code == 200


def test_a_failed_build_leaves_the_original_untouched(client, monkeypatch):
    original = _built(client, TREE, TREE)
    response = _reroot(client, original, side="left", node=_deep_node(TREE), replace=True)
    new = response.json()["id"]

    def broken(*_args, **_kwargs):
        raise RuntimeError("disk full")

    monkeypatch.setattr(jobs, "compute_pair", broken)
    assert jobs.process_next("test") is True
    failed = _status(client, new)
    assert failed["status"] == "failed" and "disk full" in failed["error"]
    kept = _status(client, original)
    assert kept["status"] == "ready" and kept["superseded_by"] is None
    assert _rf(client, original) == 0


def test_only_a_ready_comparison_can_be_rerooted(client):
    original = _built(client, TREE, TREE)
    pending = _reroot(client, original, side="left", node=_deep_node(TREE)).json()["id"]
    response = _reroot(client, pending, side="left", node=_deep_node(TREE))
    assert response.status_code == 400
    assert "only a ready comparison" in response.json()["detail"]


def test_rerooting_the_demo_pair_keeps_its_typing_data(tmp_path, monkeypatch, datasets_dir):
    """The catalogue's vibrio pair keeps its isolates under the species, not a tree id.

    The re-rooted trees are uploads, read by tree id, so the species store has
    to be copied to each — or re-rooting the demo would draw it without bars.
    """
    from phylodelta.api.identity import SINGLE_OWNER
    from phylodelta.isolates import registry as isolate_registry
    from phylodelta.isolates.ingest import ingest_all
    from phylodelta.metrics import registry_pairs
    from phylodelta.precompute.pipeline import compute_pairs, ingest_trees
    from phylodelta.trees import registry

    for name, value in (("STORE_DIR", tmp_path), ("TREES_DIR", tmp_path / "trees"),
                        ("PAIRS_DIR", tmp_path / "pairs"), ("ISOLATES_DIR", tmp_path / "isolates")):
        monkeypatch.setattr(config, name, value)
    monkeypatch.setenv("PHYLODELTA_STORE", str(tmp_path))
    monkeypatch.setenv("PHYLODELTA_AUTH", "header")
    db.reset()
    with db.using_store(tmp_path):
        db.create_schema()
        pair = "vibrio-nj__vibrio-upgma"
        assert ingest_trees(datasets_dir=datasets_dir, store_dir=tmp_path) == 0
        assert compute_pairs(store_dir=tmp_path, datasets_dir=datasets_dir, metrics=["rf"], only=pair) == 0
        assert ingest_all(datasets_dir=datasets_dir, store_dir=tmp_path) == 0
        registry.reset_cache()
        registry_pairs.reset_cache()
        isolate_registry.reset_cache()
        client = TestClient(create_app(), raise_server_exceptions=False)
        owner = {AUTH_HEADER: SINGLE_OWNER}

        left = registry.get_tree("vibrio-nj").to_arrays()
        response = client.post(f"/api/v1/comparisons/{pair}/reroot",
                               json={"side": "left", "node": _deep_node_of(left)}, headers=owner)
        assert response.status_code == 202, response.text
        new = response.json()["id"]
        assert jobs.process_next("test") is True
        status = client.get(f"/api/v1/comparisons/{new}/status", headers=owner).json()
        assert status["status"] == "ready", status

        leaves = ["1", "2", "3", "11", "69", "211"]
        ask = {"leaves": leaves, "segment_by": "Country", "filter": {}}
        before = client.post("/api/v1/isolates/vibrio/compositions", json=ask, headers=owner)
        for tree in new.split("__"):
            after = client.post(f"/api/v1/isolates/{tree}/compositions", json=ask, headers=owner)
            assert before.status_code == after.status_code == 200, (before.text, after.text)
            assert after.json()["leaves"] == before.json()["leaves"]


def _deep_node_of(t) -> int:
    candidates = [
        i for i in range(t.n_nodes)
        if t.parent[i] != NO_PARENT and t.parent[t.parent[i]] != NO_PARENT and not t.is_leaf(i)
    ]
    return max(candidates, key=lambda i: t.depth[i])

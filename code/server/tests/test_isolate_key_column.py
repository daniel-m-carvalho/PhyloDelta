"""Choosing the isolate table's key column, TSV and CSV (§47).

What these hold to: the chosen column is the index and is recorded; a column
the table does not have is refused at upload, by name, before any work; a
table that names no leaf leaves the comparison ready and says why the table
was not used; one table shared by both trees reaches both; and the demo
tables are still keyed by ST.
"""

from __future__ import annotations

import csv
import io
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from phylodelta import config, db
from phylodelta.api.app import create_app
from phylodelta.api.identity import AUTH_HEADER
from phylodelta.isolates import table as tables
from phylodelta.isolates.ingest import (
    NoLeafMatched,
    ingest_species,
    ingest_table,
    match_keys,
)
from phylodelta.isolates.store import read_isolates

DATASETS = Path(__file__).resolve().parents[3] / "datasets"

LEFT = b"(((A:0.1,B:0.1):0.1,C:0.2):0.1,D:0.3);"
RIGHT = b"(((A:0.1,C:0.1):0.1,B:0.2):0.1,E:0.3);"
# Keyed by `isolate`; `ST` is an ordinary column here, and Z names no leaf.
TSV = b"ST\tisolate\tcountry\n1\tA\tPT\n2\tB\tES\n2\tB\tFR\n3\tC\tPT\n9\tZ\tPT\n"
CSV = (
    b'\xef\xbb\xbfST,isolate,"country, as reported"\n'
    b'1,A,"Portugal, north"\n2,B,"Spain ""east"""\n3,C,PT\n'
)


def write(tmp_path: Path, name: str, data: bytes) -> Path:
    path = tmp_path / name
    path.write_bytes(data)
    return path


# --- reading the table ------------------------------------------------------


def test_a_tab_in_the_first_line_is_tsv_and_otherwise_csv(tmp_path):
    assert tables.read_header(write(tmp_path, "a", TSV)) == (
        ["ST", "isolate", "country"], "\t"
    )
    # The BOM is dropped and a quoted comma stays inside its column.
    assert tables.read_header(write(tmp_path, "b", CSV)) == (
        ["ST", "isolate", "country, as reported"], ","
    )


def test_quoted_csv_cells_and_escaped_quotes_are_read_whole(tmp_path):
    header, rows = tables.read_table(write(tmp_path, "t.csv", CSV))
    assert rows[0] == ["1", "A", "Portugal, north"]
    assert rows[1] == ["2", "B", 'Spain "east"']


@pytest.mark.parametrize(
    "first_line,refusal",
    [
        (b"ST\t\tcountry\n", r"column\(s\) 2 have no name"),
        (b"ST,country,ST\n", "'ST' more than once"),
        (b'ST,"country\n', "unclosed quote"),
        (b"just-one-column\n", "names one column"),
        (b"\n", "empty"),
    ],
)
def test_a_bad_header_is_refused_saying_what_is_wrong(tmp_path, first_line, refusal):
    with pytest.raises(tables.TableRejected, match=refusal):
        tables.read_header(write(tmp_path, "t", first_line + b"x,y\n"))


def test_a_missing_key_names_the_columns_that_exist():
    message = tables.missing_key("ST", ["isolate", "country"])
    assert "'ST'" in message and "'isolate', 'country'" in message


# --- the store ---------------------------------------------------------------


def test_the_chosen_column_is_the_index_and_is_recorded(tmp_path):
    meta = ingest_species("x", write(tmp_path, "t.tsv", TSV), tmp_path / "s", "isolate")
    reader = read_isolates(tmp_path / "s")
    assert reader.meta.key_column == meta.key_column == "isolate"
    assert reader.rows_for("B") == (1, 3), "two rows for B, contiguous"
    assert reader.rows_for("2") == (0, 0), "ST values are not the key here"
    # The key is not a facet; ST, now an ordinary column, is.
    names = {f.name for f in reader.meta.facets}
    assert "isolate" not in names and "ST" in names


def test_a_format_1_store_is_read_as_keyed_by_st(tmp_path):
    ingest_species("x", write(tmp_path, "t.tsv", TSV), tmp_path / "s")
    meta_path = tmp_path / "s" / "meta.json"
    raw = json.loads(meta_path.read_text())
    raw["format_version"] = 1
    del raw["key_column"]
    meta_path.write_text(json.dumps(raw))
    assert read_isolates(tmp_path / "s").meta.key_column == "ST"


def test_a_key_the_table_lacks_is_refused_by_name(tmp_path):
    with pytest.raises(tables.TableRejected, match="no column 'strain'"):
        ingest_species("x", write(tmp_path, "t.tsv", TSV), tmp_path / "s", "strain")


def test_the_join_is_counted_both_ways():
    keys = ["A", "B", "B", "", "Z", "Y", "Y"]
    report = match_keys("isolate", keys, ["A", "B", "C", "D"])
    assert report.rows == 7
    assert report.rows_unmatched == 3, "Z once and Y twice"
    assert report.rows_without_key == 1
    assert report.unmatched_examples == ["Y", "Z"]
    assert (report.leaves, report.leaves_without_rows) == (4, 2)


def test_a_table_that_names_no_leaf_is_refused_and_writes_nothing(tmp_path):
    with pytest.raises(NoLeafMatched, match="Was the right column chosen"):
        ingest_table(
            "x", write(tmp_path, "t.tsv", TSV), tmp_path / "s", "ST", leaves=["A", "B"]
        )
    assert not (tmp_path / "s").exists()


def test_the_real_table_as_csv_builds_the_same_store_as_as_tsv(tmp_path):
    """The CSV path measured on vibrio's 26,629 rows, not only on five."""
    source = DATASETS / "isolated_data" / "vibrio.tsv"
    if not source.exists():
        pytest.skip("vibrio.tsv not present")
    as_csv = tmp_path / "vibrio.csv"
    with open(source, newline="", encoding="utf-8", errors="replace") as fh, open(
        as_csv, "w", newline="", encoding="utf-8"
    ) as out:
        csv.writer(out).writerows(csv.reader(fh, delimiter="\t"))

    a = ingest_species("v", source, tmp_path / "tsv")
    b = ingest_species("v", as_csv, tmp_path / "csv")
    assert (a.n_rows, a.n_sequence_types, a.facets) == (b.n_rows, b.n_sequence_types, b.facets)
    for path in (tmp_path / "tsv").iterdir():
        if path.name != "meta.json":
            assert path.read_bytes() == (tmp_path / "csv" / path.name).read_bytes(), path.name


# --- the upload and the worker -----------------------------------------------


@pytest.fixture
def store(tmp_path, monkeypatch):
    monkeypatch.setenv("PHYLODELTA_STORE", str(tmp_path))
    monkeypatch.setattr(config, "STORE_DIR", tmp_path)
    monkeypatch.setattr(config, "TREES_DIR", tmp_path / "trees")
    monkeypatch.setattr(config, "PAIRS_DIR", tmp_path / "pairs")
    monkeypatch.setattr(config, "ISOLATES_DIR", tmp_path / "isolates")
    monkeypatch.setattr(config, "SCRATCH_DIR", tmp_path / "scratch")
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


HEADERS = {AUTH_HEADER: "alice"}


def post(client, data=None, **tables_sent):
    files = {
        "left_tree": ("l.nwk", io.BytesIO(LEFT)),
        "right_tree": ("r.nwk", io.BytesIO(RIGHT)),
        **{role: (name, io.BytesIO(body)) for role, (name, body) in tables_sent.items()},
    }
    return client.post("/api/v1/comparisons", files=files, data=data or {}, headers=HEADERS)


def run(client, response) -> dict:
    from phylodelta.precompute.jobs import process_next

    assert response.status_code == 202, response.text
    comparison_id = response.json()["id"]
    assert process_next("w1") is True
    return client.get(f"/api/v1/comparisons/{comparison_id}/status", headers=HEADERS).json()


def keys_of(client, dataset_id: str):
    return client.get(f"/api/v1/isolates/{dataset_id}/keys", headers=HEADERS)


def test_a_key_the_table_lacks_is_refused_at_upload_with_its_columns(client, store):
    response = post(
        client, {"left_isolates_key": "strain"}, left_isolates=("meta.tsv", TSV)
    )
    assert response.status_code == 400
    body = response.json()
    assert "'meta.tsv' has no column 'strain'" in body["detail"]
    assert "'ST', 'isolate', 'country'" in body["detail"]
    assert "left_isolates_key" in body["hint"]
    assert list((store / "uploads").glob("*")) == [], "nothing left behind"


@pytest.mark.parametrize(
    "data,sent,refusal",
    [
        ({"right_isolates_key": "ST"}, {"left_isolates": ("m.tsv", TSV)}, "no right_isolates file"),
        ({"isolates_shared": "true"}, {}, "no left_isolates table"),
        (
            {"isolates_shared": "true"},
            {"left_isolates": ("a.tsv", TSV), "right_isolates": ("b.tsv", TSV)},
            "sent once",
        ),
        ({"left_isolates_key": "  "}, {"left_isolates": ("m.tsv", TSV)}, "is empty"),
    ],
)
def test_fields_that_contradict_each_other_are_refused(client, data, sent, refusal):
    response = post(client, data, **sent)
    assert response.status_code == 400
    assert refusal in response.json()["detail"]


def test_csv_is_accepted_and_stored_as_what_it_is(client, store):
    response = post(client, {"left_isolates_key": "isolate"}, left_isolates=("m.csv", CSV))
    assert response.status_code == 202, response.text
    bundle = store / "uploads" / response.json()["id"]
    manifest = json.loads((bundle / "bundle.json").read_text())
    assert manifest["files"]["left_isolates"]["path"] == "left_isolates.csv"
    assert manifest["isolate_keys"] == {"left_isolates": "isolate"}
    assert manifest["shared_isolates"] is False


def test_a_table_sent_without_a_key_is_keyed_by_st(client, store):
    """The API contract before the key could be chosen still holds."""
    response = post(client, left_isolates=("m.tsv", b"ST\tcountry\nA\tPT\n"))
    assert response.status_code == 202, response.text
    manifest = json.loads(
        (store / "uploads" / response.json()["id"] / "bundle.json").read_text()
    )
    assert manifest["isolate_keys"] == {"left_isolates": "ST"}


def test_the_chosen_key_joins_and_the_status_reports_the_join(client):
    status = run(
        client,
        post(client, {"left_isolates_key": "isolate"}, left_isolates=("m.tsv", TSV)),
    )
    assert status["status"] == "ready"
    left = status["isolates"]["left"]
    assert left == {
        "key_column": "isolate", "rows": 5, "rows_unmatched": 1, "rows_without_key": 0,
        "unmatched_examples": ["Z"], "leaves": 4, "leaves_without_rows": 1, "error": None,
    }
    assert "right" not in status["isolates"], "left alone is not shared"
    left_id, right_id = status["id"].split("__")
    assert keys_of(client, left_id).json()["key_column"] == "isolate"
    assert keys_of(client, right_id).status_code == 404


def test_a_table_naming_no_leaf_leaves_the_comparison_ready(client):
    """The wrong column chosen: the trees are still compared, the table is not
    used, and the status says why rather than the bars being silently empty."""
    status = run(client, post(client, {"left_isolates_key": "ST"}, left_isolates=("m.tsv", TSV)))
    assert status["status"] == "ready" and status["error"] is None
    left = status["isolates"]["left"]
    assert left["key_column"] == "ST"
    assert "no value in column 'ST' names a leaf" in left["error"]
    assert keys_of(client, status["id"].split("__")[0]).status_code == 404


def test_a_shared_table_reaches_both_trees_with_a_report_each(client):
    status = run(
        client,
        post(
            client,
            {"left_isolates_key": "isolate", "isolates_shared": "true"},
            left_isolates=("m.csv", CSV),
        ),
    )
    left, right = status["isolates"]["left"], status["isolates"]["right"]
    # D is a leaf only on the left, E only on the right; neither has rows.
    assert left["leaves_without_rows"] == right["leaves_without_rows"] == 1
    left_id, right_id = status["id"].split("__")
    for dataset_id in (left_id, right_id):
        assert keys_of(client, dataset_id).json()["key_column"] == "isolate"


def test_two_tables_are_each_keyed_by_their_own_column(client):
    status = run(
        client,
        post(
            client,
            {"left_isolates_key": "isolate", "right_isolates_key": "leaf"},
            left_isolates=("l.tsv", TSV),
            right_isolates=("r.csv", b"leaf,host\nA,human\nE,water\n"),
        ),
    )
    assert status["isolates"]["left"]["key_column"] == "isolate"
    right = status["isolates"]["right"]
    assert (right["key_column"], right["rows"], right["leaves_without_rows"]) == ("leaf", 2, 2)


def test_deleting_a_comparison_removes_both_copies_of_a_shared_table(client, store):
    status = run(
        client,
        post(
            client,
            {"left_isolates_key": "isolate", "isolates_shared": "true"},
            left_isolates=("m.tsv", TSV),
        ),
    )
    left_id, right_id = status["id"].split("__")
    assert (store / "isolates" / right_id).is_dir()
    assert client.delete(f"/api/v1/comparisons/{status['id']}", headers=HEADERS).status_code == 200
    assert not (store / "isolates" / left_id).exists()
    assert not (store / "isolates" / right_id).exists()

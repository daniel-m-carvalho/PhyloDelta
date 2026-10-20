"""Declared outputs: what a metric promises, and whether it delivers.

A declaration nobody checks is documentation, and documentation drifts. These
tests cover both halves — parsing the declaration, and enforcing it against what
a metric actually returned.
"""

from __future__ import annotations


import numpy as np
import pytest

from phylodelta.metrics.contract import (
    MetricManifest,
    MetricResult,
    MetricSide,
    validate_result,
)

BASE = {
    "name": "demo",
    "title": "Demo",
    "kind": "python",
    "entrypoint": "does.not:matter",
}


def manifest(outputs: dict | None = None) -> MetricManifest:
    return MetricManifest.from_json({**BASE, "outputs": outputs or {}})


# --- parsing ---------------------------------------------------------------

def test_a_manifest_without_outputs_declares_nothing():
    m = manifest()
    assert m.outputs.columns == [] and m.outputs.scalars == []


def test_columns_and_scalars_are_parsed():
    m = manifest({
        "summary": [{"key": "rf", "label": "Robinson-Foulds"}],
        "columns": [{"name": "exact", "dtype": "uint8", "semantics": "boolean",
                     "render": "overlay", "label": "Preserved"}],
    })
    assert m.outputs.column_names == ["exact"]
    assert m.outputs.columns[0].semantics == "boolean"
    assert m.outputs.columns[0].render == "overlay"
    assert m.outputs.scalars[0].label == "Robinson-Foulds"


def test_label_defaults_to_the_name():
    m = manifest({"columns": [{"name": "agreement", "dtype": "float32"}]})
    assert m.outputs.columns[0].label == "agreement"


def test_unknown_semantics_is_refused():
    with pytest.raises(ValueError, match="semantics"):
        manifest({"columns": [{"name": "x", "dtype": "uint8", "semantics": "vibes"}]})


def test_unknown_render_hint_is_refused():
    with pytest.raises(ValueError, match="render"):
        manifest({"columns": [{"name": "x", "dtype": "uint8", "render": "interpretive dance"}]})


def test_a_column_needs_a_name_and_a_dtype():
    with pytest.raises(ValueError, match="dtype"):
        manifest({"columns": [{"name": "x"}]})


# --- enforcement -----------------------------------------------------------

def sides(**columns) -> dict:
    return {"left": MetricSide(columns=dict(columns)),
            "right": MetricSide(columns=dict(columns))}


def test_a_metric_producing_what_it_declared_passes():
    m = manifest({"columns": [{"name": "exact", "dtype": "uint8"}]})
    result = MetricResult(name="demo", **sides(exact=np.zeros(4, dtype=np.uint8)))
    validate_result(result, m)


def test_a_bool_column_satisfies_a_uint8_declaration():
    """numpy bool_ is one byte; naming it uint8 on disk is readable anywhere."""
    m = manifest({"columns": [{"name": "exact", "dtype": "uint8"}]})
    result = MetricResult(name="demo", **sides(exact=np.zeros(4, dtype=bool)))
    validate_result(result, m)


def test_a_missing_column_is_caught():
    m = manifest({"columns": [{"name": "exact", "dtype": "uint8"}]})
    with pytest.raises(ValueError, match="missing \\['exact'\\]"):
        validate_result(MetricResult(name="demo", **sides()), m)


def test_an_undeclared_column_is_caught():
    """A renamed column would otherwise surface as an empty overlay, or not at all."""
    m = manifest({"columns": [{"name": "exact", "dtype": "uint8"}]})
    result = MetricResult(name="demo", **sides(exakt=np.zeros(4, dtype=np.uint8)))
    with pytest.raises(ValueError, match="undeclared \\['exakt'\\]"):
        validate_result(result, m)


def test_a_wrong_dtype_is_caught():
    m = manifest({"columns": [{"name": "score", "dtype": "float32"}]})
    result = MetricResult(name="demo", **sides(score=np.zeros(4, dtype=np.uint8)))
    with pytest.raises(ValueError, match="declares float32"):
        validate_result(result, m)


def test_declaring_nothing_and_producing_nothing_is_valid():
    """The geodesic case: one number, nothing per node."""
    validate_result(MetricResult(name="geodesic", summary={"geodesic": 1.5}), manifest())


def test_declaring_nothing_but_producing_something_is_caught():
    result = MetricResult(name="demo", **sides(surprise=np.zeros(4, dtype=np.uint8)))
    with pytest.raises(ValueError, match="undeclared"):
        validate_result(result, manifest())


# --- the shipped manifest --------------------------------------------------

def test_rf_declares_what_it_produces(real_store):
    from phylodelta.metrics import registry
    from phylodelta.metrics.plugins.rf_python.rf import compute
    from phylodelta.trees.correspondence import compute_correspondence
    from phylodelta.trees.newick import parse_newick

    a = parse_newick("(((A,B),C),(D,E));")
    b = parse_newick("((D,E),(B,(A,C)));")
    result = compute(a, b, compute_correspondence(a, b))
    validate_result(result, registry.discover()["rf"])


def test_every_shipped_manifest_parses():
    from phylodelta.metrics import registry

    for name, m in registry.discover().items():
        assert m.name == name
        assert m.directory is not None
        for column in m.outputs.columns:
            assert column.dtype


def test_treediff_rf_refuses_a_weighted_distance():
    """The shipped pattern must not accept a *weighted* RF as an RF.

    `rf_postorder` prints "Weighted Robinson Foulds distance is: …" instead of
    "Robinson Foulds distance is: …" as soon as its input carries branch
    lengths — observed from 17,645 leaves up, where the generated ladder starts
    including them. An unanchored pattern matches that line too, so the server
    would have recorded 1.23e+06 as this pair's RF, alongside a built-in `rf`
    of 6,825, with nothing saying which was wrong. The server writes this
    metric's input without lengths, so it does not happen today; the anchor is
    what stops it being a silent wrong answer if that ever changes.
    """
    import re

    from phylodelta.metrics import registry

    pattern = registry.discover()["rf-treediff"].raw["parse"]["scalars"][0]["pattern"]

    assert re.search(pattern, "Robinson Foulds distance is: 6825").group(1) == "6825"
    assert re.search(pattern, "Weighted Robinson Foulds distance is: 1.23025e+06") is None


# --- the implementation reference (§42) -------------------------------------

def test_the_reference_is_parsed_with_its_link():
    manifest = MetricManifest.from_json({
        **BASE, "reference": {"citation": "A program. 2021.", "doi": "10.1000/xyz123"},
    })
    ref = manifest.reference
    assert (ref.citation, ref.doi, ref.url) == ("A program. 2021.", "10.1000/xyz123", "https://doi.org/10.1000/xyz123")


def test_a_reference_without_a_doi_has_no_link():
    ref = MetricManifest.from_json({**BASE, "reference": {"citation": "A program."}}).reference
    assert (ref.doi, ref.url) == ("", "")


def test_software_no_paper_describes_is_cited_by_its_link():
    ref = MetricManifest.from_json({
        **BASE, "reference": {"citation": "A tool.", "url": "https://github.com/x/tool"},
    }).reference
    assert (ref.doi, ref.url) == ("", "https://github.com/x/tool")


def test_a_metric_without_a_reference_has_none():
    assert MetricManifest.from_json(BASE).reference is None


@pytest.mark.parametrize(
    "bad, says",
    [
        ({}, "needs a 'citation'"),
        ({"citation": "  "}, "needs a 'citation'"),
        ({"citation": "X", "doi": "https://doi.org/10.1/x"}, "is not a DOI"),
        ({"citation": "X", "url": "http://insecure.example"}, "must be an https:// link"),
        ({"citation": "X", "doi": "10.1000/x", "url": "https://a.b"}, "not both"),
    ],
)
def test_a_malformed_reference_is_refused_by_name(bad, says):
    # It would reach the interface as a citation that says nothing, or a link
    # that goes nowhere.
    with pytest.raises(ValueError, match=says) as refused:
        MetricManifest.from_json({**BASE, "reference": bad})
    assert "'demo'" in str(refused.value)


def test_the_earlier_list_of_references_is_refused_not_ignored():
    # Ignoring it would drop the citation without a word.
    with pytest.raises(ValueError, match="no longer read"):
        MetricManifest.from_json({**BASE, "references": [{"citation": "X"}]})


def test_every_shipped_metric_says_where_its_implementation_comes_from():
    from phylodelta.metrics import registry

    for name, manifest in registry.discover().items():
        assert manifest.reference is not None, f"{name} has no reference"
        assert manifest.reference.url, f"{name}'s reference has neither a DOI nor a link"


def test_the_built_in_rf_says_it_is_this_projects_own_code():
    # It follows Branco, Vaz & Francisco's method (§1.10) but is not their
    # code — that is TreeDiff, the `rf-treediff` metric. Crediting the paper
    # alone read as if their implementation computed it.
    from phylodelta.metrics import registry

    metrics = registry.discover()
    assert metrics["rf"].reference.citation.startswith("PhyloDelta's own implementation")
    assert metrics["rf"].reference.doi == "10.3390/a17010015"
    assert not metrics["rf-treediff"].reference.citation.startswith("PhyloDelta")


def test_the_triplet_distance_is_not_credited_to_the_rf_paper():
    # The bug this guards: triplet cited Branco, Vaz & Francisco (2024), a
    # paper about Robinson-Foulds only. Its program, TreeDiff's trip_sht, has
    # no publication, so it is cited as software.
    from phylodelta.metrics import registry

    ref = registry.discover()["triplet"].reference
    assert ref.doi != "10.3390/a17010015"
    assert ref.url == "https://github.com/pedroparedesbranco/TreeDiff"

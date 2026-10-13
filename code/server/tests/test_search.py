"""Finding nodes by label (§37), without the API in the way."""

from __future__ import annotations

from phylodelta.trees.newick import parse_newick
from phylodelta.trees.search import LabelIndex


def _index(newick: str) -> tuple[LabelIndex, list[str]]:
    labels = parse_newick(newick).labels
    return LabelIndex(labels), labels


def _labels(index_and_labels, query, limit=50):
    index, labels = index_and_labels
    return [labels[m.node] for m in index.search(query, limit).matches]


def test_what_the_user_read_on_screen_comes_first():
    tree = _index("((12030:1,1203:1)_:1,(11203:1,51203:1)_:1)_;")
    assert _labels(tree, "1203") == ["1203", "12030"]


def test_contains_is_not_a_match():
    tree = _index("((11203:1,51203:1)_:1,(9:1,8:1)_:1)_;")
    assert _labels(tree, "1203") == []


def test_prefix_matches_run_shortest_first():
    tree = _index("(((1200:1,12:1)_:1,(120:1,121:1)_:1)_:1,(13:1,1:1)_:1)_;")
    assert _labels(tree, "12") == ["12", "120", "121", "1200"]


def test_a_named_internal_node_is_found():
    tree = _index("((9080:1,24265:1)8808:1,8979:1)_;")
    index, labels = tree
    (match,) = index.search("8808", 10).matches
    assert labels[match.node] == "8808" and match.exact


def test_an_unnamed_node_is_never_a_match():
    # `_` is how the NJ and UPGMA files spell "no name"; matching it would
    # return every internal node in the tree.
    tree = _index("((A:1,B:1)_:1,(C:1,D:1):1)_;")
    assert _labels(tree, "_") == []
    assert len(tree[0]) == 4


def test_case_is_ignored_and_the_stored_label_is_what_comes_back():
    tree = _index("((VC_1203:1,vc_1204:1)_:1,X:1)_;")
    assert _labels(tree, "vc_120") == ["VC_1203", "vc_1204"]


def test_a_blank_query_matches_nothing_rather_than_everything():
    tree = _index("((A:1,B:1)_:1,C:1)_;")
    assert tree[0].search("   ", 10).total == 0


def test_total_counts_every_match_while_the_list_is_capped():
    leaves = ",".join(f"{n}:1" for n in range(100, 200))
    index, labels = _index(f"(1:1,({leaves})_:1)_;")
    found = index.search("1", 5)
    assert found.total == 101
    assert found.exact == 1
    assert [labels[m.node] for m in found.matches] == ["1", "100", "101", "102", "103"]


def test_a_repeated_name_returns_every_node_carrying_it():
    # Leaves are unique in any tree that can be paired; internal labels are not
    # promised to be, and picking one of two would be a silent choice.
    index, labels = _index("((A:1,B:1)x:1,(C:1,D:1)x:1)_;")
    found = index.search("x", 10)
    assert found.exact == 2
    assert all(labels[m.node] == "x" and m.exact for m in found.matches)

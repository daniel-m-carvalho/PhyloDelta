"""Check the RF distance against two external implementations.

The built-in `rf` metric is already checked against TreeDiff (Table 18), but
TreeDiff is the reference implementation of the *same paper* this backend
follows, so the two share a definition. DendroPy and ETE3 share nothing with
either: different authors, different representation, and — as it turns out —
a different reporting convention.

Neither library is a dependency of the server, and neither should become one
for a check that runs once. Build a throwaway environment instead:

    uv venv /tmp/rfcheck --python 3.12
    uv pip install --python /tmp/rfcheck/bin/python dendropy ete3 numpy
    /tmp/rfcheck/bin/python harness/rf_external.py > results/rf_external.json

Two settings decide whether the comparison is like-for-like, and getting
either wrong produces a plausible near-miss rather than an error:

* **Rooted.** This store counts rooted clades. ETE3 unroots by default and
  DendroPy's unrooted mode differs by a handful of splits, so both are forced
  rooted; the unrooted figure is recorded alongside to show the size of that
  choice.
* **Reconciled.** The pipeline restricts both trees to their shared leaves and
  suppresses the unary nodes that leaves behind. Handing the 17,645 pair over
  unreconciled gives 13,654 rather than 13,650, because ST 211 is present in
  only one of the two trees (§2.6).
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import dendropy
from dendropy.calculate import treecompare
from ete3 import Tree

LADDER = Path(__file__).resolve().parent.parent / "trees" / "ladder"

#: TreeDiff's own binary, the metric the server registers as `rf-treediff`.
#: Included so the four implementations are read off ONE table: it is the
#: reference implementation of the paper this backend follows, and the question
#: "does the reference itself use the halved convention" is exactly the one a
#: reader has after seeing the factor of two.
TREEDIFF = (Path(__file__).resolve().parents[2] / "server" / "native"
            / "TreeDiff" / "rf_postorder")

#: Only the rungs that are pruned from the real pair, plus the real pair
#: itself. The synthetic rungs above it are nested relabelled copies, so an
#: external check there would be measuring the construction, not the data.
RUNGS = [1000, 2500, 5000, 10000, 17645]

#: From `uv run python harness/... ` against the built store — the values the
#: pipeline produces, recorded here so this runner needs no server.
PHYLODELTA = {1000: 531, 2500: 1219, 5000: 2207, 10000: 4113, 17645: 6825}


def files(leaves: int) -> tuple[Path, Path]:
    stem = f"ladder-{leaves:06d}"
    return LADDER / f"{stem}-a.nwk", LADDER / f"{stem}-b.nwk"


def reconciled(a: Path, b: Path, rooting: str):
    """Both trees restricted to their shared leaves, unary nodes suppressed.

    What the pipeline does before any metric runs. Done once and handed to
    every tool, so a disagreement is about the distance and not about which
    tool pruned what.
    """
    tns = dendropy.TaxonNamespace()
    kw = dict(schema="newick", taxon_namespace=tns, preserve_underscores=True,
              suppress_internal_node_taxa=True, rooting=rooting)
    t1 = dendropy.Tree.get(path=str(a), **kw)
    t2 = dendropy.Tree.get(path=str(b), **kw)
    l1 = {tx.label for tx in t1.poll_taxa()}
    l2 = {tx.label for tx in t2.poll_taxa()}
    shared = l1 & l2
    for t in (t1, t2):
        t.retain_taxa_with_labels(shared)
        t.suppress_unifurcations()
    for label in (l1 | l2) - shared:
        tns.remove_taxon_label(label)
    return t1, t2


def dendropy_sd(a: Path, b: Path, rooting: str) -> int:
    t1, t2 = reconciled(a, b, rooting)
    t1.encode_bipartitions()
    t2.encode_bipartitions()
    return int(treecompare.symmetric_difference(t1, t2))


def treediff_rf(a: Path, b: Path) -> int | None:
    """TreeDiff over the same pair, topology only.

    Given the files directly rather than through DendroPy's writer, which at
    these sizes takes longer than every distance in this table put together.
    The pruned rungs already carry no branch lengths and already share a leaf
    set, so they need no preparation; the 17,645 pair is the real one and is
    prepared by the server's own pipeline, which is what the deployed
    `rf-treediff` metric receives anyway.

    Lengths must be absent: given them, `rf_postorder` switches to printing
    "Weighted Robinson Foulds distance is:" and a reader of its output gets
    1.23e+06 where they expected 6,825. The server's manifest anchors its
    pattern to the start of a line for the same reason.
    """
    if not TREEDIFF.exists():
        return None
    out = subprocess.run([str(TREEDIFF), str(a), str(b)],
                         capture_output=True, text=True, timeout=1800).stdout
    found = re.search(r"(?m)^Robinson Foulds distance is:\s*([0-9.eE+-]+)", out)
    return int(float(found.group(1))) if found else None


#: The real pair, reconciled and written without lengths by the server's own
#: pipeline (`tools/prepare_rf_input.py`). Absent, the 17,645 row reports no
#: TreeDiff figure rather than a wrong one: handed the raw files it would
#: compare 17,645 leaves against 17,646.
PREPARED = Path(__file__).resolve().parent.parent / "trees" / "vibrio"


def treediff_input(leaves: int) -> tuple[Path, Path] | None:
    a, b = files(leaves)
    if leaves != 17645:
        return a, b
    ra, rb = PREPARED / "vibrio-a.nwk", PREPARED / "vibrio-b.nwk"
    return (ra, rb) if ra.exists() and rb.exists() else None


def ete3_rf(a: Path, b: Path) -> int:
    t1, t2 = Tree(str(a), format=1), Tree(str(b), format=1)
    l1, l2 = set(t1.get_leaf_names()), set(t2.get_leaf_names())
    shared = l1 & l2
    if l1 != shared:
        t1.prune(shared, preserve_branch_length=True)
    if l2 != shared:
        t2.prune(shared, preserve_branch_length=True)
    # Rooted, deliberately: this store counts rooted clades, and ETE3's default
    # unroots, which differs by a handful of splits — a plausible near-miss.
    return int(t1.robinson_foulds(t2, unrooted_trees=False)[0])


rows = []
for leaves in RUNGS:
    a, b = files(leaves)
    if not a.exists():
        print(f"missing {a}", file=sys.stderr)
        continue
    ours = PHYLODELTA[leaves]
    rows.append({
        "leaves": leaves,
        "phylodelta": ours,
        "phylodelta_doubled": ours * 2,
        "treediff": (treediff_rf(*prepared) if (prepared := treediff_input(leaves)) else None),
        "dendropy_rooted": dendropy_sd(a, b, "force-rooted"),
        "dendropy_unrooted": dendropy_sd(a, b, "force-unrooted"),
        "ete3_rooted": ete3_rf(a, b),
    })

json.dump({
    "dendropy": dendropy.__version__,
    "ete3": "3.1.3",
    "note": "rooted comparisons, both trees reconciled to their shared leaf set",
    "rows": rows,
}, sys.stdout, indent=1)

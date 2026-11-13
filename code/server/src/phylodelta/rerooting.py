"""Re-rooting a comparison's tree: a new comparison, built as an upload is (§56).

Every metric here is rooted — RF counts clades, triplet, MAST and SPR all read
the root — so a tree re-rooted is a different tree, and its comparison has to
be computed again. This module turns "re-root the left tree above node 812"
into exactly what an upload would have been had the user sent that tree:

* both stored trees are read back and written as Newick, one of them re-rooted
  (``normalise.reroot``). The unchanged one is re-ingested from its own Newick
  too, so the new comparison owns two independent stores — identical structure
  and node ids for the unchanged side — and shares nothing with the original;
* they go through ``uploads.accept`` into a bundle, and the bundle into the
  queue, so the worker builds it with the same ``ingest_tree_file`` and
  ``compute_pair`` as any upload, with the original's metrics;
* typing data cannot be re-joined — the original's raw tables were discarded
  when it was built (§26) — so the bundle names each side's isolate **store**
  to copy instead. A store is keyed by the leaf label (the ST), never by a
  node id, and a re-root changes no label, so the copy is exact.

New ids, always. A re-root renumbers almost every pre-order id, and an id is
what every cache, URL and shared link holds: the server keeps a reader and a
label index per tree id in each process (``trees.registry``), the slice cache
keys on it, and a link names node ids. Rebuilding under the old ids would serve
the old tree's values on the new tree's clades until every process restarted.

Nothing about the original changes unless the build succeeds: a failed re-root
is a failed new comparison, and the original is still there, as it was.
"""

from __future__ import annotations

import io
import json
import shutil
from pathlib import Path

from . import config, db, retention, uploads
from .metrics.store import read_pair
from .trees import registry as tree_registry
from .trees.newick import TreeArrays
from .trees.newick_writer import to_newick
from .trees.normalise import RerootRefused, reroot

SIDES = ("left", "right")


class RerootNotPossible(ValueError):
    """Asked of a comparison that cannot be re-rooted now, said by name."""


def _isolate_store(tree_id: str, meta) -> str | None:
    """Which isolate store a tree's typing data is in, or None.

    An upload's is under its own tree id (§24.5). A catalogue tree's — the
    demo's vibrio pair — is under its species, shared by every catalogue tree
    of that species, and the app finds it there only for a tree with a method
    (`isolateSetsFor`). The re-rooted tree is an upload, so either is copied to
    its id; missing the species case would re-root the demo without its bars.
    """
    base = Path(config.ISOLATES_DIR)
    if (base / tree_id / "meta.json").exists():
        return tree_id
    if meta.method and meta.species and (base / meta.species / "meta.json").exists():
        return meta.species
    return None


def _stored(tree_id: str) -> TreeArrays:
    return tree_registry.get_tree(tree_id).to_arrays()


def _before(comparison_id: str, metrics: list[str]) -> dict[str, dict]:
    """The original's summary per metric, kept on the new row for the header."""
    out = {}
    for metric in metrics:
        try:
            out[metric] = dict(read_pair(Path(config.PAIRS_DIR) / comparison_id / metric).meta.summary)
        except (FileNotFoundError, ValueError):
            continue
    return out


def request(
    owner_id: str,
    comparison_id: str,
    side: str,
    node: int | None,
    replace: bool = False,
):
    """Accept a re-root as a pending comparison. Returns the bundle.

    Raises ``LookupError`` for a comparison this owner does not have (the API
    turns it into the same 404 as any unknown id), ``RerootNotPossible`` or
    ``RerootRefused`` for a re-root that cannot be done, by name.
    """
    if side not in SIDES:
        raise RerootNotPossible(f"side must be one of {list(SIDES)}, not {side!r}")
    record = db.comparison_for(owner_id, comparison_id)
    if record is None:
        raise LookupError(comparison_id)
    if record.status != db.ComparisonStatus.READY:
        raise RerootNotPossible(
            f"comparison {comparison_id} is {record.status.value}; only a ready "
            "comparison can be re-rooted"
        )

    ids = {"left": record.left_id, "right": record.right_id}
    trees = {s: _stored(ids[s]) for s in SIDES}
    this = trees[side]

    if node is None:
        raise RerootNotPossible("a re-root needs the stored id of the node to re-root above")
    if not 0 <= node < this.n_nodes:
        raise RerootRefused(
            f"node {node} is not in this tree, which has nodes 0 to {this.n_nodes - 1}"
        )
    label = this.labels[node]
    rerooted = reroot(this, node)

    # Each side's isolate store, and the join report it came with. A side with
    # no store has nothing to copy, and its report says why it has none.
    reports = json.loads(record.isolate_report) if record.isolate_report else {}
    metrics = [m.strip() for m in (record.metrics or "rf").split(",") if m.strip()]

    def tree_meta(s: str):
        return tree_registry.get_tree(ids[s]).meta

    isolates = {s: found for s in SIDES if (found := _isolate_store(ids[s], tree_meta(s)))}

    sources = {}
    for s in SIDES:
        arrays = rerooted if s == side else trees[s]
        name = tree_meta(s).source or f"{s}.nwk"
        sources[f"{s}_tree"] = (name, io.BytesIO(to_newick(arrays).encode()))

    reroot_info = {
        "from": comparison_id,
        "side": side,
        "node": node,
        "label": label,
        "replace": bool(replace),
        "before": _before(comparison_id, metrics),
    }
    where = f"at {label}" if label and label != "_" else f"above node {node}"
    bundle = uploads.accept(
        sources,
        display_name=f"{record.display_name or comparison_id} (re-rooted {side} {where})",
        left_species=tree_meta("left").species,
        right_species=tree_meta("right").species,
        derived={
            "from": comparison_id,
            "isolates": isolates,
            "isolate_report": {s: reports[s] for s in SIDES if s in reports},
        },
    )
    try:
        db.record_upload(
            comparison_id=bundle.comparison_id,
            left_id=bundle.left_id,
            right_id=bundle.right_id,
            owner_id=owner_id,
            display_name=bundle.display_name,
            left_source=bundle.files["left_tree"].original_name,
            right_source=bundle.files["right_tree"].original_name,
            store_path=f"pairs/{bundle.comparison_id}",
            metrics=",".join(metrics),
            rerooted_from=comparison_id,
            reroot=json.dumps(reroot_info),
        )
    except Exception:
        uploads.discard(bundle.directory)
        raise
    return bundle, reroot_info


def copy_isolates(store: Path, derived: dict, new_ids: dict[str, str], owner_id: str) -> dict[str, dict]:
    """The job's half: each side's isolate store, copied to its new tree. Returns the join reports.

    A copy, never a shared directory: deleting either comparison must not take
    the other's typing data, and the deletion code removes ``isolates/<tree>``
    for every tree it removes. ``species`` in the copied header becomes the new
    tree's id, which is what an uploaded store records there.
    """
    reports: dict[str, dict] = {}
    previous = derived.get("isolate_report", {})
    for side, old_id in derived.get("isolates", {}).items():
        # A tree id, or a catalogue species (`_isolate_store`): the directory
        # and the `isolates-<name>` dataset row are named the same either way.
        source = store / "isolates" / old_id
        target = store / "isolates" / new_ids[side]
        if not (source / "meta.json").exists():
            reports[side] = {"error": "the original's isolate data was no longer there to copy"}
            continue
        shutil.rmtree(target, ignore_errors=True)
        shutil.copytree(source, target)
        meta_path = target / "meta.json"
        meta = json.loads(meta_path.read_text())
        meta["species"] = new_ids[side]
        meta_path.write_text(json.dumps(meta, indent=2))
        old_row = db.dataset_for(owner_id, f"isolates-{old_id}")
        db.register_dataset(
            dataset_id=f"isolates-{new_ids[side]}",
            owner_id=owner_id,
            kind=db.DatasetKind.ISOLATES,
            display_name=old_row.display_name if old_row else f"{side} isolates",
            store_path=f"isolates/{new_ids[side]}",
            source_name=meta.get("source", ""),
        )
        if side in previous:
            reports[side] = previous[side]
    for side, report in previous.items():
        reports.setdefault(side, report)
    return reports


def settle_original(comparison_id: str) -> str | None:
    """After a re-rooted comparison is ready: mark its original, or delete it.

    Kept (the default), the original is marked ``superseded_by``. Replaced,
    it goes through the same deletion as the delete endpoint, and a record is
    kept so its owner's old links lead to the new one rather than to a 404.
    Returns what was done, for the worker's log.
    """
    record = db.comparison_by_id(comparison_id)
    if record is None or not record.rerooted_from:
        return None
    info = json.loads(record.reroot or "{}")
    old = record.rerooted_from
    if info.get("replace"):
        # Links to what ``old`` itself replaced are repointed first: deleting
        # ``old`` forgets every record that leads to it.
        db.repoint_rerooted(record.owner_id, old, comparison_id)
        removed = retention.remove_comparison(record.owner_id, old)
        db.record_rerooted_away(record.owner_id, old, comparison_id)
        return f"replaced {old}" if removed else f"{old} was already gone"
    db.mark_superseded(old, comparison_id)
    return f"{old} kept, superseded by this one"


__all__ = [
    "RerootNotPossible",
    "RerootRefused",
    "SIDES",
    "copy_isolates",
    "request",
    "settle_original",
]

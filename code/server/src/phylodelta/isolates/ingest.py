"""Isolate table -> dictionary-encoded columns, sorted and indexed by its key.

The key is the column whose values name tree leaves: ``ST`` for the demo
tables, chosen at upload for anyone else's (§47). "ST" below means that column.

This is the largest input the backend handles -- 8.8 MB for vibrio and 12 MB for
clostridium, against 1.3 MB for both vibrio trees. Metadata, not topology, is
the dominant payload, which is why it is served filtered and per visible leaf
rather than shipped.
"""

from __future__ import annotations

import sys
from collections.abc import Collection
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

from .schema import DEFAULT_KEY_COLUMN, is_facet, is_segmentable, slug
from .store import MISSING, FacetMeta, IsolateMeta, code_dtype, write_isolates
from .table import TableRejected, missing_key, read_table

#: How many unmatched keys a report names. Enough to recognise the pattern --
#: "every one ends in _1", "these are sample ids" -- without carrying a
#: 30,000-entry list in a status response.
UNMATCHED_EXAMPLES = 10


class NoLeafMatched(TableRejected):
    """Not one key in the table names a leaf of its tree: almost certainly the
    wrong column. Refused rather than stored, since every bar would be empty
    and look like a tree with no isolate data instead of a mistake."""


@dataclass(frozen=True, slots=True)
class JoinReport:
    """How an uploaded table met its tree (§47), for ``/status``.

    Exact matching after trimming, nothing cleverer: a near miss shows up here
    as unmatched, with examples, rather than being joined on a guess.
    """

    key_column: str
    rows: int = 0
    #: Rows with a key that names no leaf. Kept in the store -- harmless, and
    #: a later tree might have the leaf -- but reported.
    rows_unmatched: int = 0
    #: Rows whose key cell is blank: they cannot name a leaf at all.
    rows_without_key: int = 0
    unmatched_examples: list[str] = field(default_factory=list)
    leaves: int = 0
    #: Leaves no row names. Normal in moderation (3.9% of vibrio's leaves).
    leaves_without_rows: int = 0
    #: Set when the table was not used, with why. The comparison is still ready.
    error: str | None = None

    def as_json(self) -> dict:
        return {
            "key_column": self.key_column, "rows": self.rows,
            "rows_unmatched": self.rows_unmatched,
            "rows_without_key": self.rows_without_key,
            "unmatched_examples": self.unmatched_examples,
            "leaves": self.leaves, "leaves_without_rows": self.leaves_without_rows,
            "error": self.error,
        }


def match_keys(key_column: str, keys: list[str], leaves: Collection[str]) -> JoinReport:
    """Count what matched, or refuse a table in which nothing did."""
    leaf_set = set(leaves)
    present = {key for key in keys if key}
    unmatched = present - leaf_set
    if present and not present & leaf_set:
        raise NoLeafMatched(
            f"no value in column {key_column!r} names a leaf of the tree "
            f"(the column has {_examples(present, 3)}; the leaves are like "
            f"{_examples(leaf_set, 3)}). Was the right column chosen?"
        )
    if not present:
        raise NoLeafMatched(f"column {key_column!r} is blank in every row")
    return JoinReport(
        key_column=key_column,
        rows=len(keys),
        rows_unmatched=sum(1 for key in keys if key and key in unmatched),
        rows_without_key=sum(1 for key in keys if not key),
        unmatched_examples=sorted(unmatched)[:UNMATCHED_EXAMPLES],
        leaves=len(leaf_set),
        leaves_without_rows=len(leaf_set - present),
    )


def _examples(values: set[str], n: int) -> str:
    shown = sorted(values)[:n]
    return ", ".join(repr(v) for v in shown) + (", ..." if len(values) > n else "")


def ingest_species(
    species: str, path: Path, directory: Path, key_column: str = DEFAULT_KEY_COLUMN
) -> IsolateMeta:
    """Build the store for a catalogue table. No tree to match against here."""
    meta, _ = ingest_table(species, path, directory, key_column)
    return meta


def ingest_table(
    species: str,
    path: Path,
    directory: Path,
    key_column: str = DEFAULT_KEY_COLUMN,
    leaves: Collection[str] | None = None,
    source_name: str = "",
) -> tuple[IsolateMeta, JoinReport | None]:
    """Build the store, and with ``leaves`` say how the table met that tree.

    The match is counted *before* anything is written, so a table refused for
    matching nothing leaves no store behind for the listing to offer.
    """
    header, rows = read_table(path)
    if key_column not in header:
        raise TableRejected(f"{path.name} {missing_key(key_column, header)}")
    join_at = header.index(key_column)

    def cell(row: list[str], i: int) -> str:
        return row[i].strip() if i < len(row) else ""

    report = (
        match_keys(key_column, [cell(row, join_at) for row in rows], leaves)
        if leaves is not None
        else None
    )

    # Sort by ST so that one sequence type is a contiguous run of rows. Sorted
    # by string, because sequence types are not all integers: the exports carry
    # NaN, -2, -3, -14 and similar where none was assigned.
    order = sorted(range(len(rows)), key=lambda r: cell(rows[r], join_at))
    rows = [rows[r] for r in order]

    facets: list[FacetMeta] = []
    columns: dict[str, np.ndarray] = {}
    for i, name in enumerate(header):
        distinct = {cell(row, i) for row in rows} - {""}
        if not is_facet(name, len(distinct), key_column):
            continue
        values = sorted(distinct)
        code_of = {value: k + 1 for k, value in enumerate(values)}
        dtype = code_dtype(len(values))
        codes = np.fromiter(
            (code_of.get(cell(row, i), MISSING) for row in rows),
            dtype=dtype, count=len(rows),
        )
        facets.append(
            FacetMeta(
                name=name, slug=slug(name), dtype=dtype.name,
                n_distinct=len(values),
                n_missing=int((codes == MISSING).sum()),
                segmentable=is_segmentable(len(values)),
                values=values,
            )
        )
        columns[name] = codes

    # ST -> row range. Rows are already grouped by the sort above.
    st_labels: list[str] = []
    offsets: list[int] = [0]
    previous = None
    for index, row in enumerate(rows):
        current = cell(row, join_at)
        if current != previous:
            if previous is not None:
                offsets.append(index)
            st_labels.append(current)
            previous = current
    offsets.append(len(rows))

    meta = IsolateMeta(
        species=species, source=source_name or path.name, n_rows=len(rows),
        n_sequence_types=len(st_labels), facets=facets,
        created=datetime.now(UTC).isoformat(timespec="seconds"),
        key_column=key_column,
    )
    written = write_isolates(
        directory, meta, columns, st_labels, np.asarray(offsets, dtype=np.uint32)
    )
    return written, report


def ingest_all(datasets_dir: Path | None = None, store_dir: Path | None = None) -> int:
    from .. import catalogue, config, db

    sources = catalogue.discover_isolate_sources(datasets_dir)
    if not sources:
        print("no isolate TSVs found", file=sys.stderr)
        return 1

    root = Path(store_dir or config.STORE_DIR) / "isolates"
    with db.using_store(root.parent):
        db.create_schema()
        return _ingest_each(sources, root)


def _ingest_each(sources, root) -> int:
    from .. import db
    from ..api.identity import SINGLE_OWNER

    for species, path in sources.items():
        meta = ingest_species(species, path, root / species)
        db.register_dataset(
            dataset_id=f"isolates-{species}",
            owner_id=SINGLE_OWNER,
            kind=db.DatasetKind.ISOLATES,
            display_name=f"{species} isolates",
            store_path=f"isolates/{species}",
            source_name=meta.source,
        )
        total = sum(p.stat().st_size for p in (root / species).iterdir() if p.is_file())
        source_size = path.stat().st_size
        print(
            f"{species:<14} {meta.n_rows:>7,} isolates  {meta.n_sequence_types:>7,} STs  "
            f"{len(meta.facets):>3} facets  "
            f"{source_size / 1024 / 1024:>5.1f} MB -> {total / 1024 / 1024:>4.1f} MB  "
            f"({source_size / total:.1f}x smaller)"
        )
    return 0

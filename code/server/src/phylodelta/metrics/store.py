"""On-disk stores for a computed comparison.

Two directories per pair, because the two things have different lifetimes and
different owners:

    store/pairs/{pair}/correspondence/   similarity, corresponds  — shared
    store/pairs/{pair}/{metric}/         whatever that metric declared

**Correspondence is written once per pair**, not once per metric. It is the
expensive half (the best-match search is 12.6 s of the 13 s a pair takes) and it
is identical whichever distance is being computed, so computing it per metric
would multiply the cost of adding one. It also means ``order=difference``
navigation, which ranks by ``similarity``, is metric-independent.

**A metric's directory holds only what that metric produced.** Zero columns is
valid; a geodesic distance contributes a number and nothing per node, and is
still fully usable because the client colours from correspondence.

Cost, measured on the vibrio pair: correspondence is 8 B/node/side
(4 similarity + 4 corresponds) and RF adds 1 B/node/side (``exact``).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

from ..trees.correspondence import Correspondence, CorrespondenceSide
from ..trees.newick import TreeArrays
from .columns import ColumnReader, read_header, write_side
from .contract import MetricResult, MetricSide

#: Bumped when either on-disk layout changes in a way a reader must notice.
FORMAT_VERSION = 2

CORRESPONDENCE_DIR = "correspondence"
_META = "meta.json"


def _stamp() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _write_header(directory: Path, payload: dict) -> None:
    (Path(directory) / _META).write_text(
        json.dumps(payload, indent=2, default=str) + "\n"
    )


def _check_version(raw: dict, directory: Path) -> None:
    if raw.get("format_version") != FORMAT_VERSION:
        raise ValueError(
            f"{directory} is format {raw.get('format_version')}, this build reads "
            f"{FORMAT_VERSION}; recompute the pair"
        )


# --- correspondence --------------------------------------------------------


@dataclass(frozen=True, slots=True)
class CorrespondenceMeta:
    pair_id: str
    left: str
    right: str
    n_left: int
    n_right: int
    notes: dict = field(default_factory=dict)
    created: str = ""


class CorrespondenceReader:
    """Memory-mapped read access to one pair's correspondence."""

    def __init__(self, directory: Path) -> None:
        self.directory = Path(directory)
        raw = read_header(self.directory)
        _check_version(raw, self.directory)
        self.meta = CorrespondenceMeta(
            pair_id=raw["pair_id"], left=raw["left"], right=raw["right"],
            n_left=raw["n_left"], n_right=raw["n_right"],
            notes=raw.get("notes", {}), created=raw.get("created", ""),
        )
        self.reader = ColumnReader(
            directory=self.directory,
            schema=raw["schema"],
            sizes={"left": raw["n_left"], "right": raw["n_right"]},
        )

    def column(self, side: str, column: str) -> np.ndarray:
        return self.reader.column(side, column)

    def slice(self, side: str, start: int, end: int) -> dict[str, np.ndarray]:
        return self.reader.slice(side, start, end)


def write_correspondence(
    directory: Path,
    correspondence: Correspondence,
    pair_id: str,
    left_id: str,
    right_id: str,
    left: TreeArrays,
    right: TreeArrays,
    notes: dict | None = None,
) -> CorrespondenceMeta:
    directory = Path(directory)
    schema = {
        "left": write_side(
            directory, "left",
            {"similarity": correspondence.left.similarity,
             "corresponds": correspondence.left.corresponds},
            left.n_nodes,
        ),
        "right": write_side(
            directory, "right",
            {"similarity": correspondence.right.similarity,
             "corresponds": correspondence.right.corresponds},
            right.n_nodes,
        ),
    }
    meta = CorrespondenceMeta(
        pair_id=pair_id, left=left_id, right=right_id,
        n_left=left.n_nodes, n_right=right.n_nodes,
        notes=dict(notes or {}), created=_stamp(),
    )
    _write_header(directory, {
        "pair_id": meta.pair_id, "left": meta.left, "right": meta.right,
        "n_left": meta.n_left, "n_right": meta.n_right,
        "schema": schema, "notes": meta.notes,
        "format_version": FORMAT_VERSION, "created": meta.created,
    })
    return meta


def read_correspondence(directory: Path) -> CorrespondenceReader:
    return CorrespondenceReader(directory)


# --- a metric's own columns ------------------------------------------------


@dataclass(frozen=True, slots=True)
class PairMeta:
    pair_id: str
    metric: str
    left: str
    right: str
    n_left: int
    n_right: int
    summary: dict = field(default_factory=dict)
    notes: dict = field(default_factory=dict)
    created: str = ""
    #: The version the metric's manifest declared when this was computed.
    #: Empty for pairs written before the field existed, which are exactly the
    #: ones that may hold a superseded definition — see `_check_metric_version`.
    metric_version: str = ""


#: Declared metric versions, resolved once per process.
#:
#: `registry.discover()` globs the plugins directory and re-parses every
#: manifest, which is 0.158 ms — fine where it is called once per build, and not
#: fine here: this check runs on every `read_pair`, so every comparison slice
#: request was paying it, about 10% of a 1.6 ms slice (§34.12) to be told the
#: same thing every time. A plug-in's declared version cannot change under a
#: running process without the files changing, and that is a restart.
#:
#: Deliberately NOT a cache inside `discover()`. Builds, uploads and the
#: manifest tests all want a fresh read, and making the shared function stateful
#: to speed up one caller would be the wrong trade.
_declared: dict[str, str] | None = None


def _declared_versions() -> dict[str, str]:
    global _declared
    if _declared is None:
        from . import registry

        _declared = {
            name: str(m.raw.get("version", "")) for name, m in registry.discover().items()
        }
    return _declared


class MetricVersionMismatch(ValueError):
    """A stored result computed by a different version of its metric.

    Its own type so the API can refuse it by name. As a bare `ValueError` it
    reached the browser as a 500 with nothing in it: a deployment updated
    without rebuilding showed every comparison as "Internal Server Error",
    while the message saying exactly what to run sat in the server log.
    """


def _check_metric_version(raw: dict, directory: Path) -> None:
    """Refuse a stored result computed by a different version of its metric.

    `format_version` guards the *file layout*; this guards the *meaning of the
    numbers*. They are separate failures: rf v1 and v2 write byte-identical
    files and differ only in what the scalar means, so a layout check cannot
    see it and a reader that trusted the bytes would serve a v1 distance under
    a v2 label. That happened once in the other direction — the `rf` scalar was
    half the symmetric difference while every document called it RF (§34.19) —
    and the whole cost of that was that nothing refused.

    Unknown metrics are not refused: a pair may legitimately hold a metric this
    build does not carry (a plug-in removed, a subprocess tool absent), and
    `discover()` is the authority on what exists, not this function.
    """
    stored = raw.get("metric_version", "")
    name = raw.get("metric", "?")
    declared = _declared_versions()
    if name not in declared:
        return
    current = declared[name]
    if stored != current:
        raise MetricVersionMismatch(
            f"{directory} holds `{name}` computed by version "
            f"{stored or '(unrecorded)'}, and this build declares version "
            f"{current}. The stored numbers mean something else; recompute it "
            f"(`phylodelta compute-pairs --only {raw.get('pair_id', '<pair id>')}`, "
            f"or upload the pair again)."
        )


class PairReader:
    """Memory-mapped read access to one metric's contribution for a pair."""

    def __init__(self, directory: Path) -> None:
        self.directory = Path(directory)
        raw = read_header(self.directory)
        _check_version(raw, self.directory)
        _check_metric_version(raw, self.directory)
        self.meta = PairMeta(
            pair_id=raw["pair_id"], metric=raw["metric"],
            left=raw["left"], right=raw["right"],
            n_left=raw["n_left"], n_right=raw["n_right"],
            summary=raw.get("summary", {}), notes=raw.get("notes", {}),
            created=raw.get("created", ""),
            metric_version=str(raw.get("metric_version", "")),
        )
        self.reader = ColumnReader(
            directory=self.directory,
            schema=raw.get("schema", {}),
            sizes={"left": raw["n_left"], "right": raw["n_right"]},
        )

    def columns(self, side: str) -> list[str]:
        return self.reader.columns(side)

    def column(self, side: str, column: str) -> np.ndarray:
        return self.reader.column(side, column)

    def slice(self, side: str, start: int, end: int) -> dict[str, np.ndarray]:
        return self.reader.slice(side, start, end)


def write_pair(
    directory: Path,
    result: MetricResult,
    pair_id: str,
    left_id: str,
    right_id: str,
    left: TreeArrays,
    right: TreeArrays,
) -> PairMeta:
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)

    schema: dict[str, dict[str, str]] = {}
    for side, values, arrays in (
        ("left", result.left, left),
        ("right", result.right, right),
    ):
        # None and MetricSide({}) both mean "nothing per node". That is a
        # supported result, not a failure: see contract.py.
        columns = values.columns if values is not None else {}
        schema[side] = write_side(directory, side, columns, arrays.n_nodes)

    from . import registry

    manifest = registry.discover().get(result.name)
    version = str(manifest.raw.get("version", "")) if manifest else ""

    meta = PairMeta(
        pair_id=pair_id, metric=result.name, left=left_id, right=right_id,
        n_left=left.n_nodes, n_right=right.n_nodes,
        summary=dict(result.summary), notes=dict(result.notes), created=_stamp(),
        metric_version=version,
    )
    _write_header(directory, {
        "pair_id": meta.pair_id, "metric": meta.metric,
        "left": meta.left, "right": meta.right,
        "n_left": meta.n_left, "n_right": meta.n_right,
        "schema": schema, "summary": meta.summary, "notes": meta.notes,
        "format_version": FORMAT_VERSION, "created": meta.created,
        "metric_version": meta.metric_version,
    })
    return meta


def read_pair(directory: Path) -> PairReader:
    return PairReader(directory)


__all__ = [
    "CORRESPONDENCE_DIR",
    "FORMAT_VERSION",
    "CorrespondenceMeta",
    "CorrespondenceReader",
    "PairMeta",
    "PairReader",
    "read_correspondence",
    "read_pair",
    "write_correspondence",
    "write_pair",
]

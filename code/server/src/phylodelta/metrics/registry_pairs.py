"""Find and open computed comparisons.

Mirrors ``trees.registry``: one memory-mapped reader per directory, opened once
and shared. A reader holds maps, not data.

Two things live under a pair: its **correspondence**, which is shared and keyed
by pair alone, and each **metric's** own columns. Correspondence is what
``order=difference`` ranks by, which is why that navigation mode works for any
metric — including one that contributes no per-node columns at all.

A metric may also bring a correspondence of its own (§52), stored among its
columns under the same two names. ``correspondence_for`` is the one place that
decides which of the two a request is served from.
"""

from __future__ import annotations

import threading

import numpy as np

from .. import config
from .store import CORRESPONDENCE_DIR, CorrespondenceReader, PairReader

_lock = threading.Lock()
_readers: dict[tuple[str, str], PairReader] = {}
_correspondence: dict[str, CorrespondenceReader] = {}
_priorities: dict[str, np.ndarray] = {}
#: Each registered metric's declared correspondence, read once per process for
#: the reason `store._declared_versions` is: this is asked on every slice.
_declared: dict[str, str] | None = None

#: What a request may ask to be coloured and linked by.
SOURCES = ("shared", "metric")


class PairNotFound(KeyError):
    pass


class CorrespondenceNotFound(KeyError):
    pass


class CorrespondenceNotStored(LookupError):
    """A metric declares its own correspondence, but this stored result has none.

    A result computed before the metric declared it. Refused rather than served
    from the shared correspondence instead: the view would then be coloured by
    Jaccard while saying it showed the metric's own pairing (§52).
    """


def declared_correspondence(metric: str) -> str:
    """What a metric's manifest says colours it; ``jaccard`` for one not registered."""
    global _declared
    if _declared is None:
        from . import registry

        _declared = {name: m.correspondence for name, m in registry.discover().items()}
    return _declared.get(metric, "jaccard")


def correspondence_for(pair_id: str, metric: PairReader | None, source: str = "shared"):
    """Which correspondence to serve, as ``(name, reader)``.

    ``shared`` is always the pair's Jaccard correspondence. ``metric`` is the
    one the metric declares: the shared one again for a metric that declares
    ``jaccard``, or the metric's own columns for one that declares ``self`` —
    then named after the metric. Both readers answer ``column(side, name)`` for
    ``similarity`` and ``corresponds``, so the caller reads either the same way.
    """
    if source not in SOURCES:
        raise ValueError(f"unknown correspondence source {source!r}; known: {list(SOURCES)}")
    if source == "shared" or metric is None:
        return "jaccard", get_correspondence(pair_id)
    name = metric.meta.metric
    if declared_correspondence(name) != "self":
        return "jaccard", get_correspondence(pair_id)
    if "similarity" not in metric.columns("left"):
        raise CorrespondenceNotStored(
            f"`{name}` for {pair_id} was computed before it produced its own "
            f"correspondence; recompute it (`phylodelta compute-pairs --only {pair_id} "
            f"--metric {name}`)."
        )
    return name, metric


def available(pair_id: str) -> list[str]:
    """Metrics computed for this pair. Correspondence is not one of them."""
    directory = config.PAIRS_DIR / pair_id
    if not directory.is_dir():
        return []
    return sorted(
        p.name
        for p in directory.iterdir()
        if p.name != CORRESPONDENCE_DIR and (p / "meta.json").exists()
    )


def has_correspondence(pair_id: str) -> bool:
    return (config.PAIRS_DIR / pair_id / CORRESPONDENCE_DIR / "meta.json").exists()


def get_correspondence(pair_id: str) -> CorrespondenceReader:
    with _lock:
        cached = _correspondence.get(pair_id)
    if cached is not None:
        return cached

    directory = config.PAIRS_DIR / pair_id / CORRESPONDENCE_DIR
    if not (directory / "meta.json").exists():
        raise CorrespondenceNotFound(pair_id)
    reader = CorrespondenceReader(directory)
    with _lock:
        return _correspondence.setdefault(pair_id, reader)


def get_pair(pair_id: str, metric: str) -> PairReader:
    key = (pair_id, metric)
    with _lock:
        cached = _readers.get(key)
    if cached is not None:
        return cached

    directory = config.PAIRS_DIR / pair_id / metric
    if metric == CORRESPONDENCE_DIR or not (directory / "meta.json").exists():
        raise PairNotFound(f"{pair_id}/{metric}")
    reader = PairReader(directory)
    with _lock:
        return _readers.setdefault(key, reader)


def divergence_priority_for(
    pair_id: str, side: str, parent, source: tuple[str, object] | None = None
) -> np.ndarray:
    """Cached ``order=difference`` priority for one side of a pair.

    Keyed by pair, side and **correspondence** — not by metric. Every metric
    that declares the shared correspondence ranks the same way, so switching
    between them does not invalidate it and a metric with no per-node columns
    still supports the navigation. A metric's own correspondence ranks by its
    own similarity (§52): "most different first" then means what that metric
    calls different. ``source`` is what `correspondence_for` returned.
    """
    from ..trees.summarise import divergence_priority

    name, reader = source if source is not None else ("jaccard", None)
    key = f"{pair_id}/{side}/{name}"
    with _lock:
        cached = _priorities.get(key)
    if cached is not None:
        return cached

    reader = reader if reader is not None else get_correspondence(pair_id)
    similarity = np.asarray(reader.column(side, "similarity"))
    value = divergence_priority(similarity, parent)
    with _lock:
        return _priorities.setdefault(key, value)


def reset_cache() -> None:
    global _declared
    with _lock:
        _declared = None
        _readers.clear()
        _correspondence.clear()
        _priorities.clear()

"""Open stored trees once per process.

``TreeReader`` holds memory maps, not data: the cache costs a few hundred bytes
per tree and lets the kernel's page cache do the real caching, shared across
workers. Nothing here loads a tree into the heap.
"""

from __future__ import annotations

import threading
from pathlib import Path

from .. import config
from .search import LabelIndex
from .store import TreeReader

_lock = threading.Lock()
_readers: dict[str, TreeReader] = {}


class TreeNotFound(KeyError):
    pass


def _trees_dir() -> Path:
    return config.TREES_DIR


def available_tree_ids() -> list[str]:
    root = _trees_dir()
    if not root.is_dir():
        return []
    return sorted(p.name for p in root.iterdir() if (p / "meta.json").exists())


def get_tree(tree_id: str) -> TreeReader:
    with _lock:
        reader = _readers.get(tree_id)
        if reader is not None:
            return reader
    # Built outside the lock: opening is cheap but the first call also validates
    # the header, and a slow disk should not block every other tree's lookup.
    directory = _trees_dir() / tree_id
    if not (directory / "meta.json").exists():
        raise TreeNotFound(tree_id)
    reader = TreeReader(directory)
    with _lock:
        return _readers.setdefault(tree_id, reader)


_label_indexes: dict[str, LabelIndex] = {}


def label_index(tree_id: str) -> LabelIndex:
    """The tree's named nodes, sorted for search (§37), built once per process.

    Unlike everything else here this is heap, not a memory map: bisection needs
    the labels decoded and in order, and the store keeps them in pre-order. It
    is built on the first search of a tree rather than at startup, so a tree
    nobody searches costs nothing.
    """
    cached = _label_indexes.get(tree_id)
    if cached is not None:
        return cached
    index = LabelIndex(get_tree(tree_id).labels())
    with _lock:
        return _label_indexes.setdefault(tree_id, index)


def reset_cache() -> None:
    """Drop every open map. Used by tests that rebuild a fixture store."""
    with _lock:
        _readers.clear()
        _label_indexes.clear()

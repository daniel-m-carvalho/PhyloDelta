from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
DATASETS = REPO_ROOT / "datasets"


#: What the repository ships, and so what the tests are written against.
#: `datasets/` is also where a developer drops a tree to try it — two did,
#: `staphylococcus-nj` and `aureus-rapidnj` — and every count, listing and
#: pairing assertion then failed on data no commit contains. The tests see
#: these files and nothing else, so what sits beside them cannot move them.
SHIPPED = (
    "gen_trees/vibrio-upgma-tree.nwk",
    "gen_trees/vibrio-nj-tree.nwk",
    "gen_trees/clostridium-upgma-tree.nwk",
    # Not ingested (§1.8) — kept so the catalogue's skipping them stays tested.
    "gen_trees/vibrio-goeburst-tree.nwk",
    "gen_trees/clostridium-goeburst-tree.nwk",
    "gen_trees/salmonella-100k-goeburst-tree.nwk",
    "isolated_data/vibrio.tsv",
    "isolated_data/clostridium.tsv",
)


@pytest.fixture(scope="session")
def datasets_dir(tmp_path_factory) -> Path:
    """The shipped datasets, linked into a folder of their own."""
    if not DATASETS.is_dir():
        pytest.skip(f"datasets not present at {DATASETS}")
    missing = [name for name in SHIPPED if not (DATASETS / name).is_file()]
    if missing:
        pytest.skip(f"datasets incomplete, missing {missing}")
    root = tmp_path_factory.mktemp("datasets")
    for name in SHIPPED:
        (root / name).parent.mkdir(parents=True, exist_ok=True)
        (root / name).symlink_to(DATASETS / name)
    return root


@pytest.fixture(scope="session")
def real_store(tmp_path_factory, datasets_dir: Path) -> Path:
    """Ingest the real trees once into a throwaway store.

    Built from the datasets rather than from a committed fixture so the tests
    exercise the same path the precompute CLI takes, and so a parser change
    cannot pass against a stale fixture.
    """
    from phylodelta.precompute.pipeline import ingest_trees

    store = tmp_path_factory.mktemp("store")
    assert ingest_trees(datasets_dir=datasets_dir, store_dir=store) == 0
    return store


@pytest.fixture(scope="session")
def compared_store(tmp_path_factory, datasets_dir: Path) -> Path:
    """A store with the trees ingested *and* every pair computed.

    Separate from `real_store` rather than computed into it, so that tests
    which need an uncomputed store keep one. Costs a few seconds once per
    session.
    """
    from phylodelta.precompute.pipeline import compute_pairs, ingest_trees

    store = tmp_path_factory.mktemp("compared")
    assert ingest_trees(datasets_dir=datasets_dir, store_dir=store) == 0
    assert compute_pairs(store_dir=store, datasets_dir=datasets_dir) == 0
    return store

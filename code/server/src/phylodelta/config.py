"""Where things live.

Both directories are overridable by environment variable so the service can be
deployed with the store somewhere other than the repository, and so tests can
point at a fixture store without touching the real one.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

# .../code/server/src/phylodelta/config.py -> .../repo/theses
_REPO_ROOT = Path(__file__).resolve().parents[3].parent


def _dir_from_env(var: str, default: Path) -> Path:
    raw = os.environ.get(var)
    return Path(raw).expanduser().resolve() if raw else default


#: Read-only source data: the Newick trees and the isolate TSVs.
DATASETS_DIR = _dir_from_env("PHYLODELTA_DATASETS", _REPO_ROOT / "datasets")

#: The species the demo is built from (§41). `datasets/gen_trees` is also where
#: a tree gets dropped to try it, and anything matching the filename pattern
#: was loaded and compared with everything else — a *Staphylococcus* tree put
#: there would have been paired with vibrio and clostridium on the home page,
#: matching sequence-type numbers that mean nothing across species. Other
#: trees are compared by uploading them. Comma-separated to override.
DEMO_SPECIES: tuple[str, ...] = tuple(
    part.strip()
    for part in os.environ.get("PHYLODELTA_DEMO_SPECIES", "vibrio,clostridium").split(",")
    if part.strip()
)

#: Generated artefacts. Rebuildable from DATASETS_DIR, so it is gitignored.
STORE_DIR = _dir_from_env("PHYLODELTA_STORE", Path(__file__).resolve().parents[2] / "store")

TREES_DIR = STORE_DIR / "trees"
PAIRS_DIR = STORE_DIR / "pairs"
ISOLATES_DIR = STORE_DIR / "isolates"

#: Where built native helpers live — the conformance oracle, and any metric that
#: is a binary rather than a Python function. Sources and build scripts are in
#: the repository; what they produce is not, so this is gitignored and
#: rebuildable (see native/build_treediff.sh).
NATIVE_DIR = _dir_from_env(
    "PHYLODELTA_NATIVE", Path(__file__).resolve().parents[2] / "native"
)


def threads() -> int:
    """How many threads the native search may use. 0 means one per core.

    Overridable because a shared machine should not have its whole CPU taken by
    an offline batch, and because the tests pin it to compare thread counts —
    the result must not depend on this value.

    A value that is not a count is refused by name, not read as 0: 0 means
    every core, the opposite of what someone setting this usually wants. The
    CLI checks it once at start (`pipeline.main`), so a bad value stops a
    command before it begins rather than a batch halfway through.
    """
    raw = os.environ.get("PHYLODELTA_THREADS", "").strip()
    if not raw:
        return 0
    try:
        count = int(raw)
    except ValueError:
        count = -1
    if count < 0:
        raise ValueError(
            f"PHYLODELTA_THREADS: {raw!r} is not a thread count "
            "(a whole number; 0 or unset means one per core)"
        )
    return count


_SIZE_UNITS = {"": 1, "K": 2**10, "M": 2**20, "G": 2**30, "T": 2**40}
_SIZE = re.compile(r"(?P<number>\d+(?:\.\d+)?)\s*(?:(?P<unit>[KMGT])(?:I?B)?)?")


def parse_size(text: str) -> int:
    """`2.5G`, `2560M`, `2684354560` → bytes. Units are binary (G = GiB).

    Refused by name rather than defaulted: a budget misread as "none" would let
    a metric run on exactly the pair it was meant to decline, and one misread
    as tiny would decline everything with a reason that blames the pair.
    """
    found = _SIZE.fullmatch(text.strip().upper())
    value = float(found["number"]) if found else 0.0
    if not value > 0:
        raise ValueError(f"{text!r} is not a size like 2.5G, 2560M or 2684354560")
    return int(value * _SIZE_UNITS[found["unit"] or ""])


def metric_memory() -> int | None:
    """Bytes one metric run may use beyond what the worker already holds (§50).

    A metric that declares a memory estimate (`limits.memory` in its
    metric.json) is declined when the estimate is over this. Set with
    PHYLODELTA_METRIC_MEMORY; read on every call, so tests and an operator's
    restart see a change without a code edit.

    **No default.** It is a property of the machine, so it is whoever deploys
    the app who sets it; a number chosen here would be right for one machine
    and wrong for the rest. Unset is None: no budget, and every metric runs.
    The worker says so when it starts.
    """
    raw = os.environ.get("PHYLODELTA_METRIC_MEMORY", "").strip()
    if not raw:
        return None
    try:
        return parse_size(raw)
    except ValueError as bad:
        raise ValueError(f"PHYLODELTA_METRIC_MEMORY: {bad}") from None


def format_size(n_bytes: int) -> str:
    """Bytes as the unit PHYLODELTA_METRIC_MEMORY is written in: 2.3 GiB, 594 MiB."""
    if n_bytes >= 2**30:
        return f"{n_bytes / 2**30:.1f} GiB"
    if n_bytes >= 2**20:
        return f"{n_bytes / 2**20:.0f} MiB"
    if n_bytes >= 2**10:
        return f"{n_bytes / 2**10:.0f} KiB"
    return f"{n_bytes} bytes"

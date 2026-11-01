"""What a build really did, read back from the pair it produced.

`PHYLODELTA_THREADS` is read by the worker, which the measuring tools neither
start nor control, so an argument saying how many threads ran only ever labels
the result. One such label stood for three days on a run that had used one
thread (§34.8). Every tool now asks the pair, and refuses rather than writes
when the answer is not what was asked for, or when there is no answer.
"""

from __future__ import annotations

import json
import urllib.request


def verified_threads(base: str, comparison_id: str, expected: int) -> int:
    """The resolved thread count of this build, or stop the run."""
    with urllib.request.urlopen(f"{base}/comparisons/{comparison_id}?metric=rf", timeout=120) as r:
        actual = (json.load(r).get("build") or {}).get("threads")
    if actual != expected:
        raise SystemExit(
            f"\nREFUSING TO WRITE: asked for {expected} threads, but {comparison_id} "
            f"reports {actual}. Start the worker with PHYLODELTA_THREADS={expected} "
            f"and re-run."
        )
    return actual

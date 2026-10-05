"""Find nodes by name (§37).

The client cannot do this. It holds a tree only as the slice it asked for —
fifty to two hundred nodes — so a name behind a wedge is not there to be found,
and sending every label so it could be would be the whole-tree download the
project exists to avoid.

**Every node with a real label, not only leaves.** In these trees a label is a
sequence type, and a tree format that puts STs on *internal* nodes — goeBURST,
whose files open `((9080,24265)8808, …` — would have searching leaves only
answer "not in this tree" for an ST that is in it. goeBURST is not ingested
(§1.8), and none of the three served trees names an internal node once stored
— vibrio-nj's file calls its root `211`, and suppressing that unary root drops
the name — so today this changes nothing. It is what keeps an uploaded tree
that does name ancestors from being searched wrongly. An unnamed node — `""`, or the `_` the NJ and UPGMA files
write for one — is not a name and is never matched.

**Exact first, then "starts with".** What the panels draw is the label as
stored, so typing what is on screen must find it, and first. A prefix match
comes after it for a mistyped or half-remembered name, shortest first, so `12`
lists `120` before `1200` — numeric order for numeric STs without parsing
anything as a number. "Contains" was considered and left out: for numbers it
mostly adds noise (`1203` inside `11203`, `51203`).

**Case-insensitive.** These labels are digits, where it changes nothing; for an
uploaded tree with names in it, `vc_` not finding `VC_` would be a miss nobody
could explain.
"""

from __future__ import annotations

import bisect
import heapq
from dataclasses import dataclass

#: Not names. `_` is what the source Newick writes for an unnamed internal node;
#: the client blanks it for the same reason (`UNLABELLED` in `fromSlice.ts`).
UNLABELLED = frozenset({"", "_"})

#: Above every character a label can contain, so `key + _TOP` bounds every
#: string that starts with `key`. U+10FFFF is a noncharacter; a label holding
#: it would sort past the bound and be missed by a prefix search, nothing worse.
_TOP = "\U0010ffff"


@dataclass(frozen=True)
class Match:
    node: int
    exact: bool


@dataclass(frozen=True)
class Found:
    matches: list[Match]
    #: Every match, not just those returned — so a client can say "20 of 8,758" (`1` on vibrio-upgma).
    total: int
    #: Of `total`, how many are the name exactly. More than one is possible:
    #: leaves are unique within a pairable tree, internal labels need not be.
    exact: int


class LabelIndex:
    """Labels sorted once, searched by bisection.

    Two parallel lists rather than a dict: a dict answers "is it exactly this",
    and a sorted list answers that *and* "what starts with this" in the same
    two bisections. Python lists of `str` rather than a numpy string array,
    because numpy's fixed-width strings are as wide as the longest label — one
    long name in an upload would size every entry to it.
    """

    def __init__(self, labels: list[str]) -> None:
        named = sorted(
            (label.casefold(), node)
            for node, label in enumerate(labels)
            if label not in UNLABELLED
        )
        self._keys = [key for key, _ in named]
        self._nodes = [node for _, node in named]

    def __len__(self) -> int:
        return len(self._keys)

    def search(self, query: str, limit: int) -> Found:
        key = query.strip().casefold()
        if not key:
            return Found(matches=[], total=0, exact=0)
        lo = bisect.bisect_left(self._keys, key)
        hi = bisect.bisect_left(self._keys, key + _TOP, lo)
        # Exact keys are the first run of the range: nothing starting with
        # `key` sorts before `key` itself.
        exact_end = bisect.bisect_right(self._keys, key, lo, hi)

        exact = [Match(node=n, exact=True) for n in self._nodes[lo:exact_end]]
        room = max(0, limit - len(exact))
        rest = range(exact_end, hi)
        # Shortest first, then alphabetical: the order a person reads a list
        # of numbers in. Only `room` are kept, so the cost is a pass over the
        # range rather than a sort of it.
        if room and len(rest) > room:
            rest = heapq.nsmallest(room, rest, key=lambda i: (len(self._keys[i]), i))
        else:
            rest = sorted(rest, key=lambda i: (len(self._keys[i]), i))[:room]
        prefix = [Match(node=self._nodes[i], exact=False) for i in rest]

        return Found(
            matches=(exact + prefix)[:limit],
            total=hi - lo,
            exact=exact_end - lo,
        )

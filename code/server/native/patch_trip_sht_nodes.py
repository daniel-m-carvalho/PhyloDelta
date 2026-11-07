"""Make `trip_sht_nodes` from TreeDiff's `trip_sht.cpp` (§54).

`trip_sht` counts, at every node of the first tree, the triples decided there
that both trees resolve alike (`values2[0]` in `triplets_coloring`), and prints
only their sum. This copy also writes each node's count, one per line in
pre-order, to the file named by a third argument. Nothing else changes: the
printed distance is the original's, which the metric checks.

A script rather than a diff, because the upstream file has CRLF line endings
that a diff would rewrite line by line; every replacement is asserted to apply
exactly where expected, so an upstream change fails the build by name.

    python3 patch_trip_sht_nodes.py trip_sht.cpp trip_sht_nodes.cpp
"""

import sys

source, target = sys.argv[1], sys.argv[2]
with open(source, newline="") as f:
    text = f.read()
nl = "\r\n" if "\r\n" in text else "\n"


def replace(old: str, new: str, count: int = 1) -> None:
    global text
    old, new = old.replace("\n", nl), new.replace("\n", nl)
    found = text.count(old)
    if found != count:
        sys.exit(f"patch_trip_sht_nodes: expected {count} of {old!r}, found {found}")
    text = text.replace(old, new)


replace(
    "using namespace sdsl;\n",
    "using namespace sdsl;\n\n"
    "// PhyloDelta: agreeing triples decided at each node of the first tree, by pre-order.\n"
    "static vector<long> agree_at;\n",
)
replace(
    "        dist = values2[0];\n",
    "        dist = values2[0];\n        agree_at[current - 1] = values2[0];\n",
    count=2,
)
replace(
    "    triplets_onlyleaves_2(vec_1, vec_2, code, 0, triplets_equal, size);\n",
    "    agree_at.assign(size, 0);\n"
    "    triplets_onlyleaves_2(vec_1, vec_2, code, 0, triplets_equal, size);\n",
)
replace(
    '    cout << "Triplets distance is: "',
    "    if(argc > 3){\n"
    '        FILE* out = fopen(argv[3], "w");\n'
    '        for(int i = 0; i < size; i++){ fprintf(out, "%ld\\n", agree_at[i]); }\n'
    "        fclose(out);\n"
    "    }\n"
    '    cout << "Triplets distance is: "',
)

with open(target, "w", newline="") as f:
    f.write(text)

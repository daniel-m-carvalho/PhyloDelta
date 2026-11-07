#!/usr/bin/env bash
#
# Build rspr (Whidden), the program the `spr` metric runs (§53).
#
# rspr computes rooted SPR distances and agreement forests: exactly when the
# distance is small enough to search, and by a linear-time 3-approximation
# otherwise. It is GPL-3.0, so — like TreeDiff (build_treediff.sh) — it is only
# ever run as a separate program and never linked into this MIT codebase.
#
# It also runs in the Docker builder, which is how the metric reaches the
# deployment: without it `spr` is registered and reports `available: false`.

set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEST="${1:-$HERE/rspr}"

if [ -x "$DEST/rspr" ]; then
  echo "rspr already built at $DEST — remove it to rebuild." >&2
  exit 0
fi

# **Pinned to one commit**, as TreeDiff is. Every measurement of the metric
# (DECISIONS §53) was made with this version, v1.3.1; a different rspr may
# print its forests differently, and the metric parses them.
RSPR_COMMIT=4530e11bac642ec8f1389f837314628208950605  # 2024-01-02, v1.3.1

rm -rf "$DEST"
git init -q "$DEST"
cd "$DEST"
git remote add origin https://github.com/cwhidden/rspr.git
git fetch -q --depth 1 origin "$RSPR_COMMIT"
git checkout -q FETCH_HEAD
HAVE=$(git rev-parse HEAD)
if [ "$HAVE" != "$RSPR_COMMIT" ]; then
  echo "fetched rspr ${HAVE:0:7}, not the pinned ${RSPR_COMMIT:0:7}" >&2
  exit 1
fi

# Its Makefile adds -march=native, which ties the binary to the build machine's
# CPU; a Docker image is built on one machine and run on another.
"${CXX:-g++}" -O2 -std=c++0x -o rspr rspr.cpp

echo "Built $DEST/rspr. Sanity check, one leaf moved (expect drSPR=1):"
printf '((((A,B),C),D),E);\n((((A,B),D),C),E);\n' | ./rspr -approx -q | grep "drSPR=1"

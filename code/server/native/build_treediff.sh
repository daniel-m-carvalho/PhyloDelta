#!/usr/bin/env bash
#
# Build TreeDiff (Branco, Vaz & Francisco 2024) and its sdsl-lite dependency.
#
# TreeDiff is the reference C++ implementation of the RF algorithm this backend
# follows. It is used as the conformance oracle for our own implementation, and
# is the intended basis for the succinct-representation store.
#
# Neither project builds unmodified on macOS 27 / arm64 with CMake 4.x and
# Apple clang 21. Four fixes are needed, each documented at its site below
# (a fifth, the double-precision build, is a correction rather than a build fix).
# None is optional and none is discoverable from the projects' own READMEs.
#
# It also runs in the Docker builder (Debian, g++), which is how the triplet and
# rf-treediff metrics reach the deployment: without it they are registered and
# report `available: false`, and the upload form has nothing to offer but rf.
# The macOS-only fixes are applied only on macOS.

set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEST="${1:-$HERE/TreeDiff}"

if [ -d "$DEST" ]; then
  echo "TreeDiff already present at $DEST — remove it to rebuild from scratch." >&2
  exit 0
fi

# **Pinned to one commit**, as native/build.sh pins sdsl-lite. This cloned
# whatever was newest, so a change upstream could break the build or change
# what the programs compute with nothing changed here — and rf-treediff is the
# oracle our own RF is checked against, so its output must not move under it.
# This is the newest commit, the one every measurement in this project was made
# with. TreeDiff's own sdsl-lite is a submodule, so this pins that too. To move
# it, change the hash, delete native/TreeDiff, rebuild and re-run the suite.
TREEDIFF_COMMIT=1fa132a440655446f7288a2ebc9a022543f96ed7  # 2024-01-14

# A shallow clone cannot check out a named commit, so fetch exactly that one.
git init -q "$DEST"
cd "$DEST"
git remote add origin https://github.com/pedroparedesbranco/TreeDiff.git
git fetch -q --depth 1 origin "$TREEDIFF_COMMIT"
git checkout -q FETCH_HEAD
HAVE=$(git rev-parse HEAD)
if [ "$HAVE" != "$TREEDIFF_COMMIT" ]; then
  # Refused, not built against: a different TreeDiff may compute differently.
  echo "fetched TreeDiff ${HAVE:0:7}, not the pinned ${TREEDIFF_COMMIT:0:7}" >&2
  exit 1
fi
git submodule update --init

# --- Fix 1: sdsl-lite predates CMake 3.5 -----------------------------------
# sdsl-lite's CMakeLists declares cmake_minimum_required(VERSION 2.8.7). CMake
# 4.x removed compatibility with < 3.5 and refuses to configure. The env var
# restores the old policy behaviour without editing upstream files.
export CMAKE_POLICY_VERSION_MINIMUM=3.5

# --- Fix 2: sdsl mistakes Apple clang for MSVC ------------------------------
# sdsl's compiler detection tests `CMAKE_CXX_COMPILER MATCHES ".*clang.*"` or
# `CMAKE_CXX_COMPILER_ID STREQUAL "Clang"`. Apple's id is "AppleClang" and
# CMake's default compiler path is /usr/bin/c++, so BOTH tests fail and it
# falls through to the MSVC branch, which defines -DMSVC_COMPILER and makes
# util.hpp include <process.h> — a Windows header. Naming a compiler path that
# literally contains "clang" satisfies the first test.
if [ "$(uname -s)" = "Darwin" ]; then
  export CXX=/usr/bin/clang++
  export CC=/usr/bin/clang
else
  # GCC is detected correctly, so there is nothing to work around.
  export CXX="${CXX:-g++}"
  export CC="${CC:-gcc}"
fi

# --- Fix 3: an upstream typo in louds_tree.hpp ------------------------------
# louds_tree::swap references tree.m_select1 / tree.m_select0, which do not
# exist; the members are m_bv_select1 / m_bv_select0. It survived since 2015
# because swap is a template member that was never instantiated, and because
# older compilers deferred the lookup. Clang 21 diagnoses it at definition
# time. louds_tree is not used by TreeDiff at all, but it is compiled into
# libsdsl, so the build fails without this.
sed -i.bak \
  -e 's/tree\.m_select1/tree.m_bv_select1/' \
  -e 's/tree\.m_select0/tree.m_bv_select0/' \
  sdsl-lite/include/sdsl/louds_tree.hpp

( cd sdsl-lite && ./install.sh ../sdsl )

# --- Fix 4: TreeDiff's Makefile assumes GCC and static linking --------------
# `-static` cannot work on macOS (no static libc is shipped). TreeDiff's own
# README gives the clang recipe; the Makefile just does not default to it.
# Dropped on Linux too: the runtime image has libstdc++, and a static glibc
# binary warns about every lookup it cannot make static. The compiler is
# whichever was chosen above.
sed -i.bak \
  -e "s|^  CC = g++|  CC = $CXX|" \
  -e 's|^  CFLAGS  = -O3 -Wall -static|  CFLAGS  = -O3 -Wall -std=c++11|' \
  Makefile

# --- Fix 5: wRF accumulates in float32 and loses precision at scale ---------
# The weighted variants store weights and the running distance as `float`, and
# compute wRF by summing every weight in both trees and then correcting
# downward per shared cluster (paper S3.4). On the vibrio UPGMA tree the total
# is 4.78e6 while individual corrections are ~1e0, so the cancellation falls
# below float32 resolution: comparing the tree with ITSELF yields -28.4947
# instead of 0. Rebuilding the same source with double gives 1.95e-08.
# The double build is produced alongside the original, not instead of it, so
# the discrepancy stays reproducible as evidence.
sed 's/float/double/g; s/stof/stod/g' rf_postorder.cpp > rf_postorder_double.cpp
sed 's/float/double/g; s/stof/stod/g' rf_nextsibling.cpp > rf_nextsibling_double.cpp

make
"$CXX" -O3 -Wall -std=c++11 -I./sdsl/include/ rf_postorder_double.cpp   sdsl/lib/libsdsl.a -o rf_postorder_double
"$CXX" -O3 -Wall -std=c++11 -I./sdsl/include/ rf_nextsibling_double.cpp sdsl/lib/libsdsl.a -o rf_nextsibling_double

echo
echo "Built in $DEST:"
ls -1 rf_postorder rf_postorder_double rf_nextsibling rf_nextsibling_double rf_day trip_treediff trip_sht

echo
echo "Sanity check against the paper's own documented example (expect RF = 1):"
./rf_postorder tree_examples/treeA.txt tree_examples/treeB.txt

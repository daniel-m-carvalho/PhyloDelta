"""Every table the comparison needs, generated from the result files.

Written as a generator rather than transcribed into the thesis by hand: a
number that is copied is a number that silently stops matching its source the
first time anything is re-run. Everything here reads `results/*.json` and can
be regenerated after any change.

    python3 harness/make_tables.py > results/TABLES.md
"""

from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
RESULTS = HERE.parent / "results"


def load(name, default=None):
    path = RESULTS / name
    return json.loads(path.read_text()) if path.exists() else default


ceiling = load("ceiling.json", {})
server = {r["leaves"]: r for r in load("server_build.json", [])}
endurance = load("endurance.json", [])
rows = ceiling.get("rows", [])


def fmt(value, unit="", nd=1, dash="—"):
    return dash if value is None else f"{value:,.{nd}f}{unit}"


print("# PhyloDelta vs Phylo.io — measured comparison\n")
print(
    f"All measurements: **{ceiling.get('browser', 'Chrome')}**, viewport "
    f"{ceiling.get('viewport', {}).get('width', 1440)}x{ceiling.get('viewport', {}).get('height', 900)}, "
    "macOS, 24 GB RAM, 10 cores. Both tools served from one origin, uncompressed, "
    "one fresh page each.\n"
)

# --- 1. the headline ------------------------------------------------------
print("## Table 1 — Scalability: where each tool stops\n")
print("> **Heap here is MAIN-THREAD ONLY.** `Runtime.getHeapUsage` reads one "
      "isolate, and phylo.io computes its comparison in a **Web Worker** with "
      "a heap of its own. Where the comparison finishes, the worker's results "
      "are copied back and the figure reflects them; where it does not, the "
      "column shows only the two parsed trees and so *falls* as the tree "
      "grows. It is a lower bound, not the tool's memory. Table 4's RSS "
      "figures, which cover the whole renderer including workers, are the "
      "honest memory numbers.\n")
print("Cold start to an interactive comparison. Phylo.io is split into *paint* "
      "(two trees drawn) and *compare* (its best-corresponding-node worker "
      "finished), because only the second is the same job PhyloDelta is doing: "
      "a slice arrives with its similarity values already in it.\n")
print("| leaves | phylo.io paint | phylo.io compare | phylo.io main-thread heap | PhyloDelta | PhyloDelta heap | PhyloDelta advantage | server precompute |")
print("|---:|---:|---:|---:|---:|---:|---:|---:|")
for row in rows:
    p, d = row["phyloio"], row["phylodelta"]
    leaves = row["leaves"]
    if p.get("ok"):
        ph = p.get("phases") or {}
        paint = fmt(ph.get("postFetch", p["ms"]) / 1000, " s")
        comp = fmt(ph["toCompare"] / 1000, " s", 0) if ph.get("compareComplete") else "**did not finish**"
        heap = fmt(p.get("heap_mb"), " MB")
    else:
        paint = comp = heap = "**failed**"
    # Compared against phylo.io's COMPARE time, not its paint: that is the
    # point at which it is doing the same job.
    ratio = "—"
    if p.get("ok") and d.get("ok"):
        ph = p.get("phases") or {}
        reference = ph.get("toCompare") if ph.get("compareComplete") else None
        if reference and d["ms"]:
            ratio = f"**{reference / d['ms']:,.0f}x**"
    elif not p.get("ok") and d.get("ok"):
        ratio = "**only PhyloDelta**"
    print(
        f"| {leaves:,} | {paint} | {comp} | {heap} | "
        f"{fmt(d['ms'] / 1000, ' s', 2) if d.get('ok') else '**failed**'} | "
        f"{fmt(d.get('heap_mb'), ' MB')} | {ratio} | "
        f"{fmt(server.get(leaves, {}).get('build_s'), ' s')} |"
    )

# --- 2. fairness ----------------------------------------------------------
print("\n## Table 2 — What each tool actually drew\n")
print("The check that makes Table 1 admissible. An earlier comparison in this "
      "project reported a ~34x speedup that was an artefact of the two tools "
      "rendering 91 and 2,002 nodes. **Both tools draw a roughly constant "
      "amount** — so the difference in Table 1 is not "
      "\"one of them drew less\".\n")
print("> Rows from 17,645 up show phylo.io's **pre-comparison** render only: "
      "when the worker finishes it rebuilds and redraws both panels with the "
      "similarity colouring, and where it never finishes that second render "
      "never happens. That is why the counts fall rather than rise. The point "
      "of the table is unaffected — the counts are flat or falling in every "
      "case, never proportional to the tree.\n")
print("| leaves | phylo.io SVG paths | phylo.io DOM nodes | PhyloDelta canvases | PhyloDelta tips drawn |")
print("|---:|---:|---:|---:|---|")
for row in rows:
    p, d = row["phyloio"], row["phylodelta"]
    drawn = (p.get("drawn") or {}) if p.get("ok") else {}
    dom = p.get("dom") or {}
    shown = (d.get("drawn") or {}).get("shown") or []
    tips = shown[0].split(" of ")[0].replace("showing ", "") if shown else "—"
    print(
        f"| {row['leaves']:,} | {drawn.get('paths', '—')} | {dom.get('nodes', '—'):,} | "
        f"{(d.get('drawn') or {}).get('canvases', '—')} | {tips} per panel |"
        if p.get("ok") else
        f"| {row['leaves']:,} | failed | failed | {(d.get('drawn') or {}).get('canvases', '—')} | {tips} per panel |"
    )

# --- 3. the mechanism -----------------------------------------------------
print("\n## Table 3 — Memory, and why it grows for one tool and not the other\n")
print("Phylo.io's DOM is flat while its heap climbs steeply: it **models the "
      "whole tree** in the browser, and on top of that holds MinHash sketches "
      "and a score per node, which scale with the *comparison* rather than "
      "with the tree. PhyloDelta never receives the tree at all.\n")
print("Rows where the comparison did not finish are marked — their figure "
      "excludes the worker entirely and must not be read as a decrease.\n")
print("| leaves | phylo.io main-thread heap | growth vs previous | PhyloDelta heap |")
print("|---:|---:|---:|---:|")
previous = None
for row in rows:
    p, d = row["phyloio"], row["phylodelta"]
    finished = bool((p.get("phases") or {}).get("compareComplete"))
    heap = p.get("heap_mb") if p.get("ok") else None
    growth = f"{heap / previous:.2f}x" if heap and previous and finished else "—"
    note = "" if finished else " *(compare unfinished — worker excluded)*"
    print(f"| {row['leaves']:,} | {fmt(heap, ' MB')}{note} | {growth} | {fmt(d.get('heap_mb'), ' MB')} |")
    if heap and finished:
        previous = heap

# --- 4. failure -----------------------------------------------------------
if endurance:
    print("\n## Table 4 — Failure behaviour, given 30 minutes and 16 GB\n")
    print("Table 1's failures are against a stated budget. This removes the "
          "budget: each rung was given **30 minutes** with a 16 GB renderer cap "
          "on a 24 GB machine.\n")
    print("| leaves | outcome | time to failure | peak renderer |")
    print("|---:|---|---:|---:|")
    for r in endurance:
        outcome = "completed" if r.get("ok") else "**renderer process crashed**"
        print(
            f"| {r['leaves']:,} | {outcome} | {r['ms'] / 60000:.1f} min | "
            f"{r['peak_renderer_mb']:,} MB |"
        )
    print("\n*Peak memory is sampled every 2 s from process RSS, so it is a lower "
          "bound and the two figures should not be read as an ordering.*")

# --- 5. accuracy ----------------------------------------------------------
accuracy = []
for path in sorted(RESULTS.glob("bcn_accuracy*.json")):
    accuracy.append(json.loads(path.read_text()))
if accuracy:
    print("\n## Table 5 — Accuracy: what the LSH approximation costs\n")
    print("Phylo.io finds each clade's best corresponding node by maximising "
          "Jaccard over **ten candidates** retrieved by MinHash/LSH "
          "(`worker_bcn.js`). This project maximises over every node, so it is "
          "an upper bound and every gap is a retrieval miss. Run on pairs with "
          "**identical leaf sets**, so a difference cannot be explained by "
          "unmatched-leaf handling.\n")
    print("| leaves | clades | exact match | missed | median gap | worst gap | beat exact |")
    print("|---:|---:|---:|---:|---:|---:|---:|")
    for a in accuracy:
        n = a["comparable"]
        print(
            f"| {a.get('leaves', '—')} | {n:,} | {a['exact_match']:,} ({a['exact_match']/n:.1%}) | "
            f"{a['worse']:,} ({a['worse']/n:.1%}) | {a['gap_median']:.3f} | {a['gap_worst']:.3f} | "
            f"{a['higher_than_exact']} |"
        )
    print("\n*`beat exact` must be 0: an exhaustive search cannot be beaten by a "
          "subset of the same candidates. It is reported as a check on the "
          "method, not as a result.*")

# --- 5b. where phylo.io's time goes ---------------------------------------
print("\n## Table 6 — Where phylo.io's time goes\n")
print("Its own phase split. Parsing and drawing are cheap and near-linear; "
      "**the comparison is what scales badly** — which is the same finding as "
      "this project's own correspondence search being the quadratic step "
      "(DECISIONS §17), reached independently by both implementations.\n")
print("| leaves | parse | layout | paint | compare | compare as % of total |")
print("|---:|---:|---:|---:|---:|---:|")
for row in rows:
    p = row["phyloio"]
    if not p.get("ok"):
        print(f"| {row['leaves']:,} | — | — | — | **failed** | — |")
        continue
    ph = p.get("phases") or {}
    total = (ph.get("postFetch") or 0) + (ph.get("toCompare") or 0)
    share = f"{(ph['toCompare'] / total):.0%}" if ph.get("compareComplete") and total else "—"
    print(
        f"| {row['leaves']:,} | {fmt((ph.get('parse') or 0) / 1000, ' s', 2)} | "
        f"{fmt((ph.get('layout') or 0) / 1000, ' s', 2)} | "
        f"{fmt((ph.get('paint') or 0) / 1000, ' s', 2)} | "
        f"{fmt(ph['toCompare'] / 1000, ' s', 0) if ph.get('compareComplete') else '**>600 s**'} | {share} |"
    )

# --- 5c. how solid the PhyloDelta numbers are -----------------------------
repeats = load("phylodelta_repeats.json", [])
if repeats:
    print("\n## Table 7 — PhyloDelta, repeated\n")
    print("Six samples per rung after a discarded warm-up. Included because "
          "sub-second figures are at this harness's noise floor: a single "
          "sample per rung first reported 2.7 s and 3.6 s at the top two "
          "rungs, which no repeat could reproduce.\n")
    print("| leaves | nodes | median | min | max | heap |")
    print("|---:|---:|---:|---:|---:|---:|")
    for r in repeats:
        nodes = r["leaves"] * 2 - 1
        beyond = " *(beyond phylo.io — it crashes at 141,160)*" if r["leaves"] > 141160 else ""
        print(
            f"| {r['leaves']:,} | {nodes:,} | **{r['median_ms'] / 1000:.2f} s** | "
            f"{r['min_ms'] / 1000:.2f} s | {r['max_ms'] / 1000:.2f} s | {r['heap_mb']} MB{beyond} |"
        )

# --- 5d. the server side ---------------------------------------------------
if server:
    print("\n## Table 8 — The precompute PhyloDelta pays instead\n")
    print("Measured through the real upload path: POST the bundle, a worker "
          "claims it, poll until ready. Includes ingest, reconciliation, the "
          "correspondence search and the metric.\n")
    print("| leaves | upload | build | total | bundle size |")
    print("|---:|---:|---:|---:|---:|")
    for leaves in sorted(server):
        r = server[leaves]
        print(
            f"| {leaves:,} | {r['upload_s']:.1f} s | {r['build_s']:.1f} s | "
            f"{r['total_s']:.1f} s | {r['bytes'] / 1e6:.1f} MB |"
        )
    print("\n*The ~2 s floor at small sizes is the worker's poll interval, not "
          "work.*")

# --- 5e. the mechanism, directly ------------------------------------------
latency = load("slice_latency.json", [])
if latency:
    print("\n## Table 9 — The request a panel actually makes\n")
    print("The **cause**, where every other table shows the consequence. The "
          "same GET the frontend issues, at every tree size, read-only. "
          "Latency and payload are set by the viewport budget, so neither "
          "tracks the tree: **564x more leaves, the same few milliseconds and "
          "the same few kilobytes.**\n")
    print("| leaves | median | min | max | response | leaves drawn |")
    print("|---:|---:|---:|---:|---:|---:|")
    for r in latency:
        print(
            f"| {r['leaves']:,} | **{r['median_ms']:.1f} ms** | {r['min_ms']:.1f} ms | "
            f"{r['max_ms']:.1f} ms | {r['bytes'] / 1024:.1f} KB | {r['displayed_leaves']} |"
        )
    first, last = latency[0], latency[-1]
    print(
        f"\n*From {first['leaves']:,} to {last['leaves']:,} leaves — a "
        f"{last['leaves'] / first['leaves']:.0f}x increase — the median moves "
        f"{first['median_ms']:.1f} ms to {last['median_ms']:.1f} ms and the "
        f"payload {first['bytes'] / 1024:.1f} KB to {last['bytes'] / 1024:.1f} KB. "
        "Seven samples per rung after a warm-up, since the first touch of a "
        "store memory-maps it.*")

# --- 6. the honest ledger -------------------------------------------------
print("\n## Table 10 — What the design costs\n")
print("| | phylo.io | PhyloDelta |")
print("|---|---|---|")
print("| Server required | no | **yes** |")
print("| Precompute before first view | none | up to "
      f"{max((r['build_s'] for r in server.values()), default=0):.0f} s |")
print("| Whole tree ever visible | yes, in memory | **no, never transferred** |")
print("| Works offline from a file | yes | no |")
print("| Comparison recomputed on demand | yes | no, fixed at build |")

print("\n## Table 11 — Provenance of the test data\n")
print("| rung | origin |")
print("|---:|---|")
print("| 1,000 – 10,000 | pruned subsamples of the real vibrio NJ/UPGMA pair |")
print("| 17,645 | **the real pair, unmodified** |")
print("| 35,290 – 564,640 | nested relabelled copies of the real pair, preserving depth and imbalance |")
print("\n*Every rung verified as a genuine comparison pair: 100% shared leaf "
      "sets, depth 79 to 191. Real MLST data stops at 27,962 leaves "
      "(clostridium), so rungs above 17,645 are synthetic and are used only for "
      "performance claims.*")

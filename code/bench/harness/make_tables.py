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
#: Full builds at pinned thread counts. Table 8 reports the 2-thread column as
#: the deployment setting; Table 9 compares all three.
pinned = {n: load(f"thread_builds_{n}.json") for n in (1, 2)}
navigation = load("navigation.json", {})
metric_builds = load("metric_builds.json", {})
metric_phases = load("metric_phases.json", {})
rows = ceiling.get("rows", [])


def fmt(value, unit="", nd=1, dash="—"):
    return dash if value is None else f"{value:,.{nd}f}{unit}"


print("# PhyloDelta vs Phylo.io — measured comparison\n")
print("## Environment\n")
print("| | |")
print("|---|---|")
print("| Machine | Apple silicon laptop, macOS |")
print("| CPU | 10 cores — **4 performance, 6 efficiency** |")
print("| RAM | 24 GB |")
print(f"| Browser | {ceiling.get('browser', 'Chrome')} |")
print(f"| Viewport | {ceiling.get('viewport', {}).get('width', 1440)} x "
      f"{ceiling.get('viewport', {}).get('height', 900)} |")
print("| **Backend threads** | **2 of the 10 cores** (`PHYLODELTA_THREADS=2`) |")
print("| Transport | one origin, uncompressed, one fresh page per measurement |")
print()
print("**Only 2 of the 10 cores are used for the backend**, deliberately. "
      "Table 9 is the measurement behind that choice: two threads give ~2x at "
      "94% efficiency where ten give ~4.7x at 57%, so eight further cores buy "
      "the last 2.3x at a steeply falling rate. Every build figure in these "
      "tables is therefore what a **two-core** deployment costs, not what this "
      "machine can do flat out.\n")


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
    two_thread = {r["leaves"]: r["build_s"] for r in (pinned.get(2) or {"rungs": []})["rungs"]}
    print("\n## Table 8 — The precompute PhyloDelta pays instead\n")
    print("Measured through the real upload path: POST the bundle, a worker "
          "claims it, poll until ready. Includes ingest, reconciliation, the "
          "correspondence search and the metric.\n")
    print("**At 2 threads**, the deployment setting (see Environment and "
          "Table 9). The 10-thread column is kept because the first runs used "
          "the default, and because the gap is the cost of the choice.\n")
    print("| leaves | build at 2 threads | build at 10 threads | bundle size |")
    print("|---:|---:|---:|---:|")
    for leaves in sorted(server):
        r = server[leaves]
        at_two = two_thread.get(leaves)
        print(
            f"| {leaves:,} | **{at_two:.1f} s** | {r['build_s']:.1f} s | "
            f"{r['bytes'] / 1e6:.1f} MB |"
            if at_two is not None else
            f"| {leaves:,} | — | {r['build_s']:.1f} s | {r['bytes'] / 1e6:.1f} MB |"
        )
    print("\n*The ~2 s floor at small sizes is the worker's poll interval, not "
          "work.*")

# Emitted only once both pinned runs exist, so a half-finished experiment
# cannot appear as a finished table.
if all(pinned.values()):
    print("\n## Table 9 — Build time at pinned thread counts\n")
    print("Table 8 used the default — one thread per hardware thread, **10** on "
          "this machine. These are the same builds with the count pinned, "
          "through the same upload path, each on its own store.\n")
    print("| leaves | 1 thread | 2 threads | 10 threads | 2 vs 1 | 10 vs 1 |")
    print("|---:|---:|---:|---:|---:|---:|")
    one = {r["leaves"]: r["build_s"] for r in pinned[1]["rungs"]}
    two = {r["leaves"]: r["build_s"] for r in pinned[2]["rungs"]}
    for leaves in sorted(one):
        ten = server.get(leaves, {}).get("build_s")
        a, b = one[leaves], two.get(leaves)
        if not (ten and b):
            continue
        # Below 35,290 the worker's 2 s poll interval is most of the elapsed
        # time, so the ratios are noise: this is where 1,000 leaves "gains"
        # 3.81x and 5,000 "loses" 0.80x.
        mark = ""
        if leaves < 35_290:
            mark = " *(floor-limited — ratios are noise)*"
        elif leaves == 564_640:
            mark = " *(see note)*"
        print(
            f"| {leaves:,}{mark} | {a:.1f} s | {b:.1f} s | {ten:.1f} s | "
            f"{a / b:.2f}x | {a / ten:.2f}x |"
        )
    print("\n**Read the middle rows.** From 35,290 to 282,320 the picture is "
          "clean and monotone: two threads rise 1.33x -> 2.01x, ten rise "
          "2.00x -> 4.65x. The gain grows with size because below ~70,000 "
          "leaves the *serial* parts — parse, reconcile, ingest, and the 2 s "
          "poll — are most of the elapsed time, and threading the search "
          "cannot touch them. Amdahl's law, visible directly.\n")
    print("**The 564,640 row should not be quoted as a ratio.** Two threads "
          "appear to give 2.44x, which is superlinear and therefore impossible "
          "for pure parallelism, and ten threads appear to *fall* to 3.54x, "
          "breaking an otherwise monotone trend. Both point at the machine "
          "rather than the code: the single-threaded run took **20 minutes**, "
          "long enough for thermal state to drift, and this rung's 10-thread "
          "baseline is the disputed one (339.5 s here, 196.4 s in another "
          "store — see DECISIONS §34.8). Against 196.4 s the 10-thread gain is "
          "6.11x and the trend continues. The absolute times stand; the ratios "
          "for this row do not.\n")
    print("**What to choose.** Two threads gives ~2x at 94% efficiency; ten "
          "gives ~4.7x at 57%. One thread wastes a near-free doubling. If "
          "efficiency is the objective, **two is the sweet spot** — but "
          "latency for a single comparison favours more threads, and "
          "throughput for a queue favours fewer per build with more builds at "
          "once. `PHYLODELTA_THREADS` exists so a deployment can choose; there "
          "is no single best value.")

scaling = load("thread_scaling.json")
if scaling:
    print("\n## Table 10 — Thread scaling of the parallel step\n")
    print("**Only one step of the build is parallel**: the clade-correspondence "
          "search. It is driven directly here rather than timed through a whole "
          "build, which would dilute it with the single-threaded parse, "
          "reconciliation and metric around it. "
          f"{scaling['leaves']:,} leaves, best of {scaling['repeats']} runs.\n")
    print("| threads | time | speedup | efficiency | result identical to 1 thread |")
    print("|---:|---:|---:|---:|:--:|")
    for r in scaling["rungs"]:
        print(
            f"| {r['threads']} | {r['seconds']:.2f} s | {r['speedup']:.2f}x | "
            f"{r['efficiency']:.0%} | {'yes' if r['identical_to_single_thread'] else '**NO**'} |"
        )
    print("\n**The last column is the one that matters.** Each index's result "
          "depends only on read-only inputs, so it must be bit-identical "
          "whatever the thread count. A race here would not crash — it would "
          "quietly return a slightly wrong best corresponding node, which no "
          "timing figure would reveal.\n")
    print("The knee is at **4 threads**, which is the number of performance "
          "cores on this machine (10 cores, 4 of them performance). One to four "
          "threads buys 3.37x at 84% efficiency; four to ten buys only another "
          "1.69x and drops efficiency to 57%. On a shared machine 4 threads is "
          "the better trade: 1.7x slower than 10, for 2.5x fewer cores.")

memory = load("build_memory.json")
memory_ten = load("build_memory_10threads.json")
if memory:
    print("\n## Table 11 — What the server needs while it builds\n")
    print("Peak RSS of the worker process, sampled every 200 ms against its "
          f"idle baseline of {memory['idle_rss_mb']:,.0f} MB. Measured in a "
          "throwaway store so nothing else was disturbed.\n")
    print("**The search is quadratic in time but LINEAR in memory** — every "
          "doubling of leaves roughly doubles the footprint. The pruning bound "
          "means it never materialises an n x n matrix: it holds the two trees' "
          "columns, which are memory-mapped, and one scratch buffer per "
          "thread. For contrast, building these trees with NJ would need "
          "~500 GB of distance matrix at 500,000 taxa.\n")
    if memory_ten:
        print("Both thread settings are shown, compared on **absolute peak "
              "RSS** rather than on the over-idle delta. The two runs had "
              f"different idle baselines ({memory['idle_rss_mb']:,.0f} MB and "
              f"{memory_ten['idle_rss_mb']:,.0f} MB), so subtracting each from "
              "its own baseline would make the small rungs look like 2 threads "
              "used *more*, which is an artefact of the baseline and not a "
              "measurement.\n")
        print("**Fewer threads really does use less memory** — 30-40% less "
              "across the range, because the scratch buffer is per-thread and "
              "eight of them are not allocated. That is a larger effect than "
              "expected: the prediction was that the memory-mapped trees would "
              "dominate and the difference would be negligible. It does not, "
              "and it is not.\n")
        ten_by = {r["leaves"]: r for r in memory_ten["rungs"]}
        print("| leaves | peak RSS (2 thr) | peak RSS (10 thr) | saved | marginal (2 thr) | growth |")
        print("|---:|---:|---:|---:|---:|---:|")
        previous = None
        for row in memory["rungs"]:
            other = ten_by.get(row["leaves"])
            peak = row["peak_rss_mb"]
            marginal = row["over_idle_mb"]
            saved = f"{1 - peak / other['peak_rss_mb']:.0%}" if other else "—"
            other_peak = f"{other['peak_rss_mb']:,.0f} MB" if other else "—"
            # Growth is taken on the MARGINAL figure, not on peak RSS: peak
            # carries a fixed ~33 MB interpreter baseline that dilutes every
            # ratio and would make linear growth read as 1.65x per doubling.
            growth = f"{marginal / previous:.2f}x" if previous else "—"
            print(
                f"| {row['leaves']:,} | **{peak:,.0f} MB** | {other_peak} | "
                f"{saved} | {marginal:,.0f} MB | {growth} |"
            )
            previous = marginal or None
        print("\n*Build times are deliberately omitted from this table. This "
              "run measures memory, and its elapsed times came out well above "
              "the dedicated ladder run — 842.5 s against 492.7 s at 564,640 "
              "leaves, on the same setting — because it ran straight after a "
              "browser benchmark that had saturated the machine. Table 8's "
              "figures are the ones to quote.*")
    else:
        print("| leaves | build | peak RSS | over idle | growth |")
        print("|---:|---:|---:|---:|---:|")
        previous = None
        for r in memory["rungs"]:
            over = r["over_idle_mb"]
            growth = f"{over / previous:.2f}x" if previous else "—"
            print(
                f"| {r['leaves']:,} | {r['build_s']:.1f} s | {r['peak_rss_mb']:,.0f} MB | "
                f"**{over:,.0f} MB** | {growth} |"
            )
            previous = over or None

# --- 5e. the mechanism, directly ------------------------------------------
latency = load("slice_latency.json", [])
if latency:
    print("\n## Table 12 — The request a panel actually makes\n")
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
print("\n## Table 13 — What the design costs\n")
print("| | phylo.io | PhyloDelta |")
print("|---|---|---|")
print("| Server required | no | **yes** |")
print("| Precompute before first view | none | up to "
      f"{max((r['build_s'] for r in server.values()), default=0):.0f} s |")
print("| Whole tree ever visible | yes, in memory | **no, never transferred** |")
print("| Works offline from a file | yes | no |")
print("| Comparison recomputed on demand | yes | no, fixed at build |")

print("\n## Table 14 — Provenance of the test data\n")
print("| rung | origin |")
print("|---:|---|")
print("| 1,000 – 10,000 | pruned subsamples of the real vibrio NJ/UPGMA pair |")
print("| 17,645 | **the real pair, unmodified** |")
print("| 35,290 – 564,640 | nested relabelled copies of the real pair, preserving depth and imbalance |")
print("\n*Every rung verified as a genuine comparison pair: 100% shared leaf "
      "sets, depth 79 to 191. Real MLST data stops at 27,962 leaves "
      "(clostridium), so rungs above 17,645 are synthetic and are used only for "
      "performance claims.*")


# --- 7. navigating, once loaded -------------------------------------------
nav_rows = navigation.get("rows", [])
if nav_rows:
    print("\n## Table 15 — Navigation responsiveness, once the comparison is open\n")
    print("*Median milliseconds from the action to a painted result, "
          f"{navigation.get('samples', 8)} operations per cell after a discarded warm-up.*\n")
    print("| leaves | phylo.io expand | phylo.io back | phylo.io jump | "
          "PhyloDelta expand | PhyloDelta back | PhyloDelta jump |")
    print("|---:|---:|---:|---:|---:|---:|---:|")

    #: Rungs where phylo.io never finished computing the comparison, from the
    #: ceiling run. A tool with no comparison has nothing to navigate, and that
    #: is a different statement from "navigation was slow" — the first harness
    #: run reported it as "exceeded 900s", which reads as the second.
    no_comparison = {
        r["leaves"]
        for r in rows
        if not (r.get("phyloio", {}).get("phases") or {}).get("compareComplete")
    }

    def nav(cell, key, leaves=None, tool=None):
        if tool == "phyloio" and leaves in no_comparison:
            return "*no comparison*"
        if not cell or cell.get("ok") is False:
            return "**fails**"
        got = cell.get(key) or {}
        return fmt(got.get("median_ms"), " ms") if got.get("median_ms") is not None else "**fails**"

    for row in nav_rows:
        pi, pd = row.get("phyloio", {}), row.get("phylodelta", {})
        n = row["leaves"]
        print(f"| {n:,} | {nav(pi, 'expand', n, 'phyloio')} | {nav(pi, 'back', n, 'phyloio')} "
              f"| {nav(pi, 'jump', n, 'phyloio')} "
              f"| {nav(pd, 'expand')} | {nav(pd, 'back')} | {nav(pd, 'jump')} |")

    print("\n**\"No comparison\" is not slow navigation.** phylo.io paints both trees at 17,645 "
          "leaves but its best-corresponding-node worker never finishes there — Table 1 records "
          "`compareComplete=False` against a 600 s budget — so in compare mode there is nothing to "
          "navigate. Its navigation is therefore measurable only to **10,000 leaves**, where the "
          "comparison completes in 199 s. PhyloDelta is measured at 17,645 anyway, because holding "
          "flat is the claim.\n")
    print("*The first harness run reported that cell as \"exceeded 900s\", which reads as \"its "
          "navigation is slow\". It is not the same statement, and the distinction is the whole "
          "point of the row.*\n")
    print("**Both tools are driven one layer below the click** — phylo.io through "
          "`container.trigger_(action, …)`, which is exactly what its context-menu items call, and "
          "PhyloDelta through the actions its menu items call. Synthesising a click on a WebGL "
          "canvas would have charged hit-testing to one side only. What is excluded is the same for "
          "both: opening a menu and pressing an item.\n")
    print("**The operations are not equivalent in what they reveal.** phylo.io holds the whole tree, "
          "so it collapses and expands clades of up to 1,000 leaves and draws all of them. "
          "PhyloDelta's targets are the wedges in the current slice — 309 leaves down to 41 — and "
          "expanding one draws about fifty tips. phylo.io therefore does *more* drawing per "
          "operation at these sizes and is still faster; that is a real result and not one to "
          "explain away.\n")

    # What the cache actually contributed, and where the time goes instead.
    print("\n## Table 16 — Where a PhyloDelta navigation's time goes\n")
    print("| leaves | expand total | of which fetch | back total | of which fetch | "
          "back, cache emptied | of which fetch |")
    print("|---:|---:|---:|---:|---:|---:|---:|")
    for row in nav_rows:
        pd = row.get("phylodelta", {})
        if not pd.get("ok"):
            continue
        f = pd.get("fetch_ms", {})
        cold = pd.get("uncached", {})
        def med(o):
            return fmt((o or {}).get("median_ms"), " ms")
        print(f"| {row['leaves']:,} | {med(pd.get('expand'))} | {med(f.get('expand'))} "
              f"| {med(pd.get('back'))} | {med(f.get('back'))} "
              f"| {med(cold.get('back'))} | {med(f.get('cold_back'))} |")
    print("\n*Cached and uncached are interleaved in one page against the same target, because "
          "measuring them in separate browsers reported the uncached run as three times FASTER — "
          "the first run was paying for a cold server and the second inherited a warm one. The "
          "uncached pass runs first, so any residual warming works against the cache.*\n")
    print("**The cache works and it barely matters.** On a hit the network cost of a navigation is "
          "**0 ms**, which is the cache doing exactly its job — and the navigation takes the same "
          "total time, because the round trip was never the cost. Roughly 42 ms of a ~49 ms "
          "navigation is building the tree and drawing it. Every headline figure in Tables 1–14 was "
          "measured with no caching at all, so they are a floor rather than a best case.\n")

    # phylo.io's jump does not survive compare mode.
    broken = [r for r in nav_rows
              if (r.get("phyloio", {}).get("failure_count") or 0) > 0]
    if broken:
        first = broken[0]["phyloio"]["failures"][0]
        print("\n### Table 15 note — phylo.io's \"Highlight BCN\" throws in compare mode\n")
        print("Every attempt failed, at every rung, with the same error:\n")
        print(f"> `{first.get('error')}`\n")
        print("It is reached only from the context-menu item of that name "
              "(`viewer.js` line 1175 is the sole caller), with the arguments used here, in "
              "phylo.io 2.1.1. The cause is in `api.js`: the BCN worker's reply is used to build "
              "**two separate models**, and the `elementBCN` references inside the first reply point "
              "at that reply's own embedded copy of the second tree rather than at the model built "
              "from it. `getHierarchyNodeFromModelNode` compares by object identity, finds nothing, "
              "returns null, and `expandToRoot` passes that null to "
              "`apply_collapse_from_data_to_d3`, which reads `_children` on it. The targets are "
              "parentless, which is the visible symptom of being detached.\n")
        print("Recorded with the mechanism because it is a claim about someone else's tool. It also "
              "sharpens the comparison rather than softening it: the cross-tree jump is the "
              "operation PhyloDelta's design is most open to criticism over — it costs an "
              "`/ancestor` call and a slice the panel has never held — and it is the one the "
              "comparison tool cannot complete at all.\n")


# --- 8. does the metric change the cost? ----------------------------------
phase_rows = metric_phases.get("rows", [])
if phase_rows:
    print("\n\n## Table 17 — Does the chosen metric change what a build costs?\n")
    print("*Seconds, from the worker's own per-metric timings at "
          "`PHYLODELTA_THREADS=2`. \"Shared\" is what every metric in a set pays "
          "once: parse, reconcile, correspondence, store.*\n")
    print("| leaves | shared work | rf | rf-treediff | triplet | total | metrics as % of total |")
    print("|---:|---:|---:|---:|---:|---:|---:|")

    def secs(value):
        # `is not None`, not truthiness: a real 0.0 s must not print as "—".
        return f"{value:,.1f} s" if value is not None else "—"

    for row in phase_rows:
        widest = max(row["builds"], key=lambda b: len(b["metrics"]))
        per = widest.get("per_metric", {})

        def one(name):
            got = per.get(name)
            if got is None:
                return "—"
            return "**refused**" if "failed" in got else secs(got.get("seconds"))

        shared = widest.get("shared_s")
        total = widest.get("total_s")
        metric_sum = sum(
            g["seconds"] for g in per.values() if isinstance(g, dict) and "seconds" in g
        )
        # The log resolves to 0.1 s, so a share computed from a sub-second build
        # is quantisation, not a measurement: it printed "100%" at 2,500 leaves
        # and "0%" at 1,000. Suppressed rather than shown as a number.
        share = f"{metric_sum / total * 100:.0f}%" if total and total >= 1.0 else "*n/a*"
        print(f"| {row['leaves']:,} | {secs(shared)} | {one('rf')} | {one('rf-treediff')} "
              f"| {one('triplet')} | {secs(total)} | {share} |")

    top = max(phase_rows, key=lambda r: r["leaves"])
    top_widest = max(top["builds"], key=lambda b: len(b["metrics"]))
    top_per = top_widest.get("per_metric", {})
    cheap = sum(
        top_per[m]["seconds"] for m in ("rf", "rf-treediff")
        if isinstance(top_per.get(m), dict) and "seconds" in top_per[m]
    )
    trip = (top_per.get("triplet") or {}).get("seconds")
    top_total = top_widest.get("total_s") or 0
    trip_share = f"{trip / top_total * 100:.0f}%" if trip and top_total else "—"
    print(f"\n**The answer reverses with size, so \"does the metric matter\" has no single "
          f"answer.** `rf` and `rf-treediff` are free at every scale — together {cheap:,.1f} s of a "
          f"{top_total:,.0f} s build at {top['leaves']:,} leaves. `triplet` is not: at 141,160 it "
          f"costs 12.3 s against 14.8 s for all the shared work, very nearly doubling the build. By "
          f"{top['leaves']:,} `triplet` alone has fallen back to {trip_share} of the build (the "
          f"table's last column counts all three metrics together), because the shared work is "
          f"O(n^2) and the metric is near-linear, so correspondence overtakes it.\n")
    print("So §9's claim that several metrics cost little more than one is **true "
          "asymptotically and misleading in the middle** — which is where most real trees sit. "
          "The claim should be stated about the *shared* work, which is what is actually shared, "
          "rather than about metrics in general.\n")
    print("**Measured from the worker's log, not from wall-clock differences.** The three metric "
          "sets are uploaded in a fixed order, so the \"+triplet\" build is always last, and the "
          "first pass showed it at a suspiciously uniform 1.7-2x the others — the shape of an "
          "ordering artefact rather than a cost. Per-metric timings carry no such confound.\n")
    print("*Absolute shared-work times in this table come from a single freshly-built store in "
          "one sitting and run lower than Table 9's for the same rung (256 s against 493 s at "
          "564,640). That is the store-dependent variance already recorded in §34.9 and §34.11, "
          "not a change in the code. What this table is for is the ratio within each row, which is "
          "internally consistent.*\n")

    # The cross-check, which matters more than either timing.
    build_rows = metric_builds.get("rows", [])
    agree, disagree = [], []
    for row in build_rows:
        for build in row["builds"]:
            values = build.get("values", {})
            a = (values.get("rf") or {}).get("summary", {}).get("rf")
            b = (values.get("rf-treediff") or {}).get("summary", {}).get("rf")
            if a is None or b is None:
                continue
            (agree if a == b else disagree).append((row["leaves"], a, b))
    if agree or disagree:
        print("\n## Table 18 — Two RF implementations against each other\n")
        print("| leaves | built-in `rf` | `rf-treediff` | agree |")
        print("|---:|---:|---:|:---:|")
        seen = set()
        for leaves, a, b in agree + disagree:
            if leaves in seen:
                continue
            seen.add(leaves)
            print(f"| {leaves:,} | {a:,.0f} | {b:,.0f} | {'yes' if a == b else '**NO**'} |")
        print(f"\n*{len(agree)} of {len(agree) + len(disagree)} builds agree exactly.* "
              "Different algorithms over different representations by different authors — "
              "TreeDiff is the reference implementation of the paper this project follows (§1.10) "
              "— so agreement at 1,129,279 nodes is a check on both, and a disagreement would "
              "have meant one of them was wrong.\n")

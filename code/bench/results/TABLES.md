# PhyloDelta vs Phylo.io — measured comparison

## Environment

| | |
|---|---|
| Machine | Apple M4 laptop — **4 performance + 6 efficiency cores**, 24 GB |
| OS | macOS 27.0 (build 26A428, Darwin 27.0.0) |
| Browser | Chrome 154.0.8037.58, **headless**, system Chrome via Playwright's `channel: "chrome"` |
| Browser flags | `--js-flags=--max-old-space-size=8192`, `--disable-dev-shm-usage` — **both tools, identically** |
| Viewport | 1440 x 900; Table 21 varies the height |
| **Tool compared against** | **phylo.io 2.1.1**, its own prebuilt `dist/`, unmodified |
| This project | commit `7409ab8 + uncommitted changes` |
| Runtimes | Python 3.12.14 (`uv`), Node 26.3.0, Playwright 1.63.0 |
| Backend database | SQLite, in the store directory |
| Store location | `/private/tmp/...` — an APFS SSD volume, **not** a RAM disk |
| **Backend threads** | **2 of the 10 cores** (`PHYLODELTA_THREADS=2`) |
| Transport | one origin, one fresh page per measurement; uncompressed except Table 20, which is gzip |
| Power state | **not controlled** — see the caveat below |

**The two entries that matter most for checking these numbers** are the browser flags and the phylo.io version. The heap cap decides *where* a tool fails, so Table 1's and Table 4's `failed` rows are statements about the tool at an 8 GB cap, not at Chrome's default — and it is raised for both tools, which is what makes a failure the tool's own ceiling. The version matters because several findings are about phylo.io's behaviour: the "Highlight BCN" crash (Table 15) is a fact about **2.1.1** and a later release may fix it.

**Headless, throughout.** Rendering in headless Chrome is not identical to a visible window, and these are partly rendering measurements — so this is a real caveat, not a footnote. It applies equally to both tools, so the *comparison* holds; the absolute paint times would need re-taking in a headed browser to be quoted as what a user sees.

**Power state was not controlled or recorded**, and the machine is a laptop that throttles on battery. This is worth stating plainly because the explanation already offered for the 564,640-leaf thread-scaling anomaly (§34.9, §34.11) is machine state — thermal drift over a 20-minute run — and having invoked that, the table cannot then be silent about power. Repeats under a known power state are the cheapest way to close it.

**Only 2 of the 10 cores are used for the backend**, deliberately. Table 9 is the measurement behind that choice: two threads give ~2x at 94% efficiency where ten give ~4.7x at 57%, so eight further cores buy the last 2.3x at a steeply falling rate. Every build figure in these tables is therefore what a **two-core** deployment costs, not what this machine can do flat out.

## Which of these to present

Eighteen tables is more than a chapter can carry, and most were made to answer a question that came up rather than to make an argument. Each heading below repeats its tier.

**Present these** — The argument. Drop one and a claim goes unsupported.

- **Table 1** — The headline. Where each tool stops, and the size claim.
- **Table 2** — The caveat Table 1 cannot be read without: this design draws less, and that IS the design. Omitting it is how the earlier 34x mistake happened.
- **Table 3** — Memory is half the claim — flat against growing.
- **Table 5** — Correctness. A fast wrong answer is worth nothing, so the approximation's cost has to be stated.
- **Table 8** — What the design costs. Presenting Table 1 without this is claiming the precompute is free.
- **Table 12** — The mechanism itself — a payload sized to the viewport, flat at every tree size. This is the thesis in one table.
- **Table 13** — The honest ledger. What was given up to get Table 1.
- **Table 14** — Methodology. The rungs above 17,645 are synthetic and the thesis must say so where the numbers are.
- **Table 15** — The other half of interaction: loading is not using. Also carries the finding that the comparison tool's cross-tree jump does not work at all.
- **Table 19** — The claim as the quantity it is actually about: bytes over the wire. Present it beside Table 12 — 12 is the mechanism, 19 is what the mechanism buys.
- **Table 21** — The other half of "sized to the viewport". Every other table shows the payload ignoring the tree; only this one shows it following the window, which is what earns the word *sized*.

**Appendix, or one sentence citing the number** — Defends a choice or a stated limit of a PRESENT table.

- **Table 4** — The detail behind Table 1's 'failed': what failed and how. Cite the 30-minute budget in the text.
- **Table 9** — Justifies the 2-thread setting every build figure uses. One sentence plus the table in an appendix.
- **Table 11** — The deployability argument: server memory is linear, not quadratic. A sentence with the marginal figure.
- **Table 17** — Why the metric choice is not free, and where §9's claim holds. Relevant only if the thesis discusses metric plugins.
- **Table 18** — Validation: two independent RF implementations agreeing at 1.1M nodes. A sentence, with the table in an appendix.
- **Table 20** — Table 19 under compression, which is what a real deployment serves. Answers the first objection anyone will raise to 19, and answers it the other way from the expected one.

**Keep in the repository, do not present** — Real and reproducible, but a PRESENT table already says it or it answered an internal question.

- **Table 6** — Diagnostic. Phase-splitting another tool's time compares phase names that do not mean the same thing; Table 1's paint/compare split is the part that survives.
- **Table 7** — A method note, not a result: it establishes that one sample per rung was enough. Belongs in a sentence about method.
- **Table 10** — Subsumed by Table 9, which measures the same trade-off on whole builds rather than one step.
- **Table 16** — The attribution behind Table 15 — the round trip is ~6 ms of a ~49 ms navigation. One sentence, not a table.

The PRESENT tables answer, in this order: how far each tool gets (1), on comparable work (2), at what memory (3), sending how many bytes (19), sized by what (21), how correctly (5), by what mechanism (12), at what navigation cost (15), for what precompute (8), giving up what (13), measured on what data (14).

*If only one table can be shown, it is 19.* It states the claim in the quantity the claim is about — 28.9 KB against 35.5 MB at 564,640 leaves — and it is the only table whose ratio grows without bound while everything on this side stays flat.

*Two tables to read together, not separately:* Table 1 without Table 2 overstates the result, because the tools do not draw the same amount — that asymmetry IS the design, and hiding it is how an earlier version of this comparison reported a 34x that did not exist.

---

## Table 1 — Scalability: where each tool stops

<!-- tier: PRESENT -->
> **PRESENT** — The headline. Where each tool stops, and the size claim.

> **Heap here is MAIN-THREAD ONLY.** `Runtime.getHeapUsage` reads one isolate, and phylo.io computes its comparison in a **Web Worker** with a heap of its own. Where the comparison finishes, the worker's results are copied back and the figure reflects them; where it does not, the column shows only the two parsed trees and so *falls* as the tree grows. It is a lower bound, not the tool's memory. Table 4's RSS figures, which cover the whole renderer including workers, are the honest memory numbers.

Cold start to an interactive comparison. Phylo.io is split into *paint* (two trees drawn) and *compare* (its best-corresponding-node worker finished), because only the second is the same job PhyloDelta is doing: a slice arrives with its similarity values already in it.

| leaves | phylo.io paint | phylo.io compare | phylo.io main-thread heap | PhyloDelta | PhyloDelta heap | PhyloDelta advantage | server precompute |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 1,000 | 0.4 s | 5 s | 27.4 MB | 0.29 s | 3.6 MB | **17x** | 0.5 s |
| 2,500 | 0.9 s | 19 s | 100.2 MB | 0.24 s | 3.6 MB | **78x** | 2.0 s |
| 5,000 | 1.9 s | 53 s | 291.1 MB | 0.19 s | 3.6 MB | **272x** | 2.6 s |
| 10,000 | 4.4 s | 199 s | 1,181.4 MB | 0.20 s | 3.6 MB | **1,002x** | 2.0 s |
| 17,645 | 9.3 s | **did not finish** | 58.7 MB | 0.20 s | 3.6 MB | — | 3.1 s |
| 35,290 | 25.1 s | **did not finish** | 115.6 MB | 0.19 s | 3.7 MB | — | 4.6 s |
| 70,580 | **failed** | **failed** | **failed** | 0.57 s | 3.6 MB | **only PhyloDelta** | 10.2 s |
| 141,160 | **failed** | **failed** | **failed** | 0.34 s | 3.6 MB | **only PhyloDelta** | 31.5 s |
| 282,320 | **failed** | **failed** | **failed** | 0.94 s | 3.6 MB | **only PhyloDelta** | 115.1 s |
| 564,640 | **failed** | **failed** | **failed** | 0.75 s | 3.6 MB | **only PhyloDelta** | 492.7 s |

## Table 2 — What each tool actually drew

<!-- tier: PRESENT -->
> **PRESENT** — The caveat Table 1 cannot be read without: this design draws less, and that IS the design. Omitting it is how the earlier 34x mistake happened.

The check that makes Table 1 admissible. An earlier comparison in this project reported a ~34x speedup that was an artefact of the two tools rendering 91 and 2,002 nodes. **Both tools draw a roughly constant amount** — so the difference in Table 1 is not "one of them drew less".

> Rows from 17,645 up show phylo.io's **pre-comparison** render only: when the worker finishes it rebuilds and redraws both panels with the similarity colouring, and where it never finishes that second render never happens. That is why the counts fall rather than rise. The point of the table is unaffected — the counts are flat or falling in every case, never proportional to the tree.

| leaves | phylo.io SVG paths | phylo.io DOM nodes | PhyloDelta canvases | PhyloDelta tips drawn |
|---:|---:|---:|---:|---|
| 1,000 | 918 | 8,908 | 14 | 50 per panel |
| 2,500 | 1126 | 9,662 | 14 | 50 per panel |
| 5,000 | 1166 | 9,836 | 14 | 50 per panel |
| 10,000 | 1254 | 10,166 | 14 | 50 per panel |
| 17,645 | 670 | 6,921 | 14 | 50 per panel |
| 35,290 | 640 | 6,506 | 14 | 50 per panel |
| 70,580 | failed | failed | 14 | 50 per panel |
| 141,160 | failed | failed | 14 | 50 per panel |
| 282,320 | failed | failed | 14 | 50 per panel |
| 564,640 | failed | failed | 14 | 50 per panel |

## Table 3 — Memory, and why it grows for one tool and not the other

<!-- tier: PRESENT -->
> **PRESENT** — Memory is half the claim — flat against growing.

Phylo.io's DOM is flat while its heap climbs steeply: it **models the whole tree** in the browser, and on top of that holds MinHash sketches and a score per node, which scale with the *comparison* rather than with the tree. PhyloDelta never receives the tree at all.

Rows where the comparison did not finish are marked — their figure excludes the worker entirely and must not be read as a decrease.

| leaves | phylo.io main-thread heap | growth vs previous | PhyloDelta heap |
|---:|---:|---:|---:|
| 1,000 | 27.4 MB | — | 3.6 MB |
| 2,500 | 100.2 MB | 3.66x | 3.6 MB |
| 5,000 | 291.1 MB | 2.91x | 3.6 MB |
| 10,000 | 1,181.4 MB | 4.06x | 3.6 MB |
| 17,645 | 58.7 MB *(compare unfinished — worker excluded)* | — | 3.6 MB |
| 35,290 | 115.6 MB *(compare unfinished — worker excluded)* | — | 3.7 MB |
| 70,580 | — *(compare unfinished — worker excluded)* | — | 3.6 MB |
| 141,160 | — *(compare unfinished — worker excluded)* | — | 3.6 MB |
| 282,320 | — *(compare unfinished — worker excluded)* | — | 3.6 MB |
| 564,640 | — *(compare unfinished — worker excluded)* | — | 3.6 MB |

## Table 4 — Failure behaviour, given 30 minutes and 16 GB

<!-- tier: SUPPORT -->
> **SUPPORT** — The detail behind Table 1's 'failed': what failed and how. Cite the 30-minute budget in the text.

Table 1's failures are against a stated budget. This removes the budget: each rung was given **30 minutes** with a 16 GB renderer cap on a 24 GB machine.

| leaves | outcome | time to failure | peak renderer |
|---:|---|---:|---:|
| 141,160 | **renderer process crashed** | 17.1 min | 10,722 MB |
| 282,320 | **renderer process crashed** | 25.6 min | 9,690 MB |

*Peak memory is sampled every 2 s from process RSS, so it is a lower bound and the two figures should not be read as an ordering.*

## Table 5 — Accuracy: what the LSH approximation costs

<!-- tier: PRESENT -->
> **PRESENT** — Correctness. A fast wrong answer is worth nothing, so the approximation's cost has to be stated.

Phylo.io finds each clade's best corresponding node by maximising Jaccard over **ten candidates** retrieved by MinHash/LSH (`worker_bcn.js`). This project maximises over every node, so it is an upper bound and every gap is a retrieval miss. Run on pairs with **identical leaf sets**, so a difference cannot be explained by unmatched-leaf handling.

| leaves | clades | exact match | missed | median gap | worst gap | beat exact |
|---:|---:|---:|---:|---:|---:|---:|
| 1000 | 998 | 969 (97.1%) | 29 (2.9%) | 0.108 | 0.333 | 0 |
| 2500 | 2,498 | 2,356 (94.3%) | 142 (5.7%) | 0.094 | 0.838 | 0 |
| 5000 | 4,994 | 4,765 (95.4%) | 229 (4.6%) | 0.103 | 0.640 | 0 |

*`beat exact` must be 0: an exhaustive search cannot be beaten by a subset of the same candidates. It is reported as a check on the method, not as a result.*

## Table 6 — Where phylo.io's time goes

<!-- tier: WORKING -->
> **WORKING** — Diagnostic. Phase-splitting another tool's time compares phase names that do not mean the same thing; Table 1's paint/compare split is the part that survives.

Its own phase split. Parsing and drawing are cheap and near-linear; **the comparison is what scales badly** — which is the same finding as this project's own correspondence search being the quadratic step (DECISIONS §17), reached independently by both implementations.

| leaves | parse | layout | paint | compare | compare as % of total |
|---:|---:|---:|---:|---:|---:|
| 1,000 | 0.02 s | 0.18 s | 0.18 s | 5 s | 93% |
| 2,500 | 0.04 s | 0.41 s | 0.46 s | 19 s | 95% |
| 5,000 | 0.09 s | 0.94 s | 0.92 s | 53 s | 96% |
| 10,000 | 0.22 s | 2.32 s | 1.85 s | 199 s | 98% |
| 17,645 | 0.49 s | 5.30 s | 3.50 s | **>600 s** | — |
| 35,290 | 0.93 s | 16.91 s | 7.24 s | **>600 s** | — |
| 70,580 | — | — | — | **failed** | — |
| 141,160 | — | — | — | **failed** | — |
| 282,320 | — | — | — | **failed** | — |
| 564,640 | — | — | — | **failed** | — |

## Table 7 — PhyloDelta, repeated

<!-- tier: WORKING -->
> **WORKING** — A method note, not a result: it establishes that one sample per rung was enough. Belongs in a sentence about method.

Six samples per rung after a discarded warm-up. Included because sub-second figures are at this harness's noise floor: a single sample per rung first reported 2.7 s and 3.6 s at the top two rungs, which no repeat could reproduce.

| leaves | nodes | median | min | max | heap |
|---:|---:|---:|---:|---:|---:|
| 1,000 | 1,999 | **0.62 s** | 0.48 s | 2.46 s | 3.6 MB |
| 2,500 | 4,999 | **0.52 s** | 0.48 s | 2.69 s | 3.6 MB |
| 5,000 | 9,999 | **0.61 s** | 0.45 s | 2.46 s | 3.6 MB |
| 10,000 | 19,999 | **0.58 s** | 0.46 s | 1.61 s | 3.6 MB |
| 17,645 | 35,289 | **0.61 s** | 0.47 s | 1.06 s | 3.6 MB |
| 35,290 | 70,579 | **0.58 s** | 0.44 s | 0.73 s | 3.6 MB |
| 70,580 | 141,159 | **0.59 s** | 0.42 s | 0.89 s | 3.6 MB |
| 141,160 | 282,319 | **0.66 s** | 0.42 s | 2.16 s | 3.6 MB |
| 282,320 | 564,639 | **0.53 s** | 0.44 s | 2.35 s | 3.6 MB *(beyond phylo.io — it crashes at 141,160)* |
| 564,640 | 1,129,279 | **0.43 s** | 0.38 s | 0.97 s | 3.6 MB *(beyond phylo.io — it crashes at 141,160)* |

## Table 8 — The precompute PhyloDelta pays instead

<!-- tier: PRESENT -->
> **PRESENT** — What the design costs. Presenting Table 1 without this is claiming the precompute is free.

Measured through the real upload path: POST the bundle, a worker claims it, poll until ready. Includes ingest, reconciliation, the correspondence search and the metric.

**At 2 threads**, the deployment setting (see Environment and Table 9). The 10-thread column is kept because the first runs used the default, and because the gap is the cost of the choice.

| leaves | build at 2 threads | build at 10 threads | bundle size |
|---:|---:|---:|---:|
| 1,000 | **0.5 s** | 2.0 s | 0.0 MB |
| 2,500 | **2.0 s** | 2.0 s | 0.0 MB |
| 5,000 | **2.6 s** | 2.0 s | 0.1 MB |
| 10,000 | **2.0 s** | 2.5 s | 0.2 MB |
| 17,645 | **3.1 s** | 2.6 s | 1.1 MB |
| 35,290 | **4.6 s** | 3.0 s | 2.1 MB |
| 70,580 | **10.2 s** | 5.6 s | 4.2 MB |
| 141,160 | **31.5 s** | 14.4 s | 8.6 MB |
| 282,320 | **115.1 s** | 49.8 s | 17.5 MB |
| 564,640 | **492.7 s** | 339.5 s | 35.5 MB |

*The ~2 s floor at small sizes is the worker's poll interval, not work.*

## Table 9 — Build time at pinned thread counts

<!-- tier: SUPPORT -->
> **SUPPORT** — Justifies the 2-thread setting every build figure uses. One sentence plus the table in an appendix.

Table 8 used the default — one thread per hardware thread, **10** on this machine. These are the same builds with the count pinned, through the same upload path, each on its own store.

| leaves | 1 thread | 2 threads | 10 threads | 2 vs 1 | 10 vs 1 |
|---:|---:|---:|---:|---:|---:|
| 1,000 *(floor-limited — ratios are noise)* | 2.1 s | 0.5 s | 2.0 s | 3.81x | 1.02x |
| 2,500 *(floor-limited — ratios are noise)* | 2.1 s | 2.0 s | 2.0 s | 1.01x | 1.01x |
| 5,000 *(floor-limited — ratios are noise)* | 2.0 s | 2.6 s | 2.0 s | 0.80x | 1.01x |
| 10,000 *(floor-limited — ratios are noise)* | 2.5 s | 2.0 s | 2.5 s | 1.25x | 1.00x |
| 17,645 *(floor-limited — ratios are noise)* | 3.1 s | 3.1 s | 2.6 s | 1.00x | 1.19x |
| 35,290 | 6.1 s | 4.6 s | 3.0 s | 1.33x | 2.00x |
| 70,580 | 16.7 s | 10.2 s | 5.6 s | 1.65x | 2.98x |
| 141,160 | 57.8 s | 31.5 s | 14.4 s | 1.84x | 4.03x |
| 282,320 | 231.7 s | 115.1 s | 49.8 s | 2.01x | 4.65x |
| 564,640 *(see note)* | 1200.7 s | 492.7 s | 339.5 s | 2.44x | 3.54x |

**Read the middle rows.** From 35,290 to 282,320 the picture is clean and monotone: two threads rise 1.33x -> 2.01x, ten rise 2.00x -> 4.65x. The gain grows with size because below ~70,000 leaves the *serial* parts — parse, reconcile, ingest, and the 2 s poll — are most of the elapsed time, and threading the search cannot touch them. Amdahl's law, visible directly.

**The 564,640 row should not be quoted as a ratio.** Two threads appear to give 2.44x, which is superlinear and therefore impossible for pure parallelism, and ten threads appear to *fall* to 3.54x, breaking an otherwise monotone trend. Both point at the machine rather than the code: the single-threaded run took **20 minutes**, long enough for thermal state to drift, and this rung's 10-thread baseline is the disputed one (339.5 s here, 196.4 s in another store — see DECISIONS §34.8). Against 196.4 s the 10-thread gain is 6.11x and the trend continues. The absolute times stand; the ratios for this row do not.

**What to choose.** Two threads gives ~2x at 94% efficiency; ten gives ~4.7x at 57%. One thread wastes a near-free doubling. If efficiency is the objective, **two is the sweet spot** — but latency for a single comparison favours more threads, and throughput for a queue favours fewer per build with more builds at once. `PHYLODELTA_THREADS` exists so a deployment can choose; there is no single best value.

## Table 10 — Thread scaling of the parallel step

<!-- tier: WORKING -->
> **WORKING** — Subsumed by Table 9, which measures the same trade-off on whole builds rather than one step.

**Only one step of the build is parallel**: the clade-correspondence search. It is driven directly here rather than timed through a whole build, which would dilute it with the single-threaded parse, reconciliation and metric around it. 70,580 leaves, best of 3 runs.

| threads | time | speedup | efficiency | result identical to 1 thread |
|---:|---:|---:|---:|:--:|
| 1 | 13.20 s | 1.00x | 100% | yes |
| 2 | 7.04 s | 1.88x | 94% | yes |
| 3 | 5.01 s | 2.64x | 88% | yes |
| 4 | 3.92 s | 3.37x | 84% | yes |
| 6 | 3.03 s | 4.35x | 73% | yes |
| 8 | 2.56 s | 5.15x | 64% | yes |
| 10 | 2.31 s | 5.71x | 57% | yes |

**The last column is the one that matters.** Each index's result depends only on read-only inputs, so it must be bit-identical whatever the thread count. A race here would not crash — it would quietly return a slightly wrong best corresponding node, which no timing figure would reveal.

The knee is at **4 threads**, which is the number of performance cores on this machine (10 cores, 4 of them performance). One to four threads buys 3.37x at 84% efficiency; four to ten buys only another 1.69x and drops efficiency to 57%. On a shared machine 4 threads is the better trade: 1.7x slower than 10, for 2.5x fewer cores.

## Table 11 — What the server needs while it builds

<!-- tier: SUPPORT -->
> **SUPPORT** — The deployability argument: server memory is linear, not quadratic. A sentence with the marginal figure.

Peak RSS of the worker process, sampled every 200 ms against its idle baseline of 33 MB. Measured in a throwaway store so nothing else was disturbed.

**The search is quadratic in time but LINEAR in memory** — every doubling of leaves roughly doubles the footprint. The pruning bound means it never materialises an n x n matrix: it holds the two trees' columns, which are memory-mapped, and one scratch buffer per thread. For contrast, building these trees with NJ would need ~500 GB of distance matrix at 500,000 taxa.

Both thread settings are shown, compared on **absolute peak RSS** rather than on the over-idle delta. The two runs had different idle baselines (33 MB and 69 MB), so subtracting each from its own baseline would make the small rungs look like 2 threads used *more*, which is an artefact of the baseline and not a measurement.

**Fewer threads really does use less memory** — 30-40% less across the range, because the scratch buffer is per-thread and eight of them are not allocated. That is a larger effect than expected: the prediction was that the memory-mapped trees would dominate and the difference would be negligible. It does not, and it is not.

| leaves | peak RSS (2 thr) | peak RSS (10 thr) | saved | marginal (2 thr) | growth |
|---:|---:|---:|---:|---:|---:|
| 1,000 | **43 MB** | 73 MB | 41% | 10 MB | — |
| 2,500 | **50 MB** | 76 MB | 34% | 17 MB | 1.69x |
| 5,000 | **52 MB** | 80 MB | 34% | 20 MB | 1.13x |
| 10,000 | **60 MB** | 87 MB | 31% | 27 MB | 1.40x |
| 17,645 | **76 MB** | 106 MB | 28% | 44 MB | 1.61x |
| 35,290 | **101 MB** | 148 MB | 32% | 68 MB | 1.55x |
| 70,580 | **166 MB** | 223 MB | 25% | 134 MB | 1.96x |
| 141,160 | **276 MB** | 392 MB | 29% | 244 MB | 1.82x |
| 282,320 | **470 MB** | 681 MB | 31% | 438 MB | 1.80x |
| 564,640 | **776 MB** | 1,271 MB | 39% | 743 MB | 1.70x |

*Build times are deliberately omitted from this table. This run measures memory, and its elapsed times came out well above the dedicated ladder run — 842.5 s against 492.7 s at 564,640 leaves, on the same setting — because it ran straight after a browser benchmark that had saturated the machine. Table 8's figures are the ones to quote.*

## Table 12 — The request a panel actually makes

<!-- tier: PRESENT -->
> **PRESENT** — The mechanism itself — a payload sized to the viewport, flat at every tree size. This is the thesis in one table.

The **cause**, where every other table shows the consequence. The same GET the frontend issues, at every tree size, read-only. Latency and payload are set by the viewport budget, so neither tracks the tree: **564x more leaves, the same few milliseconds and the same few kilobytes.**

| leaves | median | min | max | response | leaves drawn |
|---:|---:|---:|---:|---:|---:|
| 1,000 | **3.8 ms** | 3.1 ms | 8.5 ms | 5.4 KB | 50 |
| 2,500 | **3.0 ms** | 2.8 ms | 11.6 ms | 5.5 KB | 50 |
| 5,000 | **2.9 ms** | 2.9 ms | 3.2 ms | 5.6 KB | 50 |
| 10,000 | **2.8 ms** | 2.7 ms | 2.9 ms | 5.6 KB | 50 |
| 17,645 | **3.2 ms** | 3.0 ms | 3.9 ms | 6.9 KB | 50 |
| 35,290 | **3.1 ms** | 2.9 ms | 3.3 ms | 6.9 KB | 50 |
| 70,580 | **2.9 ms** | 2.7 ms | 3.4 ms | 6.8 KB | 50 |
| 141,160 | **3.2 ms** | 2.9 ms | 34.7 ms | 6.7 KB | 50 |
| 282,320 | **3.2 ms** | 3.0 ms | 3.4 ms | 6.5 KB | 50 |
| 564,640 | **2.9 ms** | 2.9 ms | 3.0 ms | 6.0 KB | 50 |

*From 1,000 to 564,640 leaves — a 565x increase — the median moves 3.8 ms to 2.9 ms and the payload 5.4 KB to 6.0 KB. Seven samples per rung after a warm-up, since the first touch of a store memory-maps it.*

## Table 13 — What the design costs

<!-- tier: PRESENT -->
> **PRESENT** — The honest ledger. What was given up to get Table 1.

| | phylo.io | PhyloDelta |
|---|---|---|
| Server required | no | **yes** |
| Precompute before first view | none | up to 493 s at 2 threads |
| Whole tree ever visible | yes, in memory | **no, never transferred** |
| Works offline from a file | yes | no |
| Comparison recomputed on demand | yes | no, fixed at build |

## Table 14 — Provenance of the test data

<!-- tier: PRESENT -->
> **PRESENT** — Methodology. The rungs above 17,645 are synthetic and the thesis must say so where the numbers are.

| rung | origin |
|---:|---|
| 1,000 – 10,000 | pruned subsamples of the real vibrio NJ/UPGMA pair |
| 17,645 | **the real pair, unmodified** |
| 35,290 – 564,640 | nested relabelled copies of the real pair, preserving depth and imbalance |

*Every rung verified as a genuine comparison pair: 100% shared leaf sets, depth 79 to 191. Real MLST data stops at 27,962 leaves (clostridium), so rungs above 17,645 are synthetic and are used only for performance claims.*

## Table 15 — Navigation responsiveness, once the comparison is open

<!-- tier: PRESENT -->
> **PRESENT** — The other half of interaction: loading is not using. Also carries the finding that the comparison tool's cross-tree jump does not work at all.

*Median milliseconds from the action to a painted result, 8 operations per cell after a discarded warm-up.*

| leaves | phylo.io expand | phylo.io back | phylo.io jump | PhyloDelta expand | PhyloDelta back | PhyloDelta jump |
|---:|---:|---:|---:|---:|---:|---:|
| 1,000 | 30.9 ms | 31.3 ms | **fails** | 49.6 ms | 49.0 ms | 47.6 ms |
| 2,500 | 31.1 ms | 31.1 ms | **fails** | 49.2 ms | 49.3 ms | 49.3 ms |
| 5,000 | 31.5 ms | 32.1 ms | **fails** | 49.2 ms | 49.3 ms | 49.8 ms |
| 10,000 | 31.5 ms | 31.6 ms | **fails** | 49.3 ms | 49.2 ms | 49.3 ms |
| 17,645 | *no comparison* | *no comparison* | *no comparison* | 49.2 ms | 49.3 ms | 49.3 ms |

**"No comparison" is not slow navigation.** phylo.io paints both trees at 17,645 leaves but its best-corresponding-node worker never finishes there — Table 1 records `compareComplete=False` against a 600 s budget — so in compare mode there is nothing to navigate. Its navigation is therefore measurable only to **10,000 leaves**, where the comparison completes in 199 s. PhyloDelta is measured at 17,645 anyway, because holding flat is the claim.

*The first harness run reported that cell as "exceeded 900s", which reads as "its navigation is slow". It is not the same statement, and the distinction is the whole point of the row.*

**Both tools are driven one layer below the click** — phylo.io through `container.trigger_(action, …)`, which is exactly what its context-menu items call, and PhyloDelta through the actions its menu items call. Synthesising a click on a WebGL canvas would have charged hit-testing to one side only. What is excluded is the same for both: opening a menu and pressing an item.

**The operations are not equivalent in what they reveal.** phylo.io holds the whole tree, so it collapses and expands clades of up to 1,000 leaves and draws all of them. PhyloDelta's targets are the wedges in the current slice — 309 leaves down to 41 — and expanding one draws about fifty tips. phylo.io therefore does *more* drawing per operation at these sizes and is still faster; that is a real result and not one to explain away.


## Table 16 — Where a PhyloDelta navigation's time goes

<!-- tier: WORKING -->
> **WORKING** — The attribution behind Table 15 — the round trip is ~6 ms of a ~49 ms navigation. One sentence, not a table.

| leaves | expand total | of which fetch | back total | of which fetch | back, cache emptied | of which fetch |
|---:|---:|---:|---:|---:|---:|---:|
| 1,000 | 49.6 ms | 6.8 ms | 49.0 ms | 0.0 ms | 48.8 ms | 7.8 ms |
| 2,500 | 49.2 ms | 8.1 ms | 49.3 ms | 0.0 ms | 48.9 ms | 8.4 ms |
| 5,000 | 49.2 ms | 8.1 ms | 49.3 ms | 0.0 ms | 47.7 ms | 7.9 ms |
| 10,000 | 49.3 ms | 7.8 ms | 49.2 ms | 0.0 ms | 49.1 ms | 8.1 ms |
| 17,645 | 49.2 ms | 6.6 ms | 49.3 ms | 0.0 ms | 49.0 ms | 6.7 ms |

*Cached and uncached are interleaved in one page against the same target, because measuring them in separate browsers reported the uncached run as three times FASTER — the first run was paying for a cold server and the second inherited a warm one. The uncached pass runs first, so any residual warming works against the cache.*

**The cache works and it barely matters.** On a hit the network cost of a navigation is **0 ms**, which is the cache doing exactly its job — and the navigation takes the same total time, because the round trip was never the cost. Roughly 42 ms of a ~49 ms navigation is building the tree and drawing it. Every headline figure in Tables 1–14 was measured with no caching at all, so they are a floor rather than a best case.


### Table 15 note — phylo.io's "Highlight BCN" throws in compare mode

Every attempt failed, at every rung, with the same error:

> `Cannot read properties of null (reading '_children')`

It is reached only from the context-menu item of that name (`viewer.js` line 1175 is the sole caller), with the arguments used here, in phylo.io 2.1.1. The cause is in `api.js`: the BCN worker's reply is used to build **two separate models**, and the `elementBCN` references inside the first reply point at that reply's own embedded copy of the second tree rather than at the model built from it. `getHierarchyNodeFromModelNode` compares by object identity, finds nothing, returns null, and `expandToRoot` passes that null to `apply_collapse_from_data_to_d3`, which reads `_children` on it. The targets are parentless, which is the visible symptom of being detached.

Recorded with the mechanism because it is a claim about someone else's tool. It also sharpens the comparison rather than softening it: the cross-tree jump is the operation PhyloDelta's design is most open to criticism over — it costs an `/ancestor` call and a slice the panel has never held — and it is the one the comparison tool cannot complete at all.



## Table 17 — Does the chosen metric change what a build costs?

<!-- tier: SUPPORT -->
> **SUPPORT** — Why the metric choice is not free, and where §9's claim holds. Relevant only if the thesis discusses metric plugins.

*Seconds, from the worker's own per-metric timings at `PHYLODELTA_THREADS=2`. "Shared" is what every metric in a set pays once: parse, reconcile, correspondence, store.*

| leaves | shared work | rf | rf-treediff | triplet | total | metrics as % of total |
|---:|---:|---:|---:|---:|---:|---:|
| 1,000 | 0.0 s | 0.0 s | 0.0 s | 0.0 s | 0.1 s | *n/a* |
| 2,500 | 0.1 s | 0.0 s | 0.0 s | 0.1 s | 0.1 s | *n/a* |
| 5,000 | 0.1 s | 0.0 s | 0.0 s | 0.1 s | 0.3 s | *n/a* |
| 10,000 | 0.2 s | 0.0 s | 0.0 s | 0.4 s | 0.7 s | *n/a* |
| 17,645 | 0.4 s | 0.0 s | 0.1 s | 1.1 s | 1.6 s | 75% |
| 35,290 | 1.1 s | 0.1 s | 0.1 s | 2.6 s | 4.0 s | 70% |
| 70,580 | 4.0 s | 0.1 s | 0.2 s | 5.8 s | 10.2 s | 60% |
| 141,160 | 14.8 s | 0.2 s | 0.5 s | 12.3 s | 28.0 s | 46% |
| 282,320 | 57.9 s | 0.5 s | 1.0 s | 25.5 s | 85.3 s | 32% |
| 564,640 | 256.3 s | 1.0 s | 2.2 s | 53.6 s | 313.9 s | 18% |

**The answer reverses with size, so "does the metric matter" has no single answer.** `rf` and `rf-treediff` are free at every scale — together 3.2 s of a 314 s build at 564,640 leaves. `triplet` is not: at 141,160 it costs 12.3 s against 14.8 s for all the shared work, very nearly doubling the build. By 564,640 `triplet` alone has fallen back to 17% of the build (the table's last column counts all three metrics together), because the shared work is O(n^2) and the metric is near-linear, so correspondence overtakes it.

So §9's claim that several metrics cost little more than one is **true asymptotically and misleading in the middle** — which is where most real trees sit. The claim should be stated about the *shared* work, which is what is actually shared, rather than about metrics in general.

**Measured from the worker's log, not from wall-clock differences.** The three metric sets are uploaded in a fixed order, so the "+triplet" build is always last, and the first pass showed it at a suspiciously uniform 1.7-2x the others — the shape of an ordering artefact rather than a cost. Per-metric timings carry no such confound.

*Absolute shared-work times in this table come from a single freshly-built store in one sitting and run lower than Table 9's for the same rung (256 s against 493 s at 564,640). That is the store-dependent variance already recorded in §34.9 and §34.11, not a change in the code. What this table is for is the ratio within each row, which is internally consistent.*


## Table 18 — Two RF implementations against each other

<!-- tier: SUPPORT -->
> **SUPPORT** — Validation: two independent RF implementations agreeing at 1.1M nodes. A sentence, with the table in an appendix.

| leaves | built-in `rf` | `rf-treediff` | agree |
|---:|---:|---:|:---:|
| 1,000 | 531 | 531 | yes |
| 2,500 | 1,219 | 1,219 | yes |
| 5,000 | 2,207 | 2,207 | yes |
| 10,000 | 4,113 | 4,113 | yes |
| 17,645 | 6,825 | 6,825 | yes |
| 35,290 | 13,650 | 13,650 | yes |
| 70,580 | 27,300 | 27,300 | yes |
| 141,160 | 54,600 | 54,600 | yes |
| 282,320 | 109,200 | 109,200 | yes |
| 564,640 | 218,400 | 218,400 | yes |

*20 of 20 builds agree exactly.* Different algorithms over different representations by different authors — TreeDiff is the reference implementation of the paper this project follows (§1.10) — so agreement at 1,129,279 nodes is a check on both, and a disagreement would have meant one of them was wrong.


## Table 19 — Bytes over the wire

<!-- tier: PRESENT -->
> **PRESENT** — The claim as the quantity it is actually about: bytes over the wire. Present it beside Table 12 — 12 is the mechanism, 19 is what the mechanism buys.

*"Never send the whole tree" is a claim about transferred bytes. Measured from the wire — `request.sizes()` per response, not file sizes on disk — uncompressed on both sides, one origin.*

**Application and data are separate columns on purpose.** PhyloDelta ships a bundle too, and quoting its slices against phylo.io's whole-tree download while ignoring that would be comparing a partial cost with a total one — the error Table 2 exists to prevent. Add the columns as you see fit; the application bytes are paid once per visit, the data bytes once per comparison.

| leaves | phylo.io app | phylo.io data | phylo.io total | PhyloDelta app | PhyloDelta data | PhyloDelta total | data ratio | total ratio |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1,000 | 8.27 MB | 0.02 MB | 8.28 MB | 0.49 MB | **27.5 KB** | 0.52 MB | **1x** | 16x |
| 2,500 | 8.27 MB | 0.04 MB | 8.31 MB | 0.49 MB | **27.7 KB** | 0.52 MB | **1x** | 16x |
| 5,000 | 8.27 MB | 0.08 MB | 8.35 MB | 0.49 MB | **28.3 KB** | 0.52 MB | **3x** | 16x |
| 10,000 | 8.27 MB | 0.17 MB | 8.43 MB | 0.49 MB | **28.6 KB** | 0.52 MB | **6x** | 16x |
| 17,645 | 8.27 MB | 1.11 MB | 9.38 MB | 0.49 MB | **31.3 KB** | 0.52 MB | **35x** | 18x |
| 35,290 | 8.27 MB | 2.07 MB | 10.34 MB | 0.49 MB | **31.2 KB** | 0.52 MB | **65x** | 20x |
| 70,580 | 8.27 MB | 4.25 MB | 12.52 MB | 0.49 MB | **31.1 KB** | 0.52 MB | **134x** | 24x |
| 141,160 | 8.27 MB | 8.61 MB | 16.87 MB | 0.49 MB | **30.7 KB** | 0.52 MB | **273x** | 32x |
| 282,320 | 8.27 MB | 17.50 MB | 25.76 MB | 0.49 MB | **30.1 KB** | 0.52 MB | **567x** | 50x |
| 564,640 | 8.27 MB | 35.49 MB | 43.75 MB | 0.49 MB | **28.9 KB** | 0.52 MB | **1,199x** | 84x |

**At 564,640 leaves phylo.io must transfer 35.5 MB of tree and still cannot open the comparison** (Table 1). PhyloDelta transfers 28.9 KB and shows it. The data column is the one that matters for the claim: it is flat — 27.5 KB at 1,000 leaves and 28.9 KB at 564,640 — against a download that grows linearly with the tree.

**The application bundles run the other way, and by more than expected.** phylo.io's is 8.27 MB — `phylo.js` at 4.0 MB plus two worker chunks at 2.9 and 1.4 MB — against PhyloDelta's 0.49 MB. So PhyloDelta transfers less **in total at every rung including the smallest**, which was not the expected result: the prediction was that it would lose on total bytes on small trees and win only through the data column.

*Two caveats, and they pull in opposite directions — stated separately rather than netted off.*

- **Compression is off**, deliberately, so both tools face identical transport. It was expected to narrow the ratio, since Newick compresses well. Measured, it **widens** it — see Table 20.

- **In favour of it:** PhyloDelta's data figure includes a ~13 KB `GET /api/v1/datasets` catalogue whose size tracks **how many comparisons the store holds**, not tree size. The benchmark store holds every ladder rung, so a single-comparison deployment transfers closer to 15 KB and the real figure is about half what is shown.


## Table 20 — The same transfer, compressed

<!-- tier: SUPPORT -->
> **SUPPORT** — Table 19 under compression, which is what a real deployment serves. Answers the first objection anyone will raise to 19, and answers it the other way from the expected one.

*The same runner with `BENCH_GZIP=1`: `serve.mjs` compresses static files **and** proxied API responses. Both tools, both transports, nothing else changed.*

The API had to be compressed in the proxy, because FastAPI ships no `GZipMiddleware`. Without that, this run would have compressed phylo.io's Newick and left this frontend's JSON alone — measuring a transport difference and reporting it as a design one, in our own favour.

| leaves | phylo.io data | PhyloDelta data | ratio, gzip | ratio, raw |
|---:|---:|---:|---:|---:|
| 1,000 | 0.01 MB | **7.4 KB** | **1x** | 1x |
| 2,500 | 0.02 MB | **7.5 KB** | **2x** | 1x |
| 5,000 | 0.03 MB | **7.7 KB** | **4x** | 3x |
| 10,000 | 0.07 MB | **7.8 KB** | **8x** | 6x |
| 17,645 | 0.49 MB | **9.8 KB** | **49x** | 35x |
| 35,290 | 0.80 MB | **9.7 KB** | **80x** | 65x |
| 70,580 | 1.60 MB | **9.6 KB** | **163x** | 134x |
| 141,160 | 3.21 MB | **9.3 KB** | **336x** | 273x |
| 282,320 | 6.46 MB | **8.8 KB** | **718x** | 567x |
| 564,640 | 12.96 MB | **7.7 KB** | **1,644x** | 1,199x |

**Compression widens the gap, which was not the expectation.** At 564,640 leaves the ratio goes from 1,199x to 1,644x. The reason is in the compression factors, not in the design: the slice JSON compresses 3.8x — repeated keys and small integers — while the Newick manages only 2.7x, because at this size it is mostly unique labels and branch lengths, which is close to incompressible.

This matters for the write-up beyond the number: gzip is what a real deployment serves, so **Table 20 is the honest production figure and Table 19 is the conservative one.** Quoting 19 understates the result.

*Application bundles compress too, and the asymmetry survives: 1.41 MB against 0.14 MB, still 10x apart.*


## Table 21 — Sized to the viewport, not to the tree

<!-- tier: PRESENT -->
> **PRESENT** — The other half of "sized to the viewport". Every other table shows the payload ignoring the tree; only this one shows it following the window, which is what earns the word *sized*.

*Slice payload only, summed across both panels, from the wire. Width held at 1440 px; height varied.*

Every other table here shows the payload ignoring the **tree**. That is necessary but not sufficient: a server returning a fixed fifty leaves whatever the window would satisfy all of them while not doing what the design claims. This grid separates the two — read **down** a column for invariance to the tree, and **across** the rows for dependence on the window.

| window px | panel px | leaf budget | 17,645 leaves | 564,640 leaves |
|---:|---:|---:|---:|---:|
| 400 | 255 | **50** | 14.7 KB / 50 tips | 11.9 KB / 50 tips |
| 700 | 555 | **50** | 14.7 KB / 50 tips | 11.9 KB / 50 tips |
| 1,000 | 855 | **50** | 14.7 KB / 50 tips | 11.9 KB / 50 tips |
| 1,200 | 1055 | **75** | 22.0 KB / 75 tips | 19.1 KB / 75 tips |
| 1,400 | 1255 | **100** | 28.3 KB / 100 tips | 26.4 KB / 100 tips |
| 1,700 | 1555 | **100** | 28.3 KB / 100 tips | 26.4 KB / 100 tips |
| 2,000 | 1855 | **125** | 34.8 KB / 125 tips | 33.1 KB / 125 tips |
| 2,600 | 2455 | **175** | 47.0 KB / 175 tips | 46.0 KB / 175 tips |
| 3,200 | 3055 | **225** | 59.1 KB / 225 tips | 57.7 KB / 225 tips |

**Across the rows the payload follows the window:** panel 255 px to 3,055 px (12x) takes the budget from 50 to 225 tips and the payload from 14.7 KB to 59.1 KB. Above the floor the ratio of panel pixels to budgeted leaves settles at about **14**, which is `PIXELS_PER_LEAF` — the design constant recovered from the measurement rather than asserted.

**Down the columns it ignores the tree:** at the same window, 17,645 leaves and 564,640 leaves — 32x more — cost 59.1 KB and 57.7 KB. The larger tree is marginally *cheaper*, which is label lengths, not structure.

**The honest qualification: the steps are coarse.** `readableBudget` rounds to 25 leaves at 14 px each, so the payload only changes every ~350 px of panel — and with the 40-leaf floor, every window from 400 to 1,000 px gets the same 50 tips. So "sized to the viewport" holds with a granularity of about 350 px, and across the ordinary range of laptop windows the payload is in practice constant. The quantisation is deliberate (a settling layout must not cost a request, §29) but it does mean the scaling only bites on tall displays.

*This also caught a sampling error worth keeping: the first run used evenly-spaced heights of 400-1,000 and reported an identical payload four times, which reads as the payload ignoring the viewport when it was the sample sitting inside one quantisation bucket.*


# PhyloDelta vs Phylo.io — measured comparison

## Environment

| | |
|---|---|
| Machine | Apple M4 laptop — **4 performance + 6 efficiency cores**, 24 GiB |
| OS | macOS 27.0.1 (build 26A434, Darwin 27.0.0) |
| Browser | Chrome 154.0.8037.58, **headless**, system Chrome via Playwright's `channel: "chrome"` |
| Browser flags | `--js-flags=--max-old-space-size=8192`, `--disable-dev-shm-usage` — **both tools, identically** |
| Viewport | 1440 x 900; Table 21 varies the height |
| **Tool compared against** | **phylo.io 2.2.5** (2026-01-30), its own published `dist/`, unmodified — the current release at the time of measurement |
| This project | generated at commit `a6cb1bd + uncommitted changes` |
| Runtimes | Python 3.12.14 (`uv`), Node 26.3.0, Playwright 1.63.0 |
| Backend database | SQLite, in the store directory |
| Store location | `/private/tmp/...` — an APFS SSD volume, **not** a RAM disk |
| **Backend threads** | **2 of the 10 cores** (`PHYLODELTA_THREADS=2`) |
| Transport | one origin, one fresh page per measurement; uncompressed except Table 20, which is gzip |
| Power state | not controlled (laptop) — bears only on Table 9's 564,640 ratios, already withdrawn there |

**Every figure here was re-measured against 2.2.5**, the current release, on a store rebuilt from scratch. The earlier campaign used 2.1.1 (a 2025-07-02 checkout) and its figures were indistinguishable: 199.1 s against 199.4 s to complete the comparison at 10,000 leaves, and the same memory to the tenth. `api.js` and `worker_bcn.js` are unchanged between the two releases, so that is the expected result — but it is now measured rather than inferred from a diff.

**The two entries that matter most for checking these numbers** are the browser flags and the phylo.io version. The heap cap decides *where* a tool fails, so Table 1's and Table 4's `failed` rows are statements about the tool at an 8 GiB cap, not at Chrome's default — and it is raised for both tools, which is what makes a failure the tool's own ceiling. The version matters because several findings are about phylo.io's behaviour: the "Highlight BCN" crash (Table 15) is a fact about **2.1.1** and a later release may fix it.

**Headless, throughout.** Rendering in headless Chrome is not identical to a visible window, and these are partly rendering measurements — so this is a real caveat, not a footnote. It applies equally to both tools, so the *comparison* holds; the absolute paint times would need re-taking in a headed browser to be quoted as what a user sees.

*Power state was not controlled, and is recorded for completeness rather than as a limitation.* Every claim these tables make is a claim about **shape** — flat against growing, completes against does not, ratios from 16x to 1,644x — and none of them turns on a timing difference of the size throttling produces. It bears on exactly one number: the 564,640 row of Table 9, whose ratios are withdrawn there on those grounds already.

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
- **Table 22** — Correctness again, but against implementations that share nothing with this one. Table 18's agreement is with the same paper's own code; this is the check an examiner will ask for.

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

*If only one table can be shown, it is 19.* It states the claim in the quantity the claim is about — 28.2 KiB against 33.8 MiB at 564,640 leaves — and it is the only table whose ratio grows without bound while everything on this side stays flat.

*Two tables to read together, not separately:* Table 1 without Table 2 overstates the result, because the tools do not draw the same amount — that asymmetry IS the design, and hiding it is how an earlier version of this comparison reported a 34x that did not exist.

---

## Table 1 — Scalability: where each tool stops

<!-- tier: PRESENT -->
> **PRESENT** — The headline. Where each tool stops, and the size claim.

> **Heap here is MAIN-THREAD ONLY.** `Runtime.getHeapUsage` reads one isolate, and phylo.io computes its comparison in a **Web Worker** with a heap of its own. Where the comparison finishes, the worker's results are copied back and the figure reflects them; where it does not, the column shows only the two parsed trees and so *falls* as the tree grows. It is a lower bound, not the tool's memory. Table 4's RSS figures, which cover the whole renderer including workers, are the honest memory numbers.

Cold start to an interactive comparison. Phylo.io is split into *paint* (two trees drawn) and *compare* (its best-corresponding-node worker finished), because only the second is the same job PhyloDelta is doing: a slice arrives with its similarity values already in it.

| leaves | phylo.io paint | phylo.io compare | phylo.io main-thread heap | PhyloDelta | PhyloDelta heap | PhyloDelta advantage | server precompute |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 1,000 | 0.4 s | 5 s | 26.1 MiB | 0.24 s | 3.5 MiB | **20x** | 0.5 s |
| 2,500 | 0.9 s | 18 s | 95.5 MiB | 0.22 s | 3.5 MiB | **83x** | 2.0 s |
| 5,000 | 1.9 s | 53 s | 277.6 MiB | 0.22 s | 3.5 MiB | **235x** | 2.1 s |
| 10,000 | 4.4 s | 199 s | 1,126.7 MiB | 0.21 s | 3.5 MiB | **948x** | 2.0 s |
| 17,645 | **failed** | **failed** | **failed** | 0.24 s | 3.5 MiB | **only PhyloDelta** | 2.6 s |
| 35,290 | **failed** | **failed** | **failed** | 0.23 s | 3.5 MiB | **only PhyloDelta** | 3.6 s |
| 70,580 | **failed** | **failed** | **failed** | 0.31 s | 3.5 MiB | **only PhyloDelta** | 6.1 s |
| 141,160 | **failed** | **failed** | **failed** | 0.51 s | 3.5 MiB | **only PhyloDelta** | 17.2 s |
| 282,320 | **failed** | **failed** | **failed** | 0.48 s | 3.5 MiB | **only PhyloDelta** | 60.8 s |
| 564,640 | **failed** | **failed** | **failed** | 0.74 s | 3.5 MiB | **only PhyloDelta** | 262.6 s |

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
| 17,645 | failed | failed | 14 | 50 per panel |
| 35,290 | failed | failed | 14 | 50 per panel |
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
| 1,000 | 26.1 MiB | — | 3.5 MiB |
| 2,500 | 95.5 MiB | 3.65x | 3.5 MiB |
| 5,000 | 277.6 MiB | 2.91x | 3.5 MiB |
| 10,000 | 1,126.7 MiB | 4.06x | 3.5 MiB |
| 17,645 | — *(compare unfinished — worker excluded)* | — | 3.5 MiB |
| 35,290 | — *(compare unfinished — worker excluded)* | — | 3.5 MiB |
| 70,580 | — *(compare unfinished — worker excluded)* | — | 3.5 MiB |
| 141,160 | — *(compare unfinished — worker excluded)* | — | 3.5 MiB |
| 282,320 | — *(compare unfinished — worker excluded)* | — | 3.5 MiB |
| 564,640 | — *(compare unfinished — worker excluded)* | — | 3.5 MiB |

## Table 4 — Failure behaviour, given 30 minutes and 16 GiB

<!-- tier: SUPPORT -->
> **SUPPORT** — The detail behind Table 1's 'failed': what failed and how. Cite the 30-minute budget in the text.

Table 1's failures are against a stated budget. This removes the budget: each rung was given **30 minutes** with a 16 GiB renderer cap on a 24 GiB machine.

| leaves | outcome | time to failure | peak renderer (MiB) |
|---:|---|---:|---:|
| 141,160 | **renderer process crashed** | 13.3 min | 10,877 MiB |
| 282,320 | **renderer process crashed** | 14.4 min | 10,715 MiB |

*Peak memory is sampled every 2 s from process RSS, so it is a lower bound and the two figures should not be read as an ordering.*

## Table 5 — Accuracy: what the LSH approximation costs

<!-- tier: PRESENT -->
> **PRESENT** — Correctness. A fast wrong answer is worth nothing, so the approximation's cost has to be stated.

Phylo.io finds each clade's best corresponding node by maximising Jaccard over **ten candidates** retrieved by MinHash/LSH (`worker_bcn.js`). This project maximises over every node, so it is an upper bound and every gap is a retrieval miss. Run on pairs with **identical leaf sets**, so a difference cannot be explained by unmatched-leaf handling.

| leaves | clades | exact match | missed | median gap | worst gap | beat exact |
|---:|---:|---:|---:|---:|---:|---:|
| 1000 | 998 | 952 (95.4%) | 46 (4.6%) | 0.123 | 0.449 | 0 |
| 10000 | 9,997 | 9,580 (95.8%) | 417 (4.2%) | 0.133 | 0.750 | 0 |
| 2500 | 2,493 | 2,396 (96.1%) | 97 (3.9%) | 0.115 | 0.619 | 0 |
| 5000 | 4,998 | 4,811 (96.3%) | 187 (3.7%) | 0.112 | 0.667 | 0 |

*`beat exact` must be 0: an exhaustive search cannot be beaten by a subset of the same candidates. It is reported as a check on the method, not as a result.*

## Table 6 — Where phylo.io's time goes

<!-- tier: WORKING -->
> **WORKING** — Diagnostic. Phase-splitting another tool's time compares phase names that do not mean the same thing; Table 1's paint/compare split is the part that survives.

Its own phase split. Parsing and drawing are cheap and near-linear; **the comparison is what scales badly** — which is the same finding as this project's own correspondence search being the quadratic step (DECISIONS §17), reached independently by both implementations.

| leaves | parse | layout | paint | compare | compare as % of total |
|---:|---:|---:|---:|---:|---:|
| 1,000 | 0.02 s | 0.19 s | 0.21 s | 5 s | 92% |
| 2,500 | 0.04 s | 0.40 s | 0.45 s | 18 s | 95% |
| 5,000 | 0.08 s | 0.92 s | 0.90 s | 53 s | 97% |
| 10,000 | 0.22 s | 2.34 s | 1.83 s | 199 s | 98% |
| 17,645 | — | — | — | **failed** | — |
| 35,290 | — | — | — | **failed** | — |
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
| 1,000 | 1,999 | **0.62 s** | 0.48 s | 2.46 s | 3.4 MiB |
| 2,500 | 4,999 | **0.52 s** | 0.48 s | 2.69 s | 3.4 MiB |
| 5,000 | 9,999 | **0.61 s** | 0.45 s | 2.46 s | 3.4 MiB |
| 10,000 | 19,999 | **0.58 s** | 0.46 s | 1.61 s | 3.4 MiB |
| 17,645 | 35,289 | **0.61 s** | 0.47 s | 1.06 s | 3.4 MiB |
| 35,290 | 70,579 | **0.58 s** | 0.44 s | 0.73 s | 3.4 MiB |
| 70,580 | 141,159 | **0.59 s** | 0.42 s | 0.89 s | 3.4 MiB |
| 141,160 | 282,319 | **0.66 s** | 0.42 s | 2.16 s | 3.4 MiB |
| 282,320 | 564,639 | **0.53 s** | 0.44 s | 2.35 s | 3.4 MiB *(beyond phylo.io — it crashes at 141,160)* |
| 564,640 | 1,129,279 | **0.43 s** | 0.38 s | 0.97 s | 3.4 MiB *(beyond phylo.io — it crashes at 141,160)* |

## Table 8 — The precompute PhyloDelta pays instead

<!-- tier: PRESENT -->
> **PRESENT** — What the design costs. Presenting Table 1 without this is claiming the precompute is free.

Measured through the real upload path: POST the bundle, a worker claims it, poll until ready. Includes ingest, reconciliation, the correspondence search and the metric.

**At 2 threads**, the deployment setting (see Environment and Table 9). The 10-thread column is kept because the first runs used the default, and because the gap is the cost of the choice.

| leaves | build at 2 threads | build at 10 threads | bundle size |
|---:|---:|---:|---:|
| 1,000 | **0.5 s** | 2.0 s | 0.0 MiB |
| 2,500 | **2.0 s** | 2.0 s | 0.0 MiB |
| 5,000 | **2.1 s** | 2.0 s | 0.1 MiB |
| 10,000 | **2.0 s** | 2.0 s | 0.2 MiB |
| 17,645 | **2.6 s** | 2.5 s | 1.1 MiB |
| 35,290 | **3.6 s** | 3.0 s | 2.0 MiB |
| 70,580 | **6.1 s** | 6.1 s | 4.1 MiB |
| 141,160 | **17.2 s** | 17.2 s | 8.2 MiB |
| 282,320 | **60.8 s** | 60.8 s | 16.7 MiB |
| 564,640 | **262.6 s** | 251.0 s | 33.8 MiB |

*The ~2 s floor at small sizes is the worker's poll interval, not work.*

## Table 9 — Build time at pinned thread counts

<!-- tier: SUPPORT -->
> **SUPPORT** — Justifies the 2-thread setting every build figure uses. One sentence plus the table in an appendix.

Table 8 used the default — one thread per hardware thread, **10** on this machine. These are the same builds with the count pinned, through the same upload path, each on its own store.

| leaves | 1 thread | 2 threads | 10 threads | 2 vs 1 | 10 vs 1 |
|---:|---:|---:|---:|---:|---:|
| 1,000 *(floor-limited — ratios are noise)* | 0.5 s | 0.5 s | 0.5 s | 1.00x | 1.00x |
| 2,500 *(floor-limited — ratios are noise)* | 2.1 s | 2.0 s | 2.0 s | 1.00x | 1.00x |
| 5,000 *(floor-limited — ratios are noise)* | 2.0 s | 2.1 s | 2.1 s | 0.99x | 0.99x |
| 10,000 *(floor-limited — ratios are noise)* | 2.6 s | 2.0 s | 2.0 s | 1.25x | 1.25x |
| 17,645 *(floor-limited — ratios are noise)* | 2.6 s | 2.6 s | 2.6 s | 1.00x | 1.00x |
| 35,290 | 4.1 s | 3.6 s | 2.6 s | 1.14x | 1.60x |
| 70,580 | 9.1 s | 6.1 s | 4.1 s | 1.49x | 2.22x |
| 141,160 | 30.9 s | 17.2 s | 9.0 s | 1.79x | 3.42x |
| 282,320 | 113.4 s | 60.8 s | 26.8 s | 1.87x | 4.23x |
| 564,640 | 496.2 s | 262.6 s | 125.3 s | 1.89x | 3.96x |

**Read the larger rows.** From 35,290 to 564,640 the picture is clean and monotone: two threads rise 1.14x -> 1.89x, ten rise 1.60x -> 3.96x. The gain grows with size because below ~70,000 leaves the *serial* parts — parse, reconcile, ingest, and the 2 s poll — are most of the elapsed time, and threading the search cannot touch them. Amdahl's law, visible directly.

**Re-measured, each thread count from an idle machine.** The first version of this table showed a 564,640 row where two threads gave 2.44x — superlinear, therefore impossible for pure parallelism. That was attributed to thermal drift and the attribution was wrong: the same rung measured cold and then immediately after twenty minutes of saturating load gives 262.6 s and 244.3 s, the hot run marginally *faster*, with no thermal warning recorded by the OS either time.

The cause was that **the run labelled "2 threads" executed with one**. It matches a fresh single-threaded measurement to within 0.7% at 564,640 leaves, and the gap between old and new is 1.88x — exactly the 2-thread speedup in Table 10. `PHYLODELTA_THREADS` is read by the *worker*; the measuring tool took the thread count only to name its output file and never asked the worker what it was running with. A parameter that describes a run instead of controlling it will eventually describe it wrongly, in a file that looks perfectly well-formed (DECISIONS, Corrections).

**What to choose.** At 564,640 leaves two threads give 1.89x at 94% efficiency; ten give 3.96x at 40%. One thread wastes a near-free doubling. If efficiency is the objective, **two is the sweet spot** — but latency for a single comparison favours more threads, and throughput for a queue favours fewer per build with more builds at once. `PHYLODELTA_THREADS` exists so a deployment can choose; there is no single best value.

## Table 10 — Thread scaling of the parallel step

<!-- tier: WORKING -->
> **WORKING** — Subsumed by Table 9, which measures the same trade-off on whole builds rather than one step.

**Only one step of the build is parallel**: the clade-correspondence search. It is driven directly here rather than timed through a whole build, which would dilute it with the single-threaded parse, reconciliation and metric around it. 70,580 leaves, best of 3 runs.

| threads | time | speedup | efficiency | result identical to 1 thread |
|---:|---:|---:|---:|:--:|
| 1 | 6.48 s | 1.00x | 100% | yes |
| 2 | 3.61 s | 1.80x | 90% | yes |
| 3 | 2.63 s | 2.46x | 82% | yes |
| 4 | 2.07 s | 3.13x | 78% | yes |
| 6 | 1.78 s | 3.64x | 61% | yes |
| 8 | 1.59 s | 4.07x | 51% | yes |
| 10 | 1.45 s | 4.48x | 45% | yes |

**The last column is the one that matters.** Each index's result depends only on read-only inputs, so it must be bit-identical whatever the thread count. A race here would not crash — it would quietly return a slightly wrong best corresponding node, which no timing figure would reveal.

The knee is at **4 threads**, which is the number of performance cores on this machine (10 cores, 4 of them performance). One to four threads buys 3.37x at 84% efficiency; four to ten buys only another 1.69x and drops efficiency to 57%. On a shared machine 4 threads is the better trade: 1.7x slower than 10, for 2.5x fewer cores.

## Table 11 — What the server needs while it builds

<!-- tier: SUPPORT -->
> **SUPPORT** — The deployability argument: server memory is linear, not quadratic. A sentence with the marginal figure.

Peak RSS of the worker process, sampled every 200 ms against its idle baseline of 70 MiB. Measured in a throwaway store so nothing else was disturbed.

**The search is quadratic in time but LINEAR in memory** — every doubling of leaves roughly doubles the footprint. The pruning bound means it never materialises an n x n matrix: it holds the two trees' columns, which are memory-mapped, and one scratch buffer per thread. For contrast, building these trees with NJ would need ~466 GiB of distance matrix at 500,000 taxa.

Both thread settings are shown, compared on **absolute peak RSS** rather than on the over-idle delta. The two runs had different idle baselines (70 MiB and 70 MiB), so subtracting each from its own baseline would make the small rungs look like 2 threads used *more*, which is an artefact of the baseline and not a measurement.

**Fewer threads really does use less memory** — 30-40% less across the range, because the scratch buffer is per-thread and eight of them are not allocated. That is a larger effect than expected: the prediction was that the memory-mapped trees would dominate and the difference would be negligible. It does not, and it is not.

| leaves | peak RSS (2 thr, MiB) | peak RSS (10 thr, MiB) | difference | marginal (2 thr) | growth |
|---:|---:|---:|---:|---:|---:|
| 1,000 | **71 MiB** | 72 MiB | +1% | 1 MiB | — |
| 2,500 | **76 MiB** | 76 MiB | +0% | 7 MiB | 5.50x |
| 5,000 | **79 MiB** | 80 MiB | +1% | 10 MiB | 1.47x |
| 10,000 | **88 MiB** | 88 MiB | -0% | 19 MiB | 1.96x |
| 17,645 | **110 MiB** | 109 MiB | -0% | 40 MiB | 2.11x |
| 35,290 | **150 MiB** | 151 MiB | +1% | 81 MiB | 2.02x |
| 70,580 | **224 MiB** | 226 MiB | +1% | 155 MiB | 1.91x |
| 141,160 | **394 MiB** | 395 MiB | +0% | 324 MiB | 2.09x |
| 282,320 | **678 MiB** | 680 MiB | +0% | 609 MiB | 1.88x |
| 564,640 | **1,242 MiB** | 1,274 MiB | +3% | 1,172 MiB | 1.93x |

**The thread count barely affects memory.** Both runs are on an idle machine against the same 70 MiB idle baseline, and they differ by 0-3%. An earlier version of this table reported *fewer threads use 25-39% less memory* and offered it as a second reason to prefer two; that came from a 2-thread figure of 776 MiB which a fresh run does not reproduce, from the same campaign as the mislabelled thread counts in DECISIONS Corrections. The per-thread scratch buffers are small against the memory-mapped columns — which is what was predicted before the bad measurement overturned it.

*Every byte figure in these tables is binary — KiB, MiB, GiB (2^10, 2^20, 2^30). `ps -o rss` reports KiB natively; heap and transfer counts are raw byte counts divided by 2^20. Mixing decimal and binary is how a table comes to state two different things under one heading, and this one did for a while.*

*Build times are omitted here. This run measures memory, and Table 8's figures are the ones to quote for time.*

## Table 12 — The request a panel actually makes

<!-- tier: PRESENT -->
> **PRESENT** — The mechanism itself — a payload sized to the viewport, flat at every tree size. This is the thesis in one table.

The **cause**, where every other table shows the consequence. The same GET the frontend issues, at every tree size, read-only. Latency and payload are set by the viewport budget, so neither tracks the tree: **564x more leaves, the same few milliseconds and the same few kilobytes.**

| leaves | median | min | max | response | leaves drawn |
|---:|---:|---:|---:|---:|---:|
| 1,000 | **1.9 ms** | 1.6 ms | 2.0 ms | 5.4 KiB | 50 |
| 2,500 | **1.6 ms** | 1.5 ms | 1.7 ms | 5.5 KiB | 50 |
| 5,000 | **1.6 ms** | 1.5 ms | 2.0 ms | 5.6 KiB | 50 |
| 10,000 | **1.8 ms** | 1.6 ms | 1.9 ms | 5.6 KiB | 50 |
| 17,645 | **1.6 ms** | 1.6 ms | 1.7 ms | 6.9 KiB | 50 |
| 35,290 | **1.6 ms** | 1.6 ms | 1.7 ms | 6.9 KiB | 50 |
| 70,580 | **1.6 ms** | 1.5 ms | 1.7 ms | 6.8 KiB | 50 |
| 141,160 | **1.7 ms** | 1.6 ms | 1.7 ms | 6.7 KiB | 50 |
| 282,320 | **1.6 ms** | 1.5 ms | 2.0 ms | 6.5 KiB | 50 |
| 564,640 | **1.6 ms** | 1.6 ms | 1.7 ms | 6.0 KiB | 50 |

*From 1,000 to 564,640 leaves — a 565x increase — the median moves 1.9 ms to 1.6 ms and the payload 5.4 KiB to 6.0 KiB. Seven samples per rung after a warm-up, since the first touch of a store memory-maps it.*

## Table 13 — What the design costs

<!-- tier: PRESENT -->
> **PRESENT** — The honest ledger. What was given up to get Table 1.

| | phylo.io | PhyloDelta |
|---|---|---|
| Server required | no | **yes** |
| Precompute before first view | none | up to 263 s at 2 threads |
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
| 1,000 | 63.5 ms | 64.3 ms | 62.9 ms | 65.8 ms | 65.9 ms | 65.9 ms |
| 2,500 | 63.5 ms | 62.8 ms | **fails** | 65.9 ms | 65.9 ms | 65.9 ms |
| 5,000 | 63.8 ms | 64.0 ms | **fails** | 65.9 ms | 65.9 ms | 65.8 ms |
| 10,000 | 64.3 ms | 64.2 ms | **fails** | 66.0 ms | 65.9 ms | 65.9 ms |
| 17,645 | *no comparison* | *no comparison* | *no comparison* | 49.3 ms | 49.4 ms | 49.3 ms |

**"No comparison" is not slow navigation.** phylo.io paints both trees at 17,645 leaves but its best-corresponding-node worker never finishes there — Table 1 records `compareComplete=False` against a 600 s budget — so in compare mode there is nothing to navigate. Its navigation is therefore measurable only to **10,000 leaves**, where the comparison completes in 199 s. PhyloDelta is measured at 17,645 anyway, because holding flat is the claim.

*The first harness run reported that cell as "exceeded 900s", which reads as "its navigation is slow". It is not the same statement, and the distinction is the whole point of the row.*

**Both tools are driven one layer below the click** — phylo.io through `container.trigger_(action, …)`, which is exactly what its context-menu items call, and PhyloDelta through the actions its menu items call. Synthesising a click on a WebGL canvas would have charged hit-testing to one side only. What is excluded is the same for both: opening a menu and pressing an item.

**The operations are not equivalent in what they reveal.** phylo.io holds the whole tree, so it collapses and expands clades of up to 1,000 leaves and draws all of them. PhyloDelta's targets are the wedges in the current slice — 309 leaves down to 41 — and expanding one draws about fifty tips. phylo.io therefore does *more* drawing per operation at these sizes and is still faster; that is a real result and not one to explain away.


## Table 16 — Where a PhyloDelta navigation's time goes

<!-- tier: WORKING -->
> **WORKING** — The attribution behind Table 15 — the round trip is ~6 ms of a ~49 ms navigation. One sentence, not a table.

| leaves | expand total | of which fetch | back total | of which fetch | back, cache emptied | of which fetch |
|---:|---:|---:|---:|---:|---:|---:|
| 1,000 | 65.8 ms | 3.9 ms | 65.9 ms | 0.0 ms | 65.4 ms | 3.8 ms |
| 2,500 | 65.9 ms | 3.6 ms | 65.9 ms | 0.0 ms | 65.5 ms | 4.0 ms |
| 5,000 | 65.9 ms | 3.6 ms | 65.9 ms | 0.0 ms | 65.6 ms | 4.0 ms |
| 10,000 | 66.0 ms | 3.5 ms | 65.9 ms | 0.0 ms | 65.5 ms | 3.9 ms |
| 17,645 | 49.3 ms | 3.4 ms | 49.4 ms | 0.0 ms | 49.0 ms | 3.5 ms |

*Cached and uncached are interleaved in one page against the same target, because measuring them in separate browsers reported the uncached run as three times FASTER — the first run was paying for a cold server and the second inherited a warm one. The uncached pass runs first, so any residual warming works against the cache.*

**The cache works and it barely matters.** On a hit the network cost of a navigation is **0 ms**, which is the cache doing exactly its job — and the navigation takes the same total time, because the round trip was never the cost. Roughly 42 ms of a ~49 ms navigation is building the tree and drawing it. Every headline figure in Tables 1–14 was measured with no caching at all, so they are a floor rather than a best case.


### Table 15 note — phylo.io's "Highlight BCN" is intermittent

Every attempt failed in the navigation run above, at every rung, with the same error:

> `Cannot read properties of null (reading '_children')`

**But "always" was n=1 page load per rung, and the failure is intermittent.** A dedicated probe over repeated loads of the same pair at 1,000 leaves:

| phylo.io | page loads | loads where the jump worked | attempts succeeded |
|---|---:|---:|---:|
| 2.1.1 | 8 | 0 | 0/80 |
| 2.2.5 | 8 | 1 | 10/80 |

It is **decided per page load and then holds for that load** — a load either fails on every node tried or succeeds on every node tried. So the honest claim is that the jump fails in most loads, not that it never works, and Table 15 reports one load per rung, which is why it shows only the common outcome.

**The mechanism, and why it is conditional.** It is reached only from the context-menu item of that name (`viewer.js` line 1175 is the sole caller). `api.js` builds **two separate models** from the BCN worker's reply, and the `elementBCN` references inside the first point at that reply's own embedded copy of the second tree. `getHierarchyNodeFromModelNode` compares by object identity, so whether it finds anything depends on whether structured-clone identity between the two halves of one message survives into the rebuilt models — which is evidently not guaranteed. When it does not, the lookup returns null and `expandToRoot` hands that null to `apply_collapse_from_data_to_d3`, which reads `_children` on it.

**Not a version problem.** Checked against **2.2.5** (2026-01-30) as well as the 2.1.1 used elsewhere here: `api.js` and `worker_bcn.js` are unchanged between them, all four functions in this path are byte-identical, and the measured rates match. The 2.1.1 figures in these tables are not stale on this point.

The ceiling was confirmed on 2.2.5 directly rather than inferred from the diff: at **17,645 leaves** its comparison **did not complete** inside a 600 s budget, matching 2.1.1. That is the one claim the whole of Table 1 rests on, so it was worth running rather than arguing.

It still sharpens the comparison rather than softening it: the cross-tree jump is the operation PhyloDelta's design is most open to criticism over — it costs an `/ancestor` call and a slice the panel has never held — and it is the one the comparison tool manages only sometimes.



## Table 17 — Does the chosen metric change what a build costs?

<!-- tier: SUPPORT -->
> **SUPPORT** — Why the metric choice is not free, and where §9's claim holds. Relevant only if the thesis discusses metric plugins.

*Seconds, from the worker's own per-metric timings at `PHYLODELTA_THREADS=2`. "Shared" is what every metric in a set pays once: parse, reconcile, correspondence, store.*

| leaves | shared work | rf | rf-treediff | triplet | total | metrics as % of total |
|---:|---:|---:|---:|---:|---:|---:|
| 1,000 | 0.0 s | 0.0 s | 0.0 s | 0.0 s | 0.1 s | *n/a* |
| 2,500 | 0.1 s | 0.0 s | 0.0 s | 0.1 s | 0.1 s | *n/a* |
| 5,000 | 0.1 s | 0.0 s | 0.0 s | 0.2 s | 0.3 s | *n/a* |
| 10,000 | 0.2 s | 0.0 s | 0.0 s | 0.4 s | 0.7 s | *n/a* |
| 17,645 | 0.4 s | 0.0 s | 0.1 s | 1.2 s | 1.7 s | 76% |
| 35,290 | 1.2 s | 0.1 s | 0.1 s | 2.7 s | 4.2 s | 69% |
| 70,580 | 4.0 s | 0.1 s | 0.2 s | 5.8 s | 10.3 s | 59% |
| 141,160 | 14.9 s | 0.2 s | 0.5 s | 12.3 s | 28.1 s | 46% |
| 282,320 | 58.1 s | 0.5 s | 0.9 s | 25.4 s | 85.3 s | 31% |
| 564,640 | 241.9 s | 1.0 s | 2.0 s | 53.2 s | 298.8 s | 19% |

**The answer reverses with size, so "does the metric matter" has no single answer.** `rf` and `rf-treediff` are free at every scale — together 3.0 s of a 299 s build at 564,640 leaves. `triplet` is not: at 141,160 it costs 12.3 s against 14.8 s for all the shared work, very nearly doubling the build. By 564,640 `triplet` alone has fallen back to 18% of the build (the table's last column counts all three metrics together), because the shared work is O(n^2) and the metric is near-linear, so correspondence overtakes it.

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
| 1,000 | 7.91 MiB | 0.02 MiB | 7.93 MiB | 0.47 MiB | **22.5 KiB** | 0.49 MiB | **1x** | 16x |
| 2,500 | 7.91 MiB | 0.04 MiB | 7.95 MiB | 0.47 MiB | **22.7 KiB** | 0.49 MiB | **2x** | 16x |
| 5,000 | 7.91 MiB | 0.08 MiB | 7.99 MiB | 0.47 MiB | **23.3 KiB** | 0.49 MiB | **4x** | 16x |
| 10,000 | 7.91 MiB | 0.16 MiB | 8.07 MiB | 0.47 MiB | **23.6 KiB** | 0.49 MiB | **7x** | 16x |
| 17,645 | 7.91 MiB | 1.06 MiB | 8.97 MiB | 0.47 MiB | **26.3 KiB** | 0.49 MiB | **41x** | 18x |
| 35,290 | 7.91 MiB | 1.98 MiB | 9.89 MiB | 0.47 MiB | **26.2 KiB** | 0.49 MiB | **77x** | 20x |
| 70,580 | 7.91 MiB | 4.05 MiB | 11.97 MiB | 0.47 MiB | **26.0 KiB** | 0.49 MiB | **159x** | 24x |
| 141,160 | 7.91 MiB | 8.21 MiB | 16.12 MiB | 0.47 MiB | **25.7 KiB** | 0.49 MiB | **327x** | 33x |
| 282,320 | 7.91 MiB | 16.69 MiB | 24.60 MiB | 0.47 MiB | **25.1 KiB** | 0.49 MiB | **681x** | 50x |
| 564,640 | 7.91 MiB | 33.84 MiB | 41.76 MiB | 0.47 MiB | **23.9 KiB** | 0.49 MiB | **1,451x** | 85x |

**At 564,640 leaves phylo.io must transfer 33.8 MiB of tree and still cannot open the comparison** (Table 1). PhyloDelta transfers 23.9 KiB and shows it. The data column is the one that matters for the claim: it is flat — 22.5 KiB at 1,000 leaves and 23.9 KiB at 564,640 — against a download that grows linearly with the tree.

**The application bundles run the other way, and by more than expected.** phylo.io's is 7.91 MiB — `phylo.js` at 3.81 MiB plus two worker chunks at 2.74 and 1.36 MiB — against PhyloDelta's 0.47 MiB. So PhyloDelta transfers less **in total at every rung including the smallest**, which was not the expected result: the prediction was that it would lose on total bytes on small trees and win only through the data column.

*Two caveats, and they pull in opposite directions — stated separately rather than netted off.*

- **Compression is off**, deliberately, so both tools face identical transport. It was expected to narrow the ratio, since Newick compresses well. Measured, it **widens** it — see Table 20.

- **In favour of it:** PhyloDelta's data figure includes a ~13 KiB `GET /api/v1/datasets` catalogue whose size tracks **how many comparisons the store holds**, not tree size. The benchmark store holds every ladder rung, so a single-comparison deployment transfers closer to 15 KiB and the real figure is about half what is shown.


## Table 20 — The same transfer, compressed

<!-- tier: SUPPORT -->
> **SUPPORT** — Table 19 under compression, which is what a real deployment serves. Answers the first objection anyone will raise to 19, and answers it the other way from the expected one.

*The same runner with `BENCH_GZIP=1`: `serve.mjs` compresses static files **and** proxied API responses. Both tools, both transports, nothing else changed.*

The API had to be compressed in the proxy, because FastAPI ships no `GZipMiddleware`. Without that, this run would have compressed phylo.io's Newick and left this frontend's JSON alone — measuring a transport difference and reporting it as a design one, in our own favour.

| leaves | phylo.io data | PhyloDelta data | ratio, gzip | ratio, raw |
|---:|---:|---:|---:|---:|
| 1,000 | 0.01 MiB | **7.1 KiB** | **1x** | 1x |
| 2,500 | 0.02 MiB | **7.2 KiB** | **2x** | 2x |
| 5,000 | 0.03 MiB | **7.4 KiB** | **4x** | 4x |
| 10,000 | 0.06 MiB | **7.4 KiB** | **9x** | 7x |
| 17,645 | 0.46 MiB | **9.4 KiB** | **50x** | 41x |
| 35,290 | 0.76 MiB | **9.4 KiB** | **83x** | 77x |
| 70,580 | 1.53 MiB | **9.2 KiB** | **169x** | 159x |
| 141,160 | 3.07 MiB | **9.0 KiB** | **349x** | 327x |
| 282,320 | 6.16 MiB | **8.4 KiB** | **746x** | 681x |
| 564,640 | 12.36 MiB | **7.4 KiB** | **1,719x** | 1,451x |

**Compression widens the gap, which was not the expectation.** At 564,640 leaves the ratio goes from 1,451x to 1,719x. The reason is in the compression factors, not in the design: the slice JSON compresses 3.2x — repeated keys and small integers — while the Newick manages only 2.7x, because at this size it is mostly unique labels and branch lengths, which is close to incompressible.

This matters for the write-up beyond the number: gzip is what a real deployment serves, so **Table 20 is the honest production figure and Table 19 is the conservative one.** Quoting 19 understates the result.

*Application bundles compress too, and the asymmetry survives: 1.34 MiB against 0.13 MiB, still 10x apart.*


## Table 21 — Sized to the viewport, not to the tree

<!-- tier: PRESENT -->
> **PRESENT** — The other half of "sized to the viewport". Every other table shows the payload ignoring the tree; only this one shows it following the window, which is what earns the word *sized*.

*Slice payload only, summed across both panels, from the wire. Width held at 1440 px; height varied.*

Every other table here shows the payload ignoring the **tree**. That is necessary but not sufficient: a server returning a fixed fifty leaves whatever the window would satisfy all of them while not doing what the design claims. This grid separates the two — read **down** a column for invariance to the tree, and **across** the rows for dependence on the window.

| window px | panel px | leaf budget | 17,645 leaves | 564,640 leaves |
|---:|---:|---:|---:|---:|
| 400 | 255 | **50** | 14.7 KiB / 50 tips | 11.9 KiB / 50 tips |
| 700 | 555 | **50** | 14.7 KiB / 50 tips | 11.9 KiB / 50 tips |
| 1,000 | 855 | **50** | 14.7 KiB / 50 tips | 11.9 KiB / 50 tips |
| 1,200 | 1055 | **75** | 22.0 KiB / 75 tips | 19.1 KiB / 75 tips |
| 1,400 | 1255 | **100** | 28.3 KiB / 100 tips | 26.4 KiB / 100 tips |
| 1,700 | 1555 | **100** | 28.3 KiB / 100 tips | 26.4 KiB / 100 tips |
| 2,000 | 1855 | **125** | 34.8 KiB / 125 tips | 33.1 KiB / 125 tips |
| 2,600 | 2455 | **175** | 47.0 KiB / 175 tips | 46.0 KiB / 175 tips |
| 3,200 | 3055 | **225** | 59.1 KiB / 225 tips | 57.7 KiB / 225 tips |

**Across the rows the payload follows the window:** panel 255 px to 3,055 px (12x) takes the budget from 50 to 225 tips and the payload from 14.7 KiB to 59.1 KiB. Above the floor the ratio of panel pixels to budgeted leaves settles at about **14**, which is `PIXELS_PER_LEAF` — the design constant recovered from the measurement rather than asserted.

**Down the columns it ignores the tree:** at the same window, 17,645 leaves and 564,640 leaves — 32x more — cost 59.1 KiB and 57.7 KiB. The larger tree is marginally *cheaper*, which is label lengths, not structure.

**The honest qualification: the steps are coarse.** `readableBudget` rounds to 25 leaves at 14 px each, so the payload only changes every ~350 px of panel — and with the 40-leaf floor, every window from 400 to 1,000 px gets the same 50 tips. So "sized to the viewport" holds with a granularity of about 350 px, and across the ordinary range of laptop windows the payload is in practice constant. The quantisation is deliberate (a settling layout must not cost a request, §29) but it does mean the scaling only bites on tall displays.

*This also caught a sampling error worth keeping: the first run used evenly-spaced heights of 400-1,000 and reported an identical payload four times, which reads as the payload ignoring the viewport when it was the sample sitting inside one quantisation bucket.*


## Table 22 — The RF distance across four implementations

<!-- tier: PRESENT -->
> **PRESENT** — Correctness again, but against implementations that share nothing with this one. Table 18's agreement is with the same paper's own code; this is the check an examiner will ask for.

*Produced by `harness/rf_external.py` against DendroPy 5.1.0 and ETE3 3.1.3, with TreeDiff's `rf_postorder` beside them. Every tool is given the same two trees: rooted, and reconciled to their shared leaf set.*

| leaves | PhyloDelta `rf` | `rf-treediff` | x2 | DendroPy | ETE3 | agree |
|---:|---:|---:|---:|---:|---:|:---:|
| 1,000 | 531 | 531 | 1,062 | 1,062 | 1,062 | yes |
| 2,500 | 1,219 | 1,219 | 2,438 | 2,438 | 2,438 | yes |
| 5,000 | 2,207 | 2,207 | 4,414 | 4,414 | 4,414 | yes |
| 10,000 | 4,113 | 4,113 | 8,226 | 8,226 | 8,226 | yes |
| 17,645 | 6,825 | 6,825 | 13,650 | 13,650 | 13,650 | yes |

**The topology agrees exactly; the convention splits two against two.** 5 of 5 rungs match on every column. `rf-treediff` — TreeDiff's own binary, run as a subprocess by the server — returns this store's number unchanged, while DendroPy and ETE3 return exactly twice it at every rung. The same clades are found shared and the same found exclusive in all four; what differs is that TreeDiff halves the symmetric difference and the two general-purpose libraries do not.

**That is the useful shape of this table.** Table 18's agreement is between two implementations of one paper, so it could not have revealed a convention both inherited — it would have looked exactly like this if the definition were wrong. Adding tools that share nothing with either separates the two questions: the clade sets are confirmed by all four, and the factor of two is isolated as a reporting choice this backend takes from TreeDiff. The thesis has to state which it means, because a reader checking against a published RF for these trees would otherwise find this one off by half.

**Two settings decide whether the comparison is like-for-like**, and both produce a plausible near-miss rather than an error when wrong. *Rooting*: this store counts rooted clades, and DendroPy's unrooted mode gives 1,044 rather than 1,062 at 1,000 leaves, while ETE3 unroots by default. *Reconciliation*: handing the 17,645 pair over as it sits on disk gives 13,654 rather than 13,650, because ST 211 is in only one of the two trees (§2.6).


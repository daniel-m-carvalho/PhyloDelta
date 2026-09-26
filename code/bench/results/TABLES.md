# PhyloDelta vs Phylo.io — measured comparison

All measurements: **Chrome 154.0.8037.58**, viewport 1440x900, macOS, 24 GB RAM, 10 cores. Both tools served from one origin, uncompressed, one fresh page each.

## Table 1 — Scalability: where each tool stops

> **Heap here is MAIN-THREAD ONLY.** `Runtime.getHeapUsage` reads one isolate, and phylo.io computes its comparison in a **Web Worker** with a heap of its own. Where the comparison finishes, the worker's results are copied back and the figure reflects them; where it does not, the column shows only the two parsed trees and so *falls* as the tree grows. It is a lower bound, not the tool's memory. Table 4's RSS figures, which cover the whole renderer including workers, are the honest memory numbers.

Cold start to an interactive comparison. Phylo.io is split into *paint* (two trees drawn) and *compare* (its best-corresponding-node worker finished), because only the second is the same job PhyloDelta is doing: a slice arrives with its similarity values already in it.

| leaves | phylo.io paint | phylo.io compare | phylo.io main-thread heap | PhyloDelta | PhyloDelta heap | PhyloDelta advantage | server precompute |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 1,000 | 0.4 s | 5 s | 27.4 MB | 0.29 s | 3.6 MB | **17x** | 2.0 s |
| 2,500 | 0.9 s | 19 s | 100.2 MB | 0.24 s | 3.6 MB | **78x** | 2.0 s |
| 5,000 | 1.9 s | 53 s | 291.1 MB | 0.19 s | 3.6 MB | **272x** | 2.0 s |
| 10,000 | 4.4 s | 199 s | 1,181.4 MB | 0.20 s | 3.6 MB | **1,002x** | 2.5 s |
| 17,645 | 9.3 s | **did not finish** | 58.7 MB | 0.20 s | 3.6 MB | — | 2.6 s |
| 35,290 | 25.1 s | **did not finish** | 115.6 MB | 0.19 s | 3.7 MB | — | 3.0 s |
| 70,580 | **failed** | **failed** | **failed** | 0.57 s | 3.6 MB | **only PhyloDelta** | 5.6 s |
| 141,160 | **failed** | **failed** | **failed** | 0.34 s | 3.6 MB | **only PhyloDelta** | 14.4 s |
| 282,320 | **failed** | **failed** | **failed** | 0.94 s | 3.6 MB | **only PhyloDelta** | 49.8 s |

## Table 2 — What each tool actually drew

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

## Table 3 — Memory, and why it grows for one tool and not the other

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

## Table 4 — Failure behaviour, given 30 minutes and 16 GB

Table 1's failures are against a stated budget. This removes the budget: each rung was given **30 minutes** with a 16 GB renderer cap on a 24 GB machine.

| leaves | outcome | time to failure | peak renderer |
|---:|---|---:|---:|
| 141,160 | **renderer process crashed** | 17.1 min | 10,722 MB |
| 282,320 | **renderer process crashed** | 25.6 min | 9,690 MB |

*Peak memory is sampled every 2 s from process RSS, so it is a lower bound and the two figures should not be read as an ordering.*

## Table 5 — Accuracy: what the LSH approximation costs

Phylo.io finds each clade's best corresponding node by maximising Jaccard over **ten candidates** retrieved by MinHash/LSH (`worker_bcn.js`). This project maximises over every node, so it is an upper bound and every gap is a retrieval miss. Run on pairs with **identical leaf sets**, so a difference cannot be explained by unmatched-leaf handling.

| leaves | clades | exact match | missed | median gap | worst gap | beat exact |
|---:|---:|---:|---:|---:|---:|---:|
| 1000 | 998 | 969 (97.1%) | 29 (2.9%) | 0.108 | 0.333 | 0 |
| 2500 | 2,498 | 2,356 (94.3%) | 142 (5.7%) | 0.094 | 0.838 | 0 |
| 5000 | 4,994 | 4,765 (95.4%) | 229 (4.6%) | 0.103 | 0.640 | 0 |

*`beat exact` must be 0: an exhaustive search cannot be beaten by a subset of the same candidates. It is reported as a check on the method, not as a result.*

## Table 6 — Where phylo.io's time goes

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

## Table 7 — PhyloDelta, repeated

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

Measured through the real upload path: POST the bundle, a worker claims it, poll until ready. Includes ingest, reconciliation, the correspondence search and the metric.

| leaves | upload | build | total | bundle size |
|---:|---:|---:|---:|---:|
| 1,000 | 0.0 s | 2.0 s | 2.1 s | 0.0 MB |
| 2,500 | 0.0 s | 2.0 s | 2.0 s | 0.0 MB |
| 5,000 | 0.0 s | 2.0 s | 2.0 s | 0.1 MB |
| 10,000 | 0.0 s | 2.5 s | 2.5 s | 0.2 MB |
| 17,645 | 0.0 s | 2.6 s | 2.6 s | 1.1 MB |
| 35,290 | 0.0 s | 3.0 s | 3.1 s | 2.1 MB |
| 70,580 | 0.0 s | 5.6 s | 5.6 s | 4.2 MB |
| 141,160 | 0.0 s | 14.4 s | 14.4 s | 8.6 MB |
| 282,320 | 0.1 s | 49.8 s | 49.9 s | 17.5 MB |
| 564,640 | 0.1 s | 339.5 s | 339.7 s | 35.5 MB |

*The ~2 s floor at small sizes is the worker's poll interval, not work.*

## Table 9 — What the design costs

| | phylo.io | PhyloDelta |
|---|---|---|
| Server required | no | **yes** |
| Precompute before first view | none | up to 340 s |
| Whole tree ever visible | yes, in memory | **no, never transferred** |
| Works offline from a file | yes | no |
| Comparison recomputed on demand | yes | no, fixed at build |

## Table 10 — Provenance of the test data

| rung | origin |
|---:|---|
| 1,000 – 10,000 | pruned subsamples of the real vibrio NJ/UPGMA pair |
| 17,645 | **the real pair, unmodified** |
| 35,290 – 564,640 | nested relabelled copies of the real pair, preserving depth and imbalance |

*Every rung verified as a genuine comparison pair: 100% shared leaf sets, depth 79 to 191. Real MLST data stops at 27,962 leaves (clostridium), so rungs above 17,645 are synthetic and are used only for performance claims.*

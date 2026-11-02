# PhyloDelta vs Phylo.io — measured comparison

## Environment

| | |
|---|---|
| Machine | Apple M4 laptop — **4 performance + 6 efficiency cores**, 24 GiB |
| OS | macOS 27.0.1 (build 26A434, Darwin 27.0.0) |
| Browser | Chrome 156.0.8078.74, **headless**, system Chrome via Playwright's `channel: "chrome"` |
| Browser flags | `--js-flags=--max-old-space-size=8192`, `--disable-dev-shm-usage` — **both tools, identically** |
| Viewport | 1440 x 900; Table 21 varies the height |
| **Tool compared against** | **phylo.io 2.2.5** (2026-01-30, npm `phyloio`), its own published `dist/`, unmodified, sha256 `9f9be045924a…` — the current release at the time of measurement |
| This project | measured at commit 015f70b (`v0.1.0`), 2026-11-01T18:21:44+00:00 to 2026-11-01T23:25:15+00:00 |
| Runtimes | Python 3.12.14 (`uv` 0.12.17), Node 26.3.0, Playwright 1.63.0 |
| Backend database | SQLite, in the store directory |
| Store location | APFS on a solid-state volume, **not** a RAM disk |
| **Backend threads** | **2 of the 10 cores** (`PHYLODELTA_THREADS=2`) |
| MAST budget | `PHYLODELTA_METRIC_MEMORY=16G`, a campaign setting: the code has no default |
| Transport | one origin, one fresh page per measurement; uncompressed except Table 20, which is gzip |
| Power state | recorded, at the start and at the end: Now drawing from 'AC Power' |

**Every figure here comes from one clean clone of the tag above**, by `harness/run_campaign.sh`, on a store built from scratch. The one exception is the 2.1.1 row of the "Highlight BCN" probe, kept as history because that release is no longer the one under test.

**The browser moved, and the record says so.** The campaign recorded Chrome 156.0.8078.47 at its start. Chrome then updated itself to 156.0.8078.74 at 19:23:03 local time, 79 seconds later (the framework's version folder and `Info.plist` carry that time), which was before the first browser step at 20:27. `campaign_env.py` therefore refused at the end, on `browser`, and that refusal stands in `environment.json`. Every browser result records the version that ran it, and all of them read Chrome 156.0.8078.74.

**The ceiling step was run twice.** The ceiling step hung after its 660 s deadline, because `ceiling.mjs` does not close the browser when the deadline fires, and the campaign's Chrome was stopped by hand. Its first pass is kept as `ceiling_first_pass.json`. The rungs from 70,580 up were then measured again, one process each, and those are the rows here.

**Measured after the campaign, from the same tag.** Four checks, each in its own file, which the tables say where they use them: 2,500 leaves run four more times (`accuracy_repeats.json`), the paint runner at 70,580 (`phyloio_paint_extra.json`), the 30-minute run at 70,580 and 564,640 (`endurance_extra.json`), and the comparison given 30 minutes (`phyloio_long_compare.json`).

**The two entries that matter most for checking these numbers** are the browser flags and the phylo.io version. The heap cap decides *where* a tool fails, so Table 1's failures are statements about the tool at an 8 GiB cap, and Table 4's at 16 GiB, not at Chrome's default — and in Table 1 it is raised for both tools, which is what makes a failure the tool's own ceiling. The version matters because several findings are about phylo.io's behaviour: the "Highlight BCN" failure (Table 15) is measured on 2.2.5, and a later release may fix it.

**Headless, throughout.** Rendering in headless Chrome is not identical to a visible window, and these are partly rendering measurements — so this is a real caveat, not a footnote. It applies equally to both tools, so the *comparison* holds; the absolute paint times would need re-taking in a headed browser to be quoted as what a user sees.

**Only 2 of the 10 cores are used for the backend**, deliberately. Table 9 is the measurement behind that choice: at 564,640 leaves two threads give 1.95x at 98% efficiency where ten give 3.98x at 40%, so eight further cores buy the last 2.04x at a steeply falling rate. Every build figure in these tables is therefore what a **two-core** deployment costs, not what this machine can do flat out.

## Which of these to present

23 tables is more than a chapter can carry, and most were made to answer a question that came up rather than to make an argument. Each heading below repeats its tier.

**Present these** — The argument. Drop one and a claim goes unsupported.

- **Table 1** — The headline. Where each tool stops, and the size claim.
- **Table 2** — The caveat Table 1 cannot be read without: this design draws less, and that IS the design. Omitting it is how the earlier 34x mistake happened.
- **Table 3** — Memory is half the claim — flat against growing.
- **Table 5** — Correctness. A fast wrong answer is worth nothing, so the approximation's cost has to be stated.
- **Table 8** — What the design costs. Presenting Table 1 without this is claiming the precompute is free.
- **Table 12** — The mechanism itself — a payload sized to the viewport, flat at every tree size. This is the thesis in one table.
- **Table 13** — The honest ledger. What was given up to get Table 1.
- **Table 14** — Methodology. The rungs above 17,645 are synthetic and the thesis must say so where the numbers are.
- **Table 15** — The other half of interaction: loading is not using. Also carries the finding that the comparison tool's cross-tree jump fails in most page loads.
- **Table 19** — The claim as the quantity it is actually about: bytes over the wire. Present it beside Table 12 — 12 is the mechanism, 19 is what the mechanism buys.
- **Table 21** — The other half of "sized to the viewport". Every other table shows the payload ignoring the tree; only this one shows it following the window, which is what earns the word *sized*.
- **Table 22** — Correctness again, but against implementations that share nothing with this one. Table 18's agreement is with the same paper's own code; this is the check an examiner will ask for.
- **Table 23** — Paint and compare measured apart, three loads a rung, where phylo.io paints but its comparison does not finish in 600 s. Table 1's three † rows come from here.

**Appendix, or one sentence citing the number** — Defends a choice or a stated limit of a PRESENT table.

- **Table 4** — The detail behind Table 1's limits: which are budgets and which are failures, given 30 minutes.
- **Table 9** — Justifies the 2-thread setting every build figure uses. One sentence plus the table in an appendix.
- **Table 11** — The deployability argument: server memory is linear, not quadratic. A sentence with the marginal figure.
- **Table 17** — Why the metric choice is not free, and where §9's claim holds. Relevant only if the thesis discusses metric plugins.
- **Table 18** — Validation: two independent RF implementations in a fixed ratio at every rung. A sentence, with the table in an appendix. Table 22 is the one that pins the scale.
- **Table 20** — Table 19 under compression, which is what a real deployment serves. Answers the first objection anyone will raise to 19, and answers it the other way from the expected one.

**Keep in the repository, do not present** — Real and reproducible, but a PRESENT table already says it or it answered an internal question.

- **Table 6** — Diagnostic. Phase-splitting another tool's time compares phase names that do not mean the same thing; Table 1's paint/compare split is the part that survives.
- **Table 7** — The six samples behind Table 1's PhyloDelta column, with their spread. Belongs in a sentence about method.
- **Table 10** — Subsumed by Table 9, which measures the same trade-off on whole builds rather than one step.
- **Table 16** — The attribution behind Table 15: the round trip is a few milliseconds of a three-frame navigation. One sentence, not a table.

The PRESENT tables answer, in this order: how far each tool gets (1), on comparable work (2), at what memory (3), sending how many bytes (19), sized by what (21), how correctly (5), by what mechanism (12), at what navigation cost (15), for what precompute (8), giving up what (13), measured on what data (14).

*If only one table can be shown, it is 19.* It states the claim in the quantity the claim is about — 27.7 KiB against 33.8 MiB at 564,640 leaves — and it is the only table whose ratio grows without bound while everything on this side stays flat.

*Two tables to read together, not separately:* Table 1 without Table 2 overstates the result, because the tools do not draw the same amount — that asymmetry IS the design, and hiding it is how an earlier version of this comparison reported a 34x that did not exist.

---

## Table 1 — Scalability: where each tool stops

<!-- tier: PRESENT -->
> **PRESENT** — The headline. Where each tool stops, and the size claim.

> **Heap here is MAIN-THREAD ONLY.** `Runtime.getHeapUsage` reads one isolate, and phylo.io computes its comparison in a **Web Worker** with a heap of its own. Where the comparison finishes, the worker's results are copied back and the figure reflects them; where it does not, the column shows only the two parsed trees, which is why it *drops* at 17,645. It is a lower bound, not the tool's memory. Table 4's RSS figures, which cover the whole renderer including workers, are the honest memory numbers.

Cold start to an interactive comparison. Phylo.io is split into *paint* (two trees drawn) and *compare* (its best-corresponding-node worker finished), because only the second is the same job PhyloDelta is doing: a slice arrives with its similarity values already in it.

**PhyloDelta's column is the median of six samples** (Table 7), taken before any phylo.io load had run, not the one sample `ceiling.mjs` takes after each phylo.io attempt. That single sample is not fit to quote: a phylo.io attempt that overruns its deadline leaves its renderer working while PhyloDelta is measured, and one pass of those rows read up to 1.35 s. A second pass, with the same overlap, read at most 0.35 s, so the overlap is the setting of those readings and not an isolated cause. phylo.io is one load per rung, except 17,645, 35,290 and 70,580 (marked †), which are the median of three from Table 23.

*`over 660 s` is the attempt's budget, not a failure of the tool: its renderer was still working when the attempt ended (Table 4). `crashed` is the renderer's own failure. `did not finish in 600 s` is the budget this table gives the comparison; Table 4 gives it 30 minutes.*

| leaves | phylo.io paint | phylo.io compare | phylo.io main-thread heap | PhyloDelta, median of 6 | PhyloDelta heap | PhyloDelta advantage | server precompute |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 1,000 | 0.3 s | 5 s | 26.1 MiB | 0.21 s | 3.6 MiB | **23x** | 2.1 s |
| 2,500 | 0.9 s | 18 s | 95.4 MiB | 0.21 s | 3.6 MiB | **88x** | 2.0 s |
| 5,000 | 1.8 s | 52 s | 277.6 MiB | 0.21 s | 3.6 MiB | **247x** | 2.1 s |
| 10,000 | 4.1 s | 201 s | 1,126.6 MiB | 0.21 s | 3.6 MiB | **965x** | 2.0 s |
| 17,645 † | 8.5 s | **did not finish in 600 s** | 65.7 MiB | 0.21 s | 3.6 MiB | **only PhyloDelta in budget** | 2.6 s |
| 35,290 † | 23.4 s | **did not finish in 600 s** | 119.9 MiB | 0.21 s | 3.6 MiB | **only PhyloDelta in budget** | 3.6 s |
| 70,580 † | 74.9 s | **did not finish in 600 s** | 229.3 MiB | 0.22 s | 3.6 MiB | **only PhyloDelta in budget** | 6.1 s |
| 141,160 | **crashed** | **crashed** | **crashed** | 0.19 s | 3.6 MiB | **only PhyloDelta in budget** | 16.8 s |
| 282,320 | **crashed** | **crashed** | **crashed** | 0.21 s | 3.6 MiB | **only PhyloDelta in budget** | 60.3 s |
| 564,640 | **over 660 s** | **over 660 s** | **over 660 s** | 0.21 s | 3.6 MiB | **only PhyloDelta in budget** | 242.4 s |

## Table 2 — What each tool actually drew

<!-- tier: PRESENT -->
> **PRESENT** — The caveat Table 1 cannot be read without: this design draws less, and that IS the design. Omitting it is how the earlier 34x mistake happened.

The check that makes Table 1 admissible. An earlier comparison in this project reported a ~34x speedup that was an artefact of the two tools rendering 91 and 2,002 nodes. **Both tools draw a roughly constant amount** — so the difference in Table 1 is not "one of them drew less".

> The 17,645, 35,290 and 70,580 rows show phylo.io's **pre-comparison** render, the median of three loads: when the worker finishes it rebuilds and redraws both panels with the similarity colouring, and where it never finishes that second render never happens. That is why the counts drop at 17,645. The point of the table is unaffected — the counts stay in one range, never proportional to the tree. Node counts are CDP's `domCounters` in every row.

| leaves | phylo.io SVG paths | phylo.io DOM nodes | PhyloDelta canvases | PhyloDelta tips drawn |
|---:|---:|---:|---:|---|
| 1,000 | 918 | 8,908 | 16 | 50 per panel |
| 2,500 | 1,126 | 9,662 | 16 | 50 per panel |
| 5,000 | 1,166 | 9,836 | 16 | 50 per panel |
| 10,000 | 1,254 | 10,166 | 16 | 50 per panel |
| 17,645 | 670 | 6,921 | 16 | 50 per panel |
| 35,290 | 640 | 6,506 | 16 | 50 per panel |
| 70,580 | 1,036 | 7,962 | 16 | 50 per panel |
| 141,160 | crashed | crashed | 16 | 50 per panel |
| 282,320 | crashed | crashed | 16 | 50 per panel |
| 564,640 | over 660 s | over 660 s | 16 | 50 per panel |

## Table 3 — Memory, and why it grows for one tool and not the other

<!-- tier: PRESENT -->
> **PRESENT** — Memory is half the claim — flat against growing.

Phylo.io's DOM is flat while its heap climbs steeply: it **models the whole tree** in the browser, and on top of that holds MinHash sketches and a score per node, which scale with the *comparison* rather than with the tree. PhyloDelta never receives the tree at all.

Rows where the comparison did not finish are marked — their figure excludes the worker entirely and must not be read as a decrease.

| leaves | phylo.io main-thread heap | growth vs previous | PhyloDelta heap |
|---:|---:|---:|---:|
| 1,000 | 26.1 MiB | — | 3.6 MiB |
| 2,500 | 95.4 MiB | 3.65x | 3.6 MiB |
| 5,000 | 277.6 MiB | 2.91x | 3.6 MiB |
| 10,000 | 1,126.6 MiB | 4.06x | 3.6 MiB |
| 17,645 | 65.7 MiB *(compare unfinished — worker excluded)* | — | 3.6 MiB |
| 35,290 | 119.9 MiB *(compare unfinished — worker excluded)* | — | 3.6 MiB |
| 70,580 | 229.3 MiB *(compare unfinished — worker excluded)* | — | 3.6 MiB |
| 141,160 | — *(crashed)* | — | 3.6 MiB |
| 282,320 | — *(crashed)* | — | 3.6 MiB |
| 564,640 | — *(over 660 s)* | — | 3.6 MiB |

## Table 4 — Failure behaviour, given 30 minutes and 16 GiB

<!-- tier: SUPPORT -->
> **SUPPORT** — The detail behind Table 1's limits: which are budgets and which are failures, given 30 minutes.

Table 1's limits are against a stated budget. This lifts it: 30 minutes with a 16 GiB heap cap on a 24 GiB machine.

| leaves | outcome | time | peak renderer (MiB) |
|---:|---|---:|---:|
| 70,580 | painted in 75 s; **comparison unfinished when the page's own 600 s wait ended** | 11.2 min | 9,743 MiB |
| 141,160 | **renderer process crashed** | 4.5 min | 10,392 MiB |
| 282,320 | **renderer process crashed** | 7.5 min | 10,289 MiB |
| 564,640 | **nothing painted when the 30 minutes ended** | 30.0 min | 10,657 MiB |

*Peak memory is sampled every 2 s from process RSS, so it is a lower bound and the figures should not be read as an ordering.*

*The tag's `endurance.mjs` lifts the budget for the load as a whole, not for the comparison inside it: it calls the page's `load()` without a compare budget, and that defaults to 600 s. Its `ok` therefore does not mean the comparison finished, which is why this table reads `compareComplete`.*

**The comparison itself, given 30 minutes.** The same page, with `load()` told 1,800 s. One load per rung, run after the campaign from the same tag.

| leaves | paint | comparison | time | peak renderer (MiB) |
|---:|---:|---|---:|---:|
| 17,645 | 8.7 s | **unfinished at 30 minutes** | 30.2 min | 3,492 MiB |
| 35,290 | 22.3 s | **unfinished at 30 minutes** | 30.4 min | 6,677 MiB |
| 70,580 | 73.7 s | **unfinished at 30 minutes** | 31.2 min | 9,446 MiB |

**Thirty minutes changes nothing at these rungs.** None of the three comparisons finished, and no renderer crashed. The tag's `endurance.mjs` was run with its one `load()` call given 1,800,000 ms, a 35-minute outer limit and its own output file. This cannot tell a very slow comparison from one that never ends. The step from 201 s at 10,000 leaves to over 1,800 s at 17,645 is far steeper than the 3x to 4x per doubling below it, and 17,645 is also the first rung with an unshared leaf (Table 14). That coincidence was not tested.


## Table 5 — Accuracy: what the LSH approximation costs

<!-- tier: PRESENT -->
> **PRESENT** — Correctness. A fast wrong answer is worth nothing, so the approximation's cost has to be stated.

Phylo.io finds each clade's best corresponding node by maximising Jaccard over **ten candidates** retrieved by MinHash/LSH (`worker_bcn.js`). This project maximises over every node, so it is an upper bound and every gap is a retrieval miss. Run on pairs with **identical leaf sets**, so a difference cannot be explained by unmatched-leaf handling.

| leaves | clades | exact match | missed | median gap | worst gap | beat exact |
|---:|---:|---:|---:|---:|---:|---:|
| 1,000 | 998 | 947 (94.9%) | 51 (5.1%) | 0.138 | 0.700 | 0 |
| 2,500 | 2,498 | 2,384 (95.4%) | 114 (4.6%) | 0.167 | 0.764 | 0 |
| 5,000 | 4,998 | 4,772 (95.5%) | 226 (4.5%) | 0.167 | 0.584 | 0 |
| 10,000 | 9,996 | 9,528 (95.3%) | 468 (4.7%) | 0.125 | 0.781 | 0 |

*`beat exact` must be 0: an exhaustive search cannot be beaten by a subset of the same candidates. It is reported as a check on the method, not as a result.*

*`clades` is the clades both sides scored. A clade phylo.io leaves unscored has no gap to compare, so it drops out here.*

**The same pair, five times.** At 2,500 leaves phylo.io was run five times on one input, with the same code: the campaign's run and four more after it. It missed 114, 105, 144, 113, 163 clades, so **4.2% to 6.5%**, and its worst gap ranged from 0.532 to 0.995. Between the first run and each later one only 2,285 to 2,324 of the 2,499 clade scores were identical. Its comparison is not deterministic, so every row above is one draw. The clade count moves with it: it scored 2,497 to 2,498 of the 2,499 clades, the root being unscored in every run, which is the 2,498 here against the 2,493 of the earlier run.


## Table 6 — Where phylo.io's time goes

<!-- tier: WORKING -->
> **WORKING** — Diagnostic. Phase-splitting another tool's time compares phase names that do not mean the same thing; Table 1's paint/compare split is the part that survives.

Its own phase split. Parsing and drawing are cheap and near-linear; **the comparison is what scales badly** — which is the same finding as this project's own correspondence search being the quadratic step (DECISIONS §17), reached independently by both implementations.

| leaves | parse | layout | paint | compare | compare as % of total |
|---:|---:|---:|---:|---:|---:|
| 1,000 | 0.02 s | 0.15 s | 0.18 s | 5 s | 93% |
| 2,500 | 0.04 s | 0.32 s | 0.53 s | 18 s | 95% |
| 5,000 | 0.09 s | 0.71 s | 0.95 s | 52 s | 97% |
| 10,000 | 0.23 s | 1.94 s | 1.89 s | 201 s | 98% |
| 17,645 | 0.52 s | 4.68 s | 3.52 s | **>600 s** | — |
| 35,290 | 1.00 s | 15.25 s | 7.21 s | **>600 s** | — |
| 70,580 | 2.05 s | 54.40 s | 18.41 s | **>600 s** | — |
| 141,160 | — | — | — | **crashed** | — |
| 282,320 | — | — | — | **crashed** | — |
| 564,640 | — | — | — | **over 660 s** | — |

## Table 7 — PhyloDelta, repeated

<!-- tier: WORKING -->
> **WORKING** — The six samples behind Table 1's PhyloDelta column, with their spread. Belongs in a sentence about method.

Six samples per rung after a discarded warm-up: the source of Table 1's PhyloDelta column.

| leaves | nodes | median | min | max | heap |
|---:|---:|---:|---:|---:|---:|
| 1,000 | 1,999 | **0.21 s** | 0.20 s | 0.23 s | 3.6 MiB |
| 2,500 | 4,999 | **0.21 s** | 0.19 s | 0.22 s | 3.6 MiB |
| 5,000 | 9,999 | **0.21 s** | 0.19 s | 0.23 s | 3.6 MiB |
| 10,000 | 19,999 | **0.21 s** | 0.19 s | 0.23 s | 3.6 MiB |
| 17,645 | 35,289 | **0.21 s** | 0.20 s | 0.22 s | 3.6 MiB |
| 35,290 | 70,579 | **0.21 s** | 0.21 s | 0.23 s | 3.6 MiB |
| 70,580 | 141,159 | **0.22 s** | 0.19 s | 0.22 s | 3.6 MiB |
| 141,160 | 282,319 | **0.19 s** | 0.19 s | 0.21 s | 3.6 MiB |
| 282,320 | 564,639 | **0.21 s** | 0.19 s | 0.22 s | 3.6 MiB |
| 564,640 | 1,129,279 | **0.21 s** | 0.19 s | 0.22 s | 3.6 MiB |

## Table 8 — The precompute PhyloDelta pays instead

<!-- tier: PRESENT -->
> **PRESENT** — What the design costs. Presenting Table 1 without this is claiming the precompute is free.

Measured through the real upload path: POST the bundle, a worker claims it, poll until ready. Includes ingest, reconciliation, the correspondence search and the metrics asked for. **Twice**, because the two answers differ: (a) `rf` alone, which is what `DEFAULT_UPLOAD_METRICS` builds; (b) `rf,mast`, which is what the app's upload form sends by default, with MAST run where its memory estimate fits the budget and declined where it does not. Each build's metrics are read back from the pair.

| leaves | (a) `rf`, 2 threads | (a) `rf`, 10 threads | (b) `rf,mast`, 2 threads | MAST in (b) | bundle size |
|---:|---:|---:|---:|---|---:|
| 1,000 | **2.1 s** | 2.1 s | 2.1 s | computed | 0.0 MiB |
| 2,500 | **2.0 s** | 2.1 s | 2.1 s | computed | 0.0 MiB |
| 5,000 | **2.1 s** | 2.1 s | 2.6 s | computed | 0.1 MiB |
| 10,000 | **2.0 s** | 2.1 s | 3.1 s | computed | 0.2 MiB |
| 17,645 | **2.6 s** | 2.6 s | 6.2 s | computed | 1.1 MiB |
| 35,290 | **3.6 s** | 2.6 s | 17.4 s | computed | 2.0 MiB |
| 70,580 | **6.1 s** | 4.1 s | 6.2 s | declined (needs ~18.6 GiB, an estimate) | 4.1 MiB |
| 141,160 | **16.8 s** | 8.4 s | 17.4 s | declined (needs ~74.2 GiB, an estimate) | 8.2 MiB |
| 282,320 | **60.3 s** | 24.8 s | 59.8 s | declined (needs ~296.9 GiB, an estimate) | 16.7 MiB |
| 564,640 | **242.4 s** | 118.8 s | 243.7 s | declined (needs ~1187.7 GiB, an estimate) | 33.8 MiB |

*The ~2 s floor at small sizes is the worker's poll interval, not work.*

## Table 9 — Build time at pinned thread counts

<!-- tier: SUPPORT -->
> **SUPPORT** — Justifies the 2-thread setting every build figure uses. One sentence plus the table in an appendix.

The same builds with the count pinned, `rf` only, through the same upload path, each on its own store. **Every row read its thread count back from the pair it built**, and the run refuses if the answer differs: 30 builds, none of them refused.

| leaves | 1 thread | 2 threads | 10 threads | 2 vs 1 | 10 vs 1 |
|---:|---:|---:|---:|---:|---:|
| 1,000 *(floor-limited — ratios are noise)* | 1.6 s | 2.1 s | 2.1 s | 0.75x | 0.75x |
| 2,500 *(floor-limited — ratios are noise)* | 2.0 s | 2.0 s | 2.1 s | 1.00x | 0.99x |
| 5,000 *(floor-limited — ratios are noise)* | 2.0 s | 2.1 s | 2.1 s | 0.99x | 0.98x |
| 10,000 *(floor-limited — ratios are noise)* | 2.6 s | 2.0 s | 2.1 s | 1.25x | 1.23x |
| 17,645 *(floor-limited — ratios are noise)* | 2.6 s | 2.6 s | 2.6 s | 1.00x | 0.99x |
| 35,290 | 4.1 s | 3.6 s | 2.6 s | 1.14x | 1.58x |
| 70,580 | 10.6 s | 6.1 s | 4.1 s | 1.74x | 2.58x |
| 141,160 | 30.4 s | 16.8 s | 8.4 s | 1.81x | 3.63x |
| 282,320 | 116.4 s | 60.3 s | 24.8 s | 1.93x | 4.70x |
| 564,640 | 473.5 s | 242.4 s | 118.8 s | 1.95x | 3.98x |

**Read the larger rows.** From 35,290 to 564,640 two threads rise 1.14x -> 1.95x and ten 1.58x -> 3.98x, peaking at 4.70x, so the ten-thread gain is not monotone at the top of the ladder. The gain grows with size because below ~70,000 leaves the *serial* parts — parse, reconcile, ingest, and the 2 s poll — are most of the elapsed time, and threading the search cannot touch them. Amdahl's law, visible directly.

**What to choose.** At 564,640 leaves two threads give 1.95x at 98% efficiency; ten give 3.98x at 40%. One thread wastes a near-free doubling. If efficiency is the objective, **two is the sweet spot** — but latency for a single comparison favours more threads, and throughput for a queue favours fewer per build with more builds at once. `PHYLODELTA_THREADS` exists so a deployment can choose; there is no single best value.

## Table 10 — Thread scaling of the parallel step

<!-- tier: WORKING -->
> **WORKING** — Subsumed by Table 9, which measures the same trade-off on whole builds rather than one step.

**Only one step of the build is parallel**: the clade-correspondence search. It is driven directly here rather than timed through a whole build, which would dilute it with the single-threaded parse, reconciliation and metric around it. 70,580 leaves, best of 3 runs.

| threads | time | speedup | efficiency | result identical to 1 thread |
|---:|---:|---:|---:|:--:|
| 1 | 6.70 s | 1.00x | 100% | yes |
| 2 | 3.63 s | 1.84x | 92% | yes |
| 3 | 2.61 s | 2.57x | 86% | yes |
| 4 | 2.04 s | 3.28x | 82% | yes |
| 6 | 1.76 s | 3.81x | 64% | yes |
| 8 | 1.57 s | 4.26x | 53% | yes |
| 10 | 1.44 s | 4.66x | 47% | yes |

**The last column is the one that matters.** Each index's result depends only on read-only inputs, so it must be bit-identical whatever the thread count. A race here would not crash — it would quietly return a slightly wrong best corresponding node, which no timing figure would reveal.

The knee is at **4 threads**, the number of performance cores on this machine. One to 4 threads buys 3.28x at 82% efficiency; 4 to 10 buys only another 1.42x and drops efficiency to 47%. On a shared machine 4 threads is the better trade: 1.4x slower than 10, for 2.5x fewer cores.

## Table 11 — What the server needs while it builds

<!-- tier: SUPPORT -->
> **SUPPORT** — The deployability argument: server memory is linear, not quadratic. A sentence with the marginal figure.

Peak RSS of the worker process, sampled every 200 ms against its idle baseline of 70 MiB. Measured in a throwaway store so nothing else was disturbed.

**The search is quadratic in time but LINEAR in memory** — every doubling of leaves roughly doubles the footprint. The pruning bound means it never materialises an n x n matrix: it holds the two trees' columns, which are memory-mapped, and one scratch buffer per thread. For contrast, building these trees with NJ would need ~466 GiB of distance matrix at 500,000 taxa.

Both thread settings are shown, compared on **absolute peak RSS**, the figure neither idle baseline can distort.

| leaves | peak RSS (2 thr, MiB) | peak RSS (10 thr, MiB) | difference | marginal (2 thr) | growth |
|---:|---:|---:|---:|---:|---:|
| 1,000 | **73 MiB** | 73 MiB | +0% | 4 MiB | — |
| 2,500 | **73 MiB** | 77 MiB | +5% | 4 MiB | 1.00x |
| 5,000 | **81 MiB** | 77 MiB | -5% | 11 MiB | 3.14x |
| 10,000 | **88 MiB** | 83 MiB | -6% | 19 MiB | 1.68x |
| 17,645 | **109 MiB** | 112 MiB | +3% | 39 MiB | 2.07x |
| 35,290 | **153 MiB** | 155 MiB | +1% | 84 MiB | 2.13x |
| 70,580 | **232 MiB** | 234 MiB | +1% | 163 MiB | 1.94x |
| 141,160 | **408 MiB** | 409 MiB | +0% | 339 MiB | 2.08x |
| 282,320 | **710 MiB** | 709 MiB | -0% | 641 MiB | 1.89x |
| 564,640 | **1,316 MiB** | 1,292 MiB | -2% | 1,246 MiB | 1.95x |

**The thread count barely affects memory.** From 17,645 leaves up the two runs differ by at most 3%, in no fixed direction. The per-thread scratch buffers are small against the memory-mapped columns. Below that the peaks sit a few MiB above idle and the 200 ms sampling decides the sign of the difference.

*Every byte figure in these tables is binary — KiB, MiB, GiB (2^10, 2^20, 2^30). `ps -o rss` reports KiB natively; heap and transfer counts are raw byte counts divided by 2^20. Mixing decimal and binary is how a table comes to state two different things under one heading, and this one did for a while.*

*Build times are omitted here. This run measures memory, and Table 8's figures are the ones to quote for time.*

## Table 12 — The request a panel actually makes

<!-- tier: PRESENT -->
> **PRESENT** — The mechanism itself — a payload sized to the viewport, flat at every tree size. This is the thesis in one table.

The **cause**, where every other table shows the consequence. The same GET the frontend issues, at every tree size, read-only. Latency and payload are set by the viewport budget, so neither tracks the tree: **565x more leaves, the same few milliseconds and the same few kilobytes.**

Measured twice: on the `rf` store, and with `metric=mast` on the store built the way the app uploads. Where MAST was declined the pair has no such metric and the server says so by name.

| leaves | median | min | max | response | gzip | leaves drawn | `metric=mast` median | response | gzip |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1,000 | **1.7 ms** | 1.6 ms | 1.9 ms | 5.4 KiB | 1.5 KiB | 50 | 1.7 ms | 5.3 KiB | 1.7 KiB |
| 2,500 | **1.6 ms** | 1.6 ms | 1.9 ms | 5.5 KiB | 1.6 KiB | 50 | 1.6 ms | 5.5 KiB | 1.8 KiB |
| 5,000 | **1.6 ms** | 1.6 ms | 1.7 ms | 5.7 KiB | 1.7 KiB | 50 | 1.7 ms | 5.7 KiB | 1.8 KiB |
| 10,000 | **1.7 ms** | 1.6 ms | 1.7 ms | 5.7 KiB | 1.7 KiB | 50 | 1.6 ms | 5.7 KiB | 1.8 KiB |
| 17,645 | **1.6 ms** | 1.6 ms | 1.7 ms | 6.9 KiB | 2.6 KiB | 50 | 1.6 ms | 7.0 KiB | 2.8 KiB |
| 35,290 | **1.6 ms** | 1.5 ms | 1.7 ms | 6.9 KiB | 2.6 KiB | 50 | 1.6 ms | 7.0 KiB | 2.8 KiB |
| 70,580 | **1.6 ms** | 1.6 ms | 1.6 ms | 6.8 KiB | 2.5 KiB | 50 | declined | — | — |
| 141,160 | **1.6 ms** | 1.6 ms | 1.7 ms | 6.7 KiB | 2.4 KiB | 50 | declined | — | — |
| 282,320 | **1.6 ms** | 1.6 ms | 1.7 ms | 6.5 KiB | 2.1 KiB | 50 | declined | — | — |
| 564,640 | **1.6 ms** | 1.6 ms | 1.7 ms | 6.0 KiB | 1.6 KiB | 50 | declined | — | — |

*From 1,000 to 564,640 leaves — a 565x increase — the median moves 1.7 ms to 1.6 ms and the payload 5.4 KiB to 6.0 KiB. Seven samples per rung after a warm-up, since the first touch of a store memory-maps it.*

## Table 13 — What the design costs

<!-- tier: PRESENT -->
> **PRESENT** — The honest ledger. What was given up to get Table 1.

| | phylo.io | PhyloDelta |
|---|---|---|
| Server required | no | **yes** |
| Precompute before first view | none | up to 242 s at 2 threads, `rf` alone; 244 s as the app uploads it |
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

*Read from the Newick text by `tools/ladder_stats.py`, not through the parser under test. Depth is edges from the root to the deepest leaf. Tree a is NJ and tree b UPGMA.*

| rung | leaves a | leaves b | shared | clades a | clades b | depth a | depth b |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 1,000 | 1,000 | 1,000 | 100.0000% | 999 | 999 | 79 | 68 |
| 2,500 | 2,500 | 2,500 | 100.0000% | 2,499 | 2,499 | 97 | 130 |
| 5,000 | 5,000 | 5,000 | 100.0000% | 4,999 | 4,999 | 110 | 181 |
| 10,000 | 10,000 | 10,000 | 100.0000% | 9,999 | 9,999 | 144 | 296 |
| 17,645 | 17,645 | 17,646 | 99.9943% | 17,645 | 17,645 | 176 | 443 |
| 35,290 | 35,290 | 35,292 | 99.9943% | 35,291 | 35,291 | 177 | 444 |
| 70,580 | 70,580 | 70,584 | 99.9943% | 70,583 | 70,583 | 179 | 446 |
| 141,160 | 141,160 | 141,168 | 99.9943% | 141,167 | 141,167 | 183 | 450 |
| 282,320 | 282,320 | 282,336 | 99.9943% | 282,335 | 282,335 | 191 | 458 |
| 564,640 | 564,640 | 564,672 | 99.9943% | 564,671 | 564,671 | 207 | 474 |

*Pruned rungs share 100% of their leaves. From 17,645 up one real leaf, ST 211, is in the UPGMA tree only (§2.6) and every nested copy carries it, so 99.9943% is shared and 32 leaves are not at the top rung. PhyloDelta reconciles them away; phylo.io is handed them. Depth runs 79 to 207 on the NJ side and 68 to 474 on the UPGMA side. Real MLST data stops at 27,962 leaves (clostridium), so rungs above 17,645 are synthetic and are used only for performance claims.*

## Table 15 — Navigation responsiveness, once the comparison is open

<!-- tier: PRESENT -->
> **PRESENT** — The other half of interaction: loading is not using. Also carries the finding that the comparison tool's cross-tree jump fails in most page loads.

*Median milliseconds from the action to a painted result, with the frame count at 16.67 ms beside it, up to 8 operations per cell after up to 3 discarded warm-ups, one page load per tool per rung.*

**Every figure here is a frame count.** The clock stops after two nested `requestAnimationFrame` callbacks, so a sample is quantised to the display, and a 2 ms difference in real work moves it a whole frame (§34.14). The gap between the two tools cannot be resolved by this harness. The claim that survives is that both answer well inside the 100 ms an interaction is allowed.

| leaves | phylo.io expand | phylo.io back | phylo.io jump | PhyloDelta expand | PhyloDelta back | PhyloDelta jump |
|---:|---:|---:|---:|---:|---:|---:|
| 1,000 | 31.3 ms (2 f) n=8 | 31.5 ms (2 f) n=8 | **fails** | 49.3 ms (3 f) n=8 | 49.3 ms (3 f) n=8 | 48.8 ms (3 f) n=7 |
| 2,500 | 31.2 ms (2 f) n=8 | 31.1 ms (2 f) n=8 | **fails** | 49.2 ms (3 f) n=8 | 49.3 ms (3 f) n=8 | 49.2 ms (3 f) n=8 |
| 5,000 | 31.6 ms (2 f) n=8 | 31.7 ms (2 f) n=8 | **fails** | 49.3 ms (3 f) n=8 | 49.3 ms (3 f) n=8 | 49.2 ms (3 f) n=8 |
| 10,000 | 30.6 ms (2 f) n=8 | 32.8 ms (2 f) n=8 | **fails** | 49.3 ms (3 f) n=8 | 49.3 ms (3 f) n=8 | 49.2 ms (3 f) n=8 |
| 17,645 | *no comparison* | *no comparison* | *no comparison* | 49.3 ms (3 f) n=8 | 49.2 ms (3 f) n=8 | 49.5 ms (3 f) n=8 |

**"No comparison" is not slow navigation.** phylo.io paints both trees at 17,645 leaves but its best-corresponding-node worker never finishes there inside the 600 s budget (Tables 1 and 23), so in compare mode there is nothing to navigate. Its navigation is therefore measurable only to **10,000 leaves**, where the comparison completes in 201 s. PhyloDelta is measured at 17,645 anyway, because holding flat is the claim.

**Both tools are driven one layer below the click** — phylo.io through `container.trigger_(action, …)`, which is exactly what its context-menu items call, and PhyloDelta through the actions its menu items call. Synthesising a click on a WebGL canvas would have charged hit-testing to one side only. What is excluded is the same for both: opening a menu and pressing an item.

**The operations are not equivalent in what they reveal.** phylo.io holds the whole tree, so it collapses and expands clades of 923 to 10,000 leaves and draws all of them. PhyloDelta's targets are the wedges in the current slice, 13,349 leaves down to 41, and expanding one draws about fifty tips.


## Table 16 — Where a PhyloDelta navigation's time goes

<!-- tier: WORKING -->
> **WORKING** — The attribution behind Table 15: the round trip is a few milliseconds of a three-frame navigation. One sentence, not a table.

*Fetch times are Resource Timing, so they are not quantised to the frame. A jump is one request, `/slice?around=` (§40); the expand and back fetches are the requests inside the step.*

| leaves | expand total | of which fetch | back total | of which fetch | back, cache emptied | of which fetch | jump total | of which fetch |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1,000 | 49.3 ms | 3.2 ms | 49.3 ms | 0.0 ms | 48.9 ms | 3.2 ms | 48.8 ms | 3.0 ms |
| 2,500 | 49.2 ms | 3.5 ms | 49.3 ms | 0.0 ms | 48.9 ms | 3.5 ms | 49.2 ms | 3.0 ms |
| 5,000 | 49.3 ms | 3.5 ms | 49.3 ms | 0.0 ms | 49.0 ms | 3.3 ms | 49.2 ms | 3.0 ms |
| 10,000 | 49.3 ms | 3.4 ms | 49.3 ms | 0.0 ms | 48.9 ms | 3.5 ms | 49.2 ms | 3.0 ms |
| 17,645 | 49.3 ms | 3.5 ms | 49.2 ms | 0.0 ms | 49.0 ms | 3.5 ms | 49.5 ms | 3.0 ms |

*Cached and uncached are interleaved in one page against the same target, because measuring them in separate browsers reported the uncached run as three times FASTER — the first run was paying for a cold server and the second inherited a warm one. The uncached pass runs first, so any residual warming works against the cache.*

**The cache works and it barely matters.** On a hit the network cost of a navigation is **0 ms**, which is the cache doing exactly its job — and the navigation takes the same total time, because the round trip was never the cost. An uncached fetch is 3.2–3.5 ms of a ~49 ms navigation, and the remainder is two frames of detector plus building the tree and drawing it. Every headline figure in Tables 1–14 was measured with no caching at all, so they are a floor rather than a best case.


### Table 15 note — phylo.io's "Highlight BCN" is intermittent

All 32 attempts in the navigation run above failed, at each of the 4 rungs with a comparison, with the same error:

> `Cannot read properties of null (reading '_children')`

**But that is one page load per rung, and the failure is intermittent.** A dedicated probe over repeated loads of the same pair at 1,000 leaves:

| phylo.io | page loads | loads where the jump worked | attempts succeeded |
|---|---:|---:|---:|
| 2.1.1 | 8 | 0 | 0/80 |
| 2.2.5 | 8 | 1 | 3/120 |

The honest claim is that the jump fails in most loads, not that it never works. It is **not** all-or-nothing within a load: in the 1 of 8 loads where it worked at all, 3 of 15 attempts succeeded. Table 15 reports one load per rung, which is why it shows only the common outcome.

**The mechanism, and why it is conditional.** It is reached only from the context-menu item of that name (`viewer.js` line 1175 is the sole caller). `api.js` builds **two separate models** from the BCN worker's reply, and the `elementBCN` references inside the first point at that reply's own embedded copy of the second tree. `getHierarchyNodeFromModelNode` compares by object identity, so whether it finds anything depends on whether structured-clone identity between the two halves of one message survives into the rebuilt models — which is evidently not guaranteed. When it does not, the lookup returns null and `expandToRoot` hands that null to `apply_collapse_from_data_to_d3`, which reads `_children` on it.

The ceiling was measured directly on 2.2.5: at **17,645 leaves** a further load's comparison **did not complete** inside a 600 s budget. That is the one claim the whole of Table 1 rests on.

It still sharpens the comparison rather than softening it: the cross-tree jump is the operation PhyloDelta's design is most open to criticism over — it costs a slice the panel has never held — and it is the one the comparison tool manages only sometimes.



## Table 17 — Does the chosen metric change what a build costs?

<!-- tier: SUPPORT -->
> **SUPPORT** — Why the metric choice is not free, and where §9's claim holds. Relevant only if the thesis discusses metric plugins.

*Seconds, from the worker's own per-metric timings at `PHYLODELTA_THREADS=2`. "Shared" is what every metric in a set pays once: parse, reconcile, correspondence, store.*

| leaves | shared work | rf | rf-treediff | triplet | total | metrics as % of total |
|---:|---:|---:|---:|---:|---:|---:|
| 1,000 | 0.0 s | 0.0 s | 0.0 s | 0.3 s | 0.4 s | *n/a* |
| 2,500 | 0.1 s | 0.0 s | 0.0 s | 0.1 s | 0.1 s | *n/a* |
| 5,000 | 0.1 s | 0.0 s | 0.0 s | 0.1 s | 0.3 s | *n/a* |
| 10,000 | 0.2 s | 0.0 s | 0.0 s | 0.4 s | 0.7 s | *n/a* |
| 17,645 | 0.4 s | 0.0 s | 0.1 s | 1.2 s | 1.7 s | 76% |
| 35,290 | 1.1 s | 0.1 s | 0.1 s | 2.7 s | 4.1 s | 71% |
| 70,580 | 3.9 s | 0.1 s | 0.2 s | 5.8 s | 10.2 s | 60% |
| 141,160 | 14.5 s | 0.3 s | 0.5 s | 12.3 s | 27.7 s | 47% |
| 282,320 | 56.9 s | 0.5 s | 0.9 s | 25.4 s | 84.2 s | 32% |
| 564,640 | 238.4 s | 1.0 s | 2.0 s | 53.1 s | 295.3 s | 19% |

**The answer reverses with size, so "does the metric matter" has no single answer.** `rf` and `rf-treediff` are free at every scale — together 3.0 s of a 295 s build at 564,640 leaves. `triplet` is not: at 141,160 it costs 12.3 s against 14.5 s for all the shared work, very nearly doubling the build. By 564,640 `triplet` alone has fallen back to 18% of the build (the table's last column counts all three metrics together), because the shared work is O(n^2) and the metric is near-linear, so correspondence overtakes it.

So §9's claim that several metrics cost little more than one is **true asymptotically and misleading in the middle** — which is where most real trees sit. The claim should be stated about the *shared* work, which is what is actually shared, rather than about metrics in general.

**Measured from the worker's log, not from wall-clock differences.** The three metric sets are uploaded in a fixed order, so the "+triplet" build is always last, and the first pass showed it at a suspiciously uniform 1.7-2x the others — the shape of an ordering artefact rather than a cost. Per-metric timings carry no such confound.

*The shared work at 564,640 leaves here, 238.4 s, sits beside Table 9's 242.4 s for a whole `rf` build at two threads: the same work, from the worker's log and from the wall clock.*


## Table 18 — Two RF implementations against each other

<!-- tier: SUPPORT -->
> **SUPPORT** — Validation: two independent RF implementations in a fixed ratio at every rung. A sentence, with the table in an appendix. Table 22 is the one that pins the scale.

| leaves | built-in `rf` | `rf-treediff` | x2 | as expected |
|---:|---:|---:|---:|:---:|
| 1,000 | 1,062 | 531 | 1,062 | yes |
| 2,500 | 2,438 | 1,219 | 2,438 | yes |
| 5,000 | 4,414 | 2,207 | 4,414 | yes |
| 10,000 | 8,226 | 4,113 | 8,226 | yes |
| 17,645 | 13,650 | 6,825 | 13,650 | yes |
| 35,290 | 27,300 | 13,650 | 27,300 | yes |
| 70,580 | 54,600 | 27,300 | 54,600 | yes |
| 141,160 | 109,200 | 54,600 | 109,200 | yes |
| 282,320 | 218,400 | 109,200 | 218,400 | yes |
| 564,640 | 436,800 | 218,400 | 436,800 | yes |

*20 of 20 builds match `rf == 2 x rf-treediff`.* Different algorithms over different representations by different authors — TreeDiff is the reference implementation of the paper this project follows (§1.10) — so agreement at 1,129,279 nodes is a check on both, and a disagreement would have meant one of them was wrong.

**What this table cannot check is the scale**, which is why Table 22 exists. TreeDiff reports half the symmetric difference and this store used to do the same; the two agreed at every rung while both differed from the published definition by a factor of two, and nothing here could have revealed it. Agreement between two implementations of one paper is evidence that the code is faithful, not that the quantity is the one the field means.


## Table 19 — Bytes over the wire

<!-- tier: PRESENT -->
> **PRESENT** — The claim as the quantity it is actually about: bytes over the wire. Present it beside Table 12 — 12 is the mechanism, 19 is what the mechanism buys.

*"Never send the whole tree" is a claim about transferred bytes. Measured from the wire — `request.sizes()` per response, not file sizes on disk — uncompressed on both sides, one origin.*

**Application and data are separate columns on purpose.** PhyloDelta ships a bundle too, and quoting its slices against phylo.io's whole-tree download while ignoring that would be comparing a partial cost with a total one — the error Table 2 exists to prevent. Add the columns as you see fit; the application bytes are paid once per visit, the data bytes once per comparison.

**The last two columns are the app's own path**: the store built with `rf,mast`, as its upload form does. The slices carried MAST where the query says `metric=mast`, read from the request itself; where MAST was declined the app falls back to `rf`.

| leaves | phylo.io app | phylo.io data | phylo.io total | PhyloDelta app | PhyloDelta data | PhyloDelta total | data ratio | total ratio | data, app path | slice carried MAST |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|:---:|
| 1,000 | 7.91 MiB | 0.02 MiB | 7.93 MiB | 0.49 MiB | **26.2 KiB** | 0.52 MiB | **1x** | 15x | 26.9 KiB | yes |
| 2,500 | 7.91 MiB | 0.04 MiB | 7.95 MiB | 0.49 MiB | **26.5 KiB** | 0.52 MiB | **2x** | 15x | 27.2 KiB | yes |
| 5,000 | 7.91 MiB | 0.08 MiB | 7.99 MiB | 0.49 MiB | **27.1 KiB** | 0.52 MiB | **3x** | 15x | 27.8 KiB | yes |
| 10,000 | 7.91 MiB | 0.16 MiB | 8.07 MiB | 0.49 MiB | **27.4 KiB** | 0.52 MiB | **6x** | 16x | 28.2 KiB | yes |
| 17,645 | 7.91 MiB | 1.06 MiB | 8.97 MiB | 0.49 MiB | **30.1 KiB** | 0.52 MiB | **36x** | 17x | 30.9 KiB | yes |
| 35,290 | 7.91 MiB | 1.98 MiB | 9.89 MiB | 0.49 MiB | **30.0 KiB** | 0.52 MiB | **67x** | 19x | 30.9 KiB | yes |
| 70,580 | 7.91 MiB | 4.05 MiB | 11.97 MiB | 0.49 MiB | **29.8 KiB** | 0.52 MiB | **139x** | 23x | 30.0 KiB | no |
| 141,160 | 7.91 MiB | 8.21 MiB | 16.12 MiB | 0.49 MiB | **29.5 KiB** | 0.52 MiB | **285x** | 31x | 29.7 KiB | no |
| 282,320 | 7.91 MiB | 16.69 MiB | 24.60 MiB | 0.49 MiB | **28.9 KiB** | 0.52 MiB | **591x** | 47x | 29.1 KiB | no |
| 564,640 | 7.91 MiB | 33.84 MiB | 41.76 MiB | 0.49 MiB | **27.7 KiB** | 0.52 MiB | **1,252x** | 80x | 27.9 KiB | no |

**At 564,640 leaves phylo.io must transfer 33.8 MiB of tree and still cannot open the comparison** (Table 1). PhyloDelta transfers 27.7 KiB and shows it. The data column is the one that matters for the claim: it is flat — 26.2 KiB at 1,000 leaves and 27.7 KiB at 564,640 — against a download that grows linearly with the tree.

**The application bundles run the other way, and by more than expected.** phylo.io's is 7.91 MiB — `phylo.js` at 3.81 MiB plus two worker chunks at 2.74 and 1.36 MiB — against PhyloDelta's 0.49 MiB. So PhyloDelta transfers less **in total at every rung including the smallest**, which was not the expected result: the prediction was that it would lose on total bytes on small trees and win only through the data column.

*Two caveats, and they pull in opposite directions — stated separately rather than netted off.*

- **Compression is off**, deliberately, so both tools face identical transport. It was expected to narrow the ratio, since Newick compresses well. Measured, it **widens** it — see Table 20.

- **In favour of it:** PhyloDelta's data figure includes a 7.4 KiB `GET /api/v1/datasets` catalogue whose size tracks **how many comparisons the store holds**, not tree size. The benchmark store holds every ladder rung, so a single-comparison deployment transfers less than is shown.


## Table 20 — The same transfer, compressed

<!-- tier: SUPPORT -->
> **SUPPORT** — Table 19 under compression, which is what a real deployment serves. Answers the first objection anyone will raise to 19, and answers it the other way from the expected one.

*The same runner with `BENCH_GZIP=1`: `serve.mjs` compresses static files **and** proxied API responses. Both tools, both transports, nothing else changed.*

The API had to be compressed in the proxy, because FastAPI ships no `GZipMiddleware`. Without that, this run would have compressed phylo.io's Newick and left this frontend's JSON alone — measuring a transport difference and reporting it as a design one, in our own favour.

| leaves | phylo.io data | PhyloDelta data | of which the two slices | ratio, gzip | ratio, raw | data, app path | of which the two slices | under 10 KiB |
|---:|---:|---:|---:|---:|---:|---:|---:|:---:|
| 1,000 | 0.01 MiB | **8.7 KiB** | 3.5 KiB | **1x** | 1x | 9.6 KiB | 3.8 KiB | yes |
| 2,500 | 0.02 MiB | **8.8 KiB** | 3.6 KiB | **2x** | 2x | 9.7 KiB | 3.9 KiB | yes |
| 5,000 | 0.03 MiB | **9.0 KiB** | 3.8 KiB | **4x** | 3x | 9.9 KiB | 4.1 KiB | yes |
| 10,000 | 0.06 MiB | **9.1 KiB** | 3.8 KiB | **7x** | 6x | 10.0 KiB | 4.2 KiB | yes |
| 17,645 | 0.46 MiB | **11.1 KiB** | 5.8 KiB | **43x** | 36x | 12.0 KiB | 6.2 KiB | **no** |
| 35,290 | 0.76 MiB | **11.0 KiB** | 5.7 KiB | **71x** | 67x | 12.0 KiB | 6.1 KiB | **no** |
| 70,580 | 1.53 MiB | **10.9 KiB** | 5.6 KiB | **144x** | 139x | 11.0 KiB | 5.6 KiB | **no** |
| 141,160 | 3.07 MiB | **10.6 KiB** | 5.4 KiB | **295x** | 285x | 10.7 KiB | 5.3 KiB | **no** |
| 282,320 | 6.16 MiB | **10.1 KiB** | 4.8 KiB | **626x** | 591x | 10.2 KiB | 4.8 KiB | **no** |
| 564,640 | 12.36 MiB | **9.0 KiB** | 3.7 KiB | **1,409x** | 1,252x | 9.1 KiB | 3.7 KiB | yes |

**The data column is not under 10 KiB at every rung.** Opening a comparison transfers up to 11.1 KiB compressed on the `rf` store and 12.0 KiB on the app's path. Of the largest, the two slices — the view itself — are 5.8 KiB, and 5.2 KiB is requests made once when a comparison opens: the metric catalogue, the dataset catalogue, `/me`, status and the comparison header. Across both paths the two slices never exceed 6.2 KiB.


**Compression widens the gap, which was not the expectation.** At 564,640 leaves the ratio goes from 1,252x to 1,409x. The reason is in the compression factors, not in the design: the slice JSON compresses 3.1x — repeated keys and small integers — while the Newick manages only 2.7x, because at this size it is mostly unique labels and branch lengths, which is close to incompressible.

This matters for the write-up beyond the number: gzip is what a real deployment serves, so **Table 20 is the honest production figure and Table 19 is the conservative one.** Quoting 19 understates the result.

*Application bundles compress too, and the asymmetry survives: 1.34 MiB against 0.14 MiB, still 10x apart.*


## Table 21 — Sized to the viewport, not to the tree

<!-- tier: PRESENT -->
> **PRESENT** — The other half of "sized to the viewport". Every other table shows the payload ignoring the tree; only this one shows it following the window, which is what earns the word *sized*.

*Slice payload only, summed across both panels, from the wire. Width held at 1440 px; height varied.*

Every other table here shows the payload ignoring the **tree**. That is necessary but not sufficient: a server returning a fixed fifty leaves whatever the window would satisfy all of them while not doing what the design claims. This grid separates the two — read **down** a column for invariance to the tree, and **across** the rows for dependence on the window.

| window px | panel px | leaf budget | 17,645 leaves | 564,640 leaves |
|---:|---:|---:|---:|---:|
| 400 | 210 | **50** | 14.7 KiB / 50 tips | 12.0 KiB / 50 tips |
| 700 | 510 | **50** | 14.7 KiB / 50 tips | 12.0 KiB / 50 tips |
| 1,000 | 810 | **50** | 14.7 KiB / 50 tips | 12.0 KiB / 50 tips |
| 1,200 | 1010 | **75** | 22.0 KiB / 75 tips | 19.2 KiB / 75 tips |
| 1,400 | 1210 | **75** | 22.0 KiB / 75 tips | 19.2 KiB / 75 tips |
| 1,700 | 1510 | **100** | 28.4 KiB / 100 tips | 26.4 KiB / 100 tips |
| 2,000 | 1810 | **125** | 34.8 KiB / 125 tips | 33.2 KiB / 125 tips |
| 2,600 | 2410 | **175** | 47.0 KiB / 175 tips | 46.0 KiB / 175 tips |
| 3,200 | 3010 | **225** | 59.1 KiB / 225 tips | 57.7 KiB / 225 tips |

**Across the rows the payload follows the window:** panel 210 px to 3,010 px (14x) takes the budget from 50 to 225 tips and the payload from 14.7 KiB to 59.1 KiB. Above the floor the ratio of panel pixels to budgeted leaves settles at about **14**, which is `PIXELS_PER_LEAF` — the design constant recovered from the measurement rather than asserted.

**Down the columns it ignores the tree:** at the same window, 17,645 leaves and 564,640 leaves — 32x more — cost 59.1 KiB and 57.7 KiB. The larger tree is marginally *cheaper*, which is label lengths, not structure.

**The honest qualification: the steps are coarse.** `readableBudget` rounds to 25 leaves at 14 px each, so the payload only changes every ~350 px of panel — and with the 40-leaf floor, every window from 400 to 1,000 px gets the same 50 tips. So "sized to the viewport" holds with a granularity of about 350 px, and across the ordinary range of laptop windows the payload is in practice constant. The quantisation is deliberate (a settling layout must not cost a request, §29) but it does mean the scaling only bites on tall displays.

*This also caught a sampling error worth keeping: the first run used evenly-spaced heights of 400-1,000 and reported an identical payload four times, which reads as the payload ignoring the viewport when it was the sample sitting inside one quantisation bucket.*


## Table 22 — The RF distance across four implementations

<!-- tier: PRESENT -->
> **PRESENT** — Correctness again, but against implementations that share nothing with this one. Table 18's agreement is with the same paper's own code; this is the check an examiner will ask for.

*Produced by `harness/rf_external.py` against DendroPy 5.1.0 and ETE3 3.1.3, with TreeDiff's `rf_postorder` beside them. Every tool is given the same two trees: rooted, and reconciled to their shared leaf set.*

| leaves | PhyloDelta `rf` | normalised | DendroPy | ETE3 | `rf-treediff` (half) | equal |
|---:|---:|---:|---:|---:|---:|:---:|
| 1,000 | **1,062** | 0.532 | 1,062 | 1,062 | 531 | yes |
| 2,500 | **2,438** | 0.488 | 2,438 | 2,438 | 1,219 | yes |
| 5,000 | **4,414** | 0.442 | 4,414 | 4,414 | 2,207 | yes |
| 10,000 | **8,226** | 0.411 | 8,226 | 8,226 | 4,113 | yes |
| 17,645 | **13,650** | 0.387 | 13,650 | 13,650 | 6,825 | yes |

**Exact agreement at every rung.** 5 of 5 rungs have PhyloDelta equal to both DendroPy and ETE3, and equal to twice `rf-treediff`. The clade sets were never in question — Table 18 had already checked those — but the *scale* was, and this is what fixed it.

**This table is why the metric changed.** It used to show PhyloDelta at exactly half of DendroPy and ETE3 at every rung: the store reported half the symmetric difference, following TreeDiff, while every document here and the thesis itself defined RF as the whole of it. Table 18 could not have caught that, because TreeDiff is the reference implementation of the same paper and shares the convention — two implementations of one definition agreeing tells you the code is faithful, not that the definition is the field's. The `rf` metric is now at version 2 and reports the full difference; stored comparisons from version 1 are refused by name rather than re-labelled.

**The normalisation was the half that was actually wrong.** Version 1 divided the *halved* RF by the maximum of the *full* RF, so the ratio could not exceed 0.5 whatever the trees — and the test that should have caught it asserted `> 0.49` for two near-unrelated trees, reading the ceiling as "near-maximal". The vibrio pair reported 0.193 and now reports 0.387; two unrelated trees now reach 0.9999 instead of sitting just under the ceiling.

**Two settings decide whether the comparison is like-for-like**, and both produce a plausible near-miss rather than an error when wrong. *Rooting*: this store counts rooted clades, and DendroPy's unrooted mode gives 1,044 rather than 1,062 at 1,000 leaves, while ETE3 unroots by default. *Reconciliation*: handing the 17,645 pair over as it sits on disk adds four bipartitions, because ST 211 is in only one of the two trees (§2.6).


## Table 23 — phylo.io 2.2.5: paint and compare, measured separately

<!-- tier: PRESENT -->
> **PRESENT** — Paint and compare measured apart, three loads a rung, where phylo.io paints but its comparison does not finish in 600 s. Table 1's three † rows come from here.

*`harness/phyloio_paint.mjs` against 2.2.5, Chrome 156.0.8078.74, bench commit `015f70b`. 3 page loads per rung, 700 s per load, 600 s for the comparison.*

Tables 1, 2 and 3 take these rows from here, because one load cannot say whether a paint or a comparison is reliable and three can.

| leaves | loads | painted | paint (median) | SVG paths | compare finished in 600 s |
|---:|---:|---:|---:|---:|:---:|
| 17,645 | 3 | **3 of 3** | 8.5 s | 670 | **no** |
| 35,290 | 3 | **3 of 3** | 23.4 s | 640 | **no** |
| 70,580 | 3 | **3 of 3** | 74.9 s | 1036 | **no** |

**It paints, reliably; its comparison is the slow half.** 9 of 9 loads painted and 0 of 9 finished the comparison in 600 s. Table 4 gives the comparison longer. A slice here arrives with its similarity values already in it.

*The 70,580 row was run after the campaign, from the same tag and by the same runner, because the single ceiling attempt could not tell a slow load from a failed one: its 660 s limit is shorter than this rung's 75 s paint plus the 600 s comparison.*


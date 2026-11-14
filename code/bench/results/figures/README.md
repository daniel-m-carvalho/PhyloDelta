# Data behind the thesis charts

Written by `harness/make_tables.py` from `results/*.json`, beside `TABLES.md`; never edited by hand. Every `_median`, `_q1`, `_q3` triple is the median and the inclusive first and third quartiles of the repeated measurement (§34.24). An empty cell means nothing was measured, never zero.

- `time_to_interactive.csv` — Table 1. phylo.io paint and compare, PhyloDelta's load, the precompute at two threads (Table 8), and the **first opening**: precompute plus load, median plus median. Its `q1`/`q3` are the sums of the two quartiles, a band around the total rather than quartiles of a measured total, since the two are measured separately. `*_loads` columns count the loads that got that far.
- `browser_memory.csv` — Tables 3 and 4: main-thread heap per load, and peak renderer RSS where Table 4 measured it (the larger rungs).
- `data_transferred.csv` — Tables 19 and 20: bytes of tree and comparison data per page load, uncompressed and gzip.
- `reroot.csv` — Table 24: seconds from a re-root to the re-rooted comparison on screen, and the clade re-rooted on.

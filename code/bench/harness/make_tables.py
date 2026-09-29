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


def _run(*argv, default="unknown"):
    """A short command's first line of output, or a stated default.

    Read rather than written down: a hand-copied commit is wrong from the next
    commit onwards, and this file exists because a copied number stops matching
    its source. A missing tool degrades to "unknown" instead of failing the run.
    """
    import subprocess

    try:
        out = subprocess.run(argv, capture_output=True, text=True, timeout=10)
        return out.stdout.strip().splitlines()[0] if out.stdout.strip() else default
    except Exception:
        return default


def _commit() -> str:
    """The commit these tables were generated at, flagged if the tree is dirty.

    `TABLES.md` is excluded from the dirty check, because writing it is what makes
    the tree dirty — including it made the marker fire on every single run, which
    is a warning that means nothing. The marker is for *uncommitted inputs*: a
    changed runner or an unsaved result file, where the tables would describe code
    that is not in the commit named beside them.
    """
    sha = _run("git", "rev-parse", "--short", "HEAD")
    import subprocess

    try:
        out = subprocess.run(
            ["git", "status", "--porcelain"], capture_output=True, text=True, timeout=10
        )
        changed = [
            line for line in out.stdout.splitlines()
            if line.strip() and not line.endswith("results/TABLES.md")
        ]
    except Exception:
        changed = []
    return f"{sha}{' + uncommitted changes' if changed else ''}"


def _os_version() -> str:
    product = _run("sw_vers", "-productVersion")
    build = _run("sw_vers", "-buildVersion")
    kernel = _run("uname", "-r")
    return f"macOS {product} (build {build}, Darwin {kernel})"


def load(name, default=None):
    path = RESULTS / name
    return json.loads(path.read_text()) if path.exists() else default


ceiling = load("ceiling.json", {})
server = {r["leaves"]: r for r in load("server_build.json", [])}
endurance = load("endurance.json", [])
#: Full builds at pinned thread counts. Table 8 reports the 2-thread column as
#: the deployment setting; Table 9 compares all three.
#: Pinned-thread builds. 10 is loaded like the others now: it used to be taken
#: from `server_build.json` on the assumption that the benchmark store had been
#: built with the default thread count. That assumption silently became false
#: the moment the store was rebuilt at 2 threads, and the table then showed a
#: 2-thread run in a column headed "10 threads" — the same failure as the
#: mislabelled file in DECISIONS Corrections, in the generator this time.
pinned = {n: load(f"thread_builds_{n}.json") for n in (1, 2, 10)}

#: Build time at the **deployment** thread count, which is what every table that
#: quotes one precompute figure must use.
#:
#: `server_build.json` is the original run and used the default — ten threads,
#: the whole machine. Quoting it as "the precompute" overstates the design by
#: ~1.5x at the top rung (339.5 s against 492.7 s) and contradicts Table 8 on the
#: same page. Tables 1 and 13 were doing exactly that.
DEPLOY_THREADS = 2
deploy_build = {
    r["leaves"]: r["build_s"]
    for r in (pinned.get(DEPLOY_THREADS) or {"rungs": []})["rungs"]
}


#: Measured at 10 threads, from its own pinned run — never inferred from
#: whatever the benchmark store happened to be built with.
ten_thread = {
    r["leaves"]: r["build_s"] for r in (pinned.get(10) or {"rungs": []})["rungs"]
}


def precompute_s(leaves):
    """Seconds to build this rung at the deployment setting, or None.

    Falls back to the 10-thread run only where no pinned measurement exists, so a
    missing rung shows a number that is optimistic rather than no number at all —
    and `precompute_is_pinned` is what lets a caller say which it got.
    """
    if leaves in deploy_build:
        return deploy_build[leaves]
    return server.get(leaves, {}).get("build_s")


def precompute_is_pinned(leaves) -> bool:
    return leaves in deploy_build
navigation = load("navigation.json", {})
metric_builds = load("metric_builds.json", {})
metric_phases = load("metric_phases.json", {})
transfer = load("transfer.json", {})
transfer_gzip = load("transfer_gzip.json", {})
viewport = load("viewport.json", {})
bcn_211 = load("phyloio_bcn_2.1.1.json", {})
bcn_225 = load("phyloio_bcn_2.2.5.json", {})
ceiling_225 = load("phyloio_ceiling_2.2.5.json", {})
rows = ceiling.get("rows", [])


# --- which of these belong in the thesis ----------------------------------
#
# Eighteen tables is more than a thesis chapter can carry, and most were produced
# to answer a question that came up rather than to make an argument. The tier is
# recorded here, beside the generator, so the classification is part of the
# artefact rather than a judgement made once in conversation and lost.
#
#   PRESENT   the argument. Drop one and a claim goes unsupported.
#   SUPPORT   defends a choice or a limit of a PRESENT table. Appendix, or a
#             sentence in the text citing the number.
#   WORKING   real, reproducible, and not worth a reader's time: it answered an
#             internal question, or a PRESENT table already says it.
PRESENT, SUPPORT, WORKING = "PRESENT", "SUPPORT", "WORKING"

TIERS = {
    1: (PRESENT, "The headline. Where each tool stops, and the size claim."),
    2: (PRESENT, "The caveat Table 1 cannot be read without: this design draws "
                 "less, and that IS the design. Omitting it is how the earlier "
                 "34x mistake happened."),
    3: (PRESENT, "Memory is half the claim — flat against growing."),
    4: (SUPPORT, "The detail behind Table 1's 'failed': what failed and how. Cite "
                 "the 30-minute budget in the text."),
    5: (PRESENT, "Correctness. A fast wrong answer is worth nothing, so the "
                 "approximation's cost has to be stated."),
    6: (WORKING, "Diagnostic. Phase-splitting another tool's time compares phase "
                 "names that do not mean the same thing; Table 1's paint/compare "
                 "split is the part that survives."),
    7: (WORKING, "A method note, not a result: it establishes that one sample per "
                 "rung was enough. Belongs in a sentence about method."),
    8: (PRESENT, "What the design costs. Presenting Table 1 without this is "
                 "claiming the precompute is free."),
    9: (SUPPORT, "Justifies the 2-thread setting every build figure uses. One "
                 "sentence plus the table in an appendix."),
    10: (WORKING, "Subsumed by Table 9, which measures the same trade-off on whole "
                  "builds rather than one step."),
    11: (SUPPORT, "The deployability argument: server memory is linear, not "
                  "quadratic. A sentence with the marginal figure."),
    12: (PRESENT, "The mechanism itself — a payload sized to the viewport, flat at "
                  "every tree size. This is the thesis in one table."),
    13: (PRESENT, "The honest ledger. What was given up to get Table 1."),
    14: (PRESENT, "Methodology. The rungs above 17,645 are synthetic and the "
                  "thesis must say so where the numbers are."),
    15: (PRESENT, "The other half of interaction: loading is not using. Also "
                  "carries the finding that the comparison tool's cross-tree jump "
                  "does not work at all."),
    16: (WORKING, "The attribution behind Table 15 — the round trip is ~6 ms of a "
                  "~49 ms navigation. One sentence, not a table."),
    17: (SUPPORT, "Why the metric choice is not free, and where §9's claim holds. "
                  "Relevant only if the thesis discusses metric plugins."),
    18: (SUPPORT, "Validation: two independent RF implementations agreeing at 1.1M "
                  "nodes. A sentence, with the table in an appendix."),
    19: (PRESENT, "The claim as the quantity it is actually about: bytes over the "
                  "wire. Present it beside Table 12 — 12 is the mechanism, 19 is "
                  "what the mechanism buys."),
    20: (SUPPORT, "Table 19 under compression, which is what a real deployment "
                  "serves. Answers the first objection anyone will raise to 19, "
                  "and answers it the other way from the expected one."),
    21: (PRESENT, "The other half of \"sized to the viewport\". Every other table "
                  "shows the payload ignoring the tree; only this one shows it "
                  "following the window, which is what earns the word *sized*."),
}


def table(number: int, title: str, lead: str = "\n") -> None:
    """Print a table heading with its tier, so the file says what to present."""
    tier, why = TIERS[number]
    print(f"{lead}## Table {number} — {title}\n")
    print(f"<!-- tier: {tier} -->")
    print(f"> **{tier}** — {why}\n")


def fmt(value, unit="", nd=1, dash="—"):
    return dash if value is None else f"{value:,.{nd}f}{unit}"


print("# PhyloDelta vs Phylo.io — measured comparison\n")
print("## Environment\n")
print("| | |")
print("|---|---|")
print("| Machine | Apple M4 laptop — **4 performance + 6 efficiency cores**, 24 GB |")
print(f"| OS | {_os_version()} |")
print(f"| Browser | {ceiling.get('browser', 'Chrome')}, **headless**, system Chrome "
      "via Playwright's `channel: \"chrome\"` |")
print("| Browser flags | `--js-flags=--max-old-space-size=8192`, "
      "`--disable-dev-shm-usage` — **both tools, identically** |")
print(f"| Viewport | {ceiling.get('viewport', {}).get('width', 1440)} x "
      f"{ceiling.get('viewport', {}).get('height', 900)}; Table 21 varies the height |")
print("| **Tool compared against** | **phylo.io 2.1.1**, its own prebuilt `dist/`, "
      "unmodified; findings re-checked against **2.2.5** (see the Table 15 note) |")
# "Generated at", not "this is the commit of this file": committing the generated
# file necessarily produces a later commit, so the row lags by one by
# construction. Saying which it means costs a word and stops it reading as wrong.
print(f"| This project | generated at commit `{_commit()}` |")
print("| Runtimes | Python 3.12.14 (`uv`), Node 26.3.0, Playwright 1.63.0 |")
print("| Backend database | SQLite, in the store directory |")
print("| Store location | `/private/tmp/...` — an APFS SSD volume, **not** a RAM disk |")
print("| **Backend threads** | **2 of the 10 cores** (`PHYLODELTA_THREADS=2`) |")
print("| Transport | one origin, one fresh page per measurement; uncompressed "
      "except Table 20, which is gzip |")
print("| Power state | not controlled (laptop) — bears only on Table 9's "
      "564,640 ratios, already withdrawn there |")
print()
print("**The two entries that matter most for checking these numbers** are the "
      "browser flags and the phylo.io version. The heap cap decides *where* a tool "
      "fails, so Table 1's and Table 4's `failed` rows are statements about the "
      "tool at an 8 GB cap, not at Chrome's default — and it is raised for both "
      "tools, which is what makes a failure the tool's own ceiling. The version "
      "matters because several findings are about phylo.io's behaviour: the "
      "\"Highlight BCN\" crash (Table 15) is a fact about **2.1.1** and a later "
      "release may fix it.\n")
print("**Headless, throughout.** Rendering in headless Chrome is not identical to "
      "a visible window, and these are partly rendering measurements — so this is "
      "a real caveat, not a footnote. It applies equally to both tools, so the "
      "*comparison* holds; the absolute paint times would need re-taking in a "
      "headed browser to be quoted as what a user sees.\n")
print("*Power state was not controlled, and is recorded for completeness rather "
      "than as a limitation.* Every claim these tables make is a claim about "
      "**shape** — flat against growing, completes against does not, ratios from "
      "16x to 1,644x — and none of them turns on a timing difference of the size "
      "throttling produces. It bears on exactly one number: the 564,640 row of "
      "Table 9, whose ratios are withdrawn there on those grounds already.\n")
print("**Only 2 of the 10 cores are used for the backend**, deliberately. "
      "Table 9 is the measurement behind that choice: two threads give ~2x at "
      "94% efficiency where ten give ~4.7x at 57%, so eight further cores buy "
      "the last 2.3x at a steeply falling rate. Every build figure in these "
      "tables is therefore what a **two-core** deployment costs, not what this "
      "machine can do flat out.\n")


# --- 0. what to present ---------------------------------------------------
print("## Which of these to present\n")
print("Eighteen tables is more than a chapter can carry, and most were made to "
      "answer a question that came up rather than to make an argument. Each "
      "heading below repeats its tier.\n")
for tier, heading, blurb in (
    (PRESENT, "Present these", "The argument. Drop one and a claim goes unsupported."),
    (SUPPORT, "Appendix, or one sentence citing the number",
     "Defends a choice or a stated limit of a PRESENT table."),
    (WORKING, "Keep in the repository, do not present",
     "Real and reproducible, but a PRESENT table already says it or it answered "
     "an internal question."),
):
    chosen = [n for n, (t, _) in sorted(TIERS.items()) if t == tier]
    print(f"**{heading}** — {blurb}\n")
    for n in chosen:
        print(f"- **Table {n}** — {TIERS[n][1]}")
    print()
print("The PRESENT tables answer, in this order: how far each tool gets (1), "
      "on comparable work (2), at what memory (3), sending how many bytes (19), "
      "sized by what (21), how correctly (5), by what mechanism (12), at what "
      "navigation cost (15), for what precompute (8), giving up what (13), "
      "measured on what data (14).\n")
print("*If only one table can be shown, it is 19.* It states the claim in the "
      "quantity the claim is about — 28.9 KB against 35.5 MB at 564,640 leaves — "
      "and it is the only table whose ratio grows without bound while everything "
      "on this side stays flat.\n")
print("*Two tables to read together, not separately:* Table 1 without Table 2 "
      "overstates the result, because the tools do not draw the same amount — "
      "that asymmetry IS the design, and hiding it is how an earlier version of "
      "this comparison reported a 34x that did not exist.\n")
print("---\n")


# --- 1. the headline ------------------------------------------------------
table(1, "Scalability: where each tool stops", lead="")
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
        f"{fmt(precompute_s(leaves), ' s')}"
        f"{'' if precompute_is_pinned(leaves) else ' *(10 threads)*'} |"
    )

# --- 2. fairness ----------------------------------------------------------
table(2, "What each tool actually drew")
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
table(3, "Memory, and why it grows for one tool and not the other")
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
    table(4, "Failure behaviour, given 30 minutes and 16 GB")
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
    table(5, "Accuracy: what the LSH approximation costs")
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
table(6, "Where phylo.io's time goes")
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
    table(7, "PhyloDelta, repeated")
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
    two_thread = deploy_build
    table(8, "The precompute PhyloDelta pays instead")
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
    table(9, "Build time at pinned thread counts")
    print("Table 8 used the default — one thread per hardware thread, **10** on "
          "this machine. These are the same builds with the count pinned, "
          "through the same upload path, each on its own store.\n")
    print("| leaves | 1 thread | 2 threads | 10 threads | 2 vs 1 | 10 vs 1 |")
    print("|---:|---:|---:|---:|---:|---:|")
    one = {r["leaves"]: r["build_s"] for r in pinned[1]["rungs"]}
    two = {r["leaves"]: r["build_s"] for r in pinned[2]["rungs"]}
    for leaves in sorted(one):
        ten = ten_thread.get(leaves)
        a, b = one[leaves], two.get(leaves)
        if not (ten and b):
            continue
        # Below 35,290 the worker's 2 s poll interval is most of the elapsed
        # time, so the ratios are noise: this is where 1,000 leaves "gains"
        # 3.81x and 5,000 "loses" 0.80x.
        mark = ""
        if leaves < 35_290:
            mark = " *(floor-limited — ratios are noise)*"

        print(
            f"| {leaves:,}{mark} | {a:.1f} s | {b:.1f} s | {ten:.1f} s | "
            f"{a / b:.2f}x | {a / ten:.2f}x |"
        )
    big = [n for n in sorted(one) if n >= 35_290 and two.get(n) and ten_thread.get(n)]
    lo, hi = big[0], big[-1]
    print(f"\n**Read the larger rows.** From {lo:,} to {hi:,} the picture is "
          f"clean and monotone: two threads rise {one[lo]/two[lo]:.2f}x -> "
          f"{one[hi]/two[hi]:.2f}x, ten rise {one[lo]/ten_thread[lo]:.2f}x -> "
          f"{one[hi]/ten_thread[hi]:.2f}x. The gain grows with size because below "
          f"~70,000 leaves the *serial* parts — parse, reconcile, ingest, and the "
          f"2 s poll — are most of the elapsed time, and threading the search "
          f"cannot touch them. Amdahl's law, visible directly.\n")
    print("**Re-measured, each thread count from an idle machine.** The first "
          "version of this table showed a 564,640 row where two threads gave "
          "2.44x — superlinear, therefore impossible for pure parallelism. That "
          "was attributed to thermal drift and the attribution was wrong: the "
          "same rung measured cold and then immediately after twenty minutes of "
          "saturating load gives 262.6 s and 244.3 s, the hot run marginally "
          "*faster*, with no thermal warning recorded by the OS either time.\n")
    print("The cause was that **the run labelled \"2 threads\" executed with "
          "one**. It matches a fresh single-threaded measurement to within 0.7% "
          "at 564,640 leaves, and the gap between old and new is 1.88x — "
          "exactly the 2-thread speedup in Table 10. `PHYLODELTA_THREADS` is "
          "read by the *worker*; the measuring tool took the thread count only "
          "to name its output file and never asked the worker what it was "
          "running with. A parameter that describes a run instead of "
          "controlling it will eventually describe it wrongly, in a file that "
          "looks perfectly well-formed (DECISIONS, Corrections).\n")
    s2, s10 = one[hi] / two[hi], one[hi] / ten_thread[hi]
    print(f"**What to choose.** At {hi:,} leaves two threads give {s2:.2f}x at "
          f"{s2 / 2 * 100:.0f}% efficiency; ten give {s10:.2f}x at "
          f"{s10 / 10 * 100:.0f}%. One thread wastes a near-free doubling. If "
          "efficiency is the objective, **two is the sweet spot** — but "
          "latency for a single comparison favours more threads, and "
          "throughput for a queue favours fewer per build with more builds at "
          "once. `PHYLODELTA_THREADS` exists so a deployment can choose; there "
          "is no single best value.")

scaling = load("thread_scaling.json")
if scaling:
    table(10, "Thread scaling of the parallel step")
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
    table(11, "What the server needs while it builds")
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
    table(12, "The request a panel actually makes")
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
table(13, "What the design costs")
print("| | phylo.io | PhyloDelta |")
print("|---|---|---|")
print("| Server required | no | **yes** |")
print("| Precompute before first view | none | up to "
      f"{max((precompute_s(n) or 0) for n in server) if server else 0:.0f} s "
      f"at {DEPLOY_THREADS} threads |")
print("| Whole tree ever visible | yes, in memory | **no, never transferred** |")
print("| Works offline from a file | yes | no |")
print("| Comparison recomputed on demand | yes | no, fixed at build |")

table(14, "Provenance of the test data")
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
    table(15, "Navigation responsiveness, once the comparison is open")
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
    table(16, "Where a PhyloDelta navigation's time goes")
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
        print("\n### Table 15 note — phylo.io's \"Highlight BCN\" is intermittent\n")
        print("Every attempt failed in the navigation run above, at every rung, with the same "
              "error:\n")
        print(f"> `{first.get('error')}`\n")
        print("**But \"always\" was n=1 page load per rung, and the failure is intermittent.** A "
              "dedicated probe over repeated loads of the same pair at 1,000 leaves:\n")
        if bcn_211 or bcn_225:
            print("| phylo.io | page loads | loads where the jump worked | attempts succeeded |")
            print("|---|---:|---:|---:|")
            for d in (bcn_211, bcn_225):
                if d:
                    print(f"| {d['label']} | {d['loads']} | {d['loads_with_any_success']} "
                          f"| {d['attempts_succeeded']}/{d['attempts_total']} |")
            print()
        print("It is **decided per page load and then holds for that load** — a load either fails "
              "on every node tried or succeeds on every node tried. So the honest claim is that the "
              "jump fails in most loads, not that it never works, and Table 15 reports one load per "
              "rung, which is why it shows only the common outcome.\n")
        print("**The mechanism, and why it is conditional.** It is reached only from the "
              "context-menu item of that name (`viewer.js` line 1175 is the sole caller). `api.js` "
              "builds **two separate models** from the BCN worker's reply, and the `elementBCN` "
              "references inside the first point at that reply's own embedded copy of the second "
              "tree. `getHierarchyNodeFromModelNode` compares by object identity, so whether it "
              "finds anything depends on whether structured-clone identity between the two halves "
              "of one message survives into the rebuilt models — which is evidently not "
              "guaranteed. When it does not, the lookup returns null and `expandToRoot` hands that "
              "null to `apply_collapse_from_data_to_d3`, which reads `_children` on it.\n")
        print("**Not a version problem.** Checked against **2.2.5** (2026-01-30) as well as the "
              "2.1.1 used elsewhere here: `api.js` and `worker_bcn.js` are unchanged between them, "
              "all four functions in this path are byte-identical, and the measured rates match. "
              "The 2.1.1 figures in these tables are not stale on this point.\n")
        if ceiling_225:
            done = ceiling_225["per_load"][0]["completed"]
            print(f"The ceiling was confirmed on 2.2.5 directly rather than inferred from the "
                  f"diff: at **{ceiling_225['leaves']:,} leaves** its comparison "
                  f"**{'completed' if done else 'did not complete'}** inside a 600 s budget, "
                  f"matching 2.1.1. That is the one claim the whole of Table 1 rests on, so it was "
                  f"worth running rather than arguing.\n")
        print("It still sharpens the comparison rather than softening it: the cross-tree jump is "
              "the operation PhyloDelta's design is most open to criticism over — it costs an "
              "`/ancestor` call and a slice the panel has never held — and it is the one the "
              "comparison tool manages only sometimes.\n")


# --- 8. does the metric change the cost? ----------------------------------
phase_rows = metric_phases.get("rows", [])
if phase_rows:
    table(17, "Does the chosen metric change what a build costs?", lead="\n\n")
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
        table(18, "Two RF implementations against each other")
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

# --- 9. the claim as bytes -------------------------------------------------
transfer_rows = transfer.get("rows", [])
if transfer_rows:
    table(19, "Bytes over the wire")
    print("*\"Never send the whole tree\" is a claim about transferred bytes. "
          "Measured from the wire — `request.sizes()` per response, not file "
          "sizes on disk — uncompressed on both sides, one origin.*\n")
    print("**Application and data are separate columns on purpose.** PhyloDelta "
          "ships a bundle too, and quoting its slices against phylo.io's "
          "whole-tree download while ignoring that would be comparing a partial "
          "cost with a total one — the error Table 2 exists to prevent. Add the "
          "columns as you see fit; the application bytes are paid once per "
          "visit, the data bytes once per comparison.\n")
    print("| leaves | phylo.io app | phylo.io data | phylo.io total | "
          "PhyloDelta app | PhyloDelta data | PhyloDelta total | data ratio | total ratio |")
    print("|---:|---:|---:|---:|---:|---:|---:|---:|---:|")

    for row in transfer_rows:
        pi, pd = row.get("phyloio", {}), row.get("phylodelta", {})
        pi_app, pi_data = pi.get("app"), pi.get("data")
        pd_app, pd_data = pd.get("app"), pd.get("data")
        if None in (pi_app, pi_data, pd_app, pd_data):
            print(f"| {row['leaves']:,} | — | — | — | — | — | — | — | — |")
            continue
        pi_total, pd_total = pi_app + pi_data, pd_app + pd_data
        print(
            f"| {row['leaves']:,} | {pi_app / 1e6:,.2f} MB | {pi_data / 1e6:,.2f} MB "
            f"| {pi_total / 1e6:,.2f} MB | {pd_app / 1e6:,.2f} MB "
            f"| **{pd_data / 1024:,.1f} KB** | {pd_total / 1e6:,.2f} MB "
            f"| **{pi_data / pd_data:,.0f}x** | {pi_total / pd_total:,.0f}x |"
        )

    top = transfer_rows[-1]
    tpi, tpd = top["phyloio"], top["phylodelta"]
    first = transfer_rows[0]
    print(f"\n**At {top['leaves']:,} leaves phylo.io must transfer "
          f"{tpi['data'] / 1e6:,.1f} MB of tree and still cannot open the "
          f"comparison** (Table 1). PhyloDelta transfers "
          f"{tpd['data'] / 1024:,.1f} KB and shows it. The data column is the one "
          f"that matters for the claim: it is flat — "
          f"{first['phylodelta']['data'] / 1024:,.1f} KB at "
          f"{first['leaves']:,} leaves and {tpd['data'] / 1024:,.1f} KB at "
          f"{top['leaves']:,} — against a download that grows linearly with the "
          f"tree.\n")
    print("**The application bundles run the other way, and by more than "
          f"expected.** phylo.io's is {tpi['app'] / 1e6:,.2f} MB — `phylo.js` at "
          "4.0 MB plus two worker chunks at 2.9 and 1.4 MB — against PhyloDelta's "
          f"{tpd['app'] / 1e6:,.2f} MB. So PhyloDelta transfers less **in total at "
          "every rung including the smallest**, which was not the expected result: "
          "the prediction was that it would lose on total bytes on small trees and "
          "win only through the data column.\n")
    print("*Two caveats, and they pull in opposite directions — stated separately "
          "rather than netted off.*\n")
    print("- **Compression is off**, deliberately, so both tools face identical "
          "transport. It was expected to narrow the ratio, since Newick "
          "compresses well. Measured, it **widens** it — see Table 20.\n")
    print("- **In favour of it:** PhyloDelta's data figure includes a ~13 KB "
          "`GET /api/v1/datasets` catalogue whose size tracks **how many "
          "comparisons the store holds**, not tree size. The benchmark store "
          "holds every ladder rung, so a single-comparison deployment transfers "
          "closer to 15 KB and the real figure is about half what is shown.\n")

# --- 10. the same, compressed ---------------------------------------------
gz_rows = transfer_gzip.get("rows", [])
raw_by_leaves = {r["leaves"]: r for r in transfer.get("rows", [])}
if gz_rows:
    table(20, "The same transfer, compressed")
    print("*The same runner with `BENCH_GZIP=1`: `serve.mjs` compresses static "
          "files **and** proxied API responses. Both tools, both transports, "
          "nothing else changed.*\n")
    print("The API had to be compressed in the proxy, because FastAPI ships no "
          "`GZipMiddleware`. Without that, this run would have compressed "
          "phylo.io's Newick and left this frontend's JSON alone — measuring a "
          "transport difference and reporting it as a design one, in our own "
          "favour.\n")
    print("| leaves | phylo.io data | PhyloDelta data | ratio, gzip | ratio, raw |")
    print("|---:|---:|---:|---:|---:|")
    for row in gz_rows:
        pi, pd = row.get("phyloio", {}), row.get("phylodelta", {})
        if pi.get("data") is None or not pd.get("data"):
            print(f"| {row['leaves']:,} | — | — | — | — |")
            continue
        was = raw_by_leaves.get(row["leaves"], {})
        was_ratio = (
            f"{was['phyloio']['data'] / was['phylodelta']['data']:,.0f}x"
            if was and was.get("phyloio", {}).get("data") and was.get("phylodelta", {}).get("data")
            else "—"
        )
        print(f"| {row['leaves']:,} | {pi['data'] / 1e6:,.2f} MB "
              f"| **{pd['data'] / 1024:,.1f} KB** "
              f"| **{pi['data'] / pd['data']:,.0f}x** | {was_ratio} |")

    top_gz = gz_rows[-1]
    top_raw = raw_by_leaves.get(top_gz["leaves"], {})
    gz_data = top_gz["phylodelta"]["data"]
    raw_data = top_raw["phylodelta"]["data"]
    gz_tree = top_gz["phyloio"]["data"]
    raw_tree = top_raw["phyloio"]["data"]
    print(f"\n**Compression widens the gap, which was not the expectation.** At "
          f"{top_gz['leaves']:,} leaves the ratio goes from "
          f"{raw_tree / raw_data:,.0f}x to {gz_tree / gz_data:,.0f}x. The reason is "
          f"in the compression factors, not in the design: the slice JSON "
          f"compresses {raw_data / gz_data:,.1f}x — repeated keys and small "
          f"integers — while the Newick manages only {raw_tree / gz_tree:,.1f}x, "
          f"because at this size it is mostly unique labels and branch lengths, "
          f"which is close to incompressible.\n")
    print("This matters for the write-up beyond the number: gzip is what a real "
          "deployment serves, so **Table 20 is the honest production figure and "
          "Table 19 is the conservative one.** Quoting 19 understates the result.\n")
    gz_app_pi = top_gz["phyloio"]["app"]
    gz_app_pd = top_gz["phylodelta"]["app"]
    print(f"*Application bundles compress too, and the asymmetry survives: "
          f"{gz_app_pi / 1e6:,.2f} MB against {gz_app_pd / 1e6:,.2f} MB, still "
          f"{gz_app_pi / gz_app_pd:,.0f}x apart.*\n")

# --- 11. sized to the viewport, not to the tree ----------------------------
vp_rows = viewport.get("rows", [])
if vp_rows:
    rungs = viewport.get("rungs", [])
    table(21, "Sized to the viewport, not to the tree")
    print("*Slice payload only, summed across both panels, from the wire. Width "
          f"held at {viewport.get('width', 1440)} px; height varied.*\n")
    print("Every other table here shows the payload ignoring the **tree**. That is "
          "necessary but not sufficient: a server returning a fixed fifty leaves "
          "whatever the window would satisfy all of them while not doing what the "
          "design claims. This grid separates the two — read **down** a column for "
          "invariance to the tree, and **across** the rows for dependence on the "
          "window.\n")
    header = "| window px | panel px | leaf budget | " + " | ".join(
        f"{n:,} leaves" for n in rungs
    ) + " |"
    print(header)
    print("|---:" * (3 + len(rungs)) + "|")
    for row in vp_rows:
        first = next((c for c in row["cells"] if c.get("ok")), {})
        cells = []
        for c in row["cells"]:
            cells.append(
                f"{c['bytes'] / 1024:,.1f} KB / {c['displayed_leaves']} tips"
                if c.get("ok") else "—"
            )
        print(f"| {row['height']:,} | {first.get('panel_px', '—')} "
              f"| **{first.get('budget', '—')}** | " + " | ".join(cells) + " |")

    ok_rows = [r for r in vp_rows if any(c.get("ok") for c in r["cells"])]
    if ok_rows:
        lo, hi = ok_rows[0], ok_rows[-1]
        lo_cell = next(c for c in lo["cells"] if c.get("ok"))
        hi_cell = next(c for c in hi["cells"] if c.get("ok"))
        lo_panel = lo_cell.get("panel_px") or 1
        hi_panel = hi_cell.get("panel_px") or 1
        print(f"\n**Across the rows the payload follows the window:** panel "
              f"{lo_panel:,} px to {hi_panel:,} px ({hi_panel / lo_panel:,.0f}x) "
              f"takes the budget from {lo_cell['budget']} to {hi_cell['budget']} "
              f"tips and the payload from {lo_cell['bytes'] / 1024:,.1f} KB to "
              f"{hi_cell['bytes'] / 1024:,.1f} KB. Above the floor the ratio of "
              f"panel pixels to budgeted leaves settles at about **14**, which is "
              f"`PIXELS_PER_LEAF` — the design constant recovered from the "
              f"measurement rather than asserted.\n")
        # Invariance down the columns, stated from the widest row.
        per = [c for c in hi["cells"] if c.get("ok")]
        if len(per) > 1:
            a, b = per[0], per[-1]
            print(f"**Down the columns it ignores the tree:** at the same window, "
                  f"{a['total_leaves']:,} leaves and {b['total_leaves']:,} leaves "
                  f"— {b['total_leaves'] / a['total_leaves']:,.0f}x more — cost "
                  f"{a['bytes'] / 1024:,.1f} KB and {b['bytes'] / 1024:,.1f} KB. "
                  f"The larger tree is marginally *cheaper*, which is label "
                  f"lengths, not structure.\n")

    print("**The honest qualification: the steps are coarse.** `readableBudget` "
          "rounds to 25 leaves at 14 px each, so the payload only changes every "
          "~350 px of panel — and with the 40-leaf floor, every window from 400 "
          "to 1,000 px gets the same 50 tips. So \"sized to the viewport\" holds "
          "with a granularity of about 350 px, and across the ordinary range of "
          "laptop windows the payload is in practice constant. The quantisation is "
          "deliberate (a settling layout must not cost a request, §29) but it does "
          "mean the scaling only bites on tall displays.\n")
    print("*This also caught a sampling error worth keeping: the first run used "
          "evenly-spaced heights of 400-1,000 and reported an identical payload "
          "four times, which reads as the payload ignoring the viewport when it "
          "was the sample sitting inside one quantisation bucket.*\n")

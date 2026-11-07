"""Every table the comparison needs, generated from the result files.

Written as a generator rather than transcribed into the thesis by hand: a
number that is copied is a number that silently stops matching its source the
first time anything is re-run. Everything here reads `results/*.json` and can
be regenerated after any change.

    python3 harness/make_tables.py > results/TABLES.md
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from statistics import median

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
    """The commit that **measured** these tables, read from what the run recorded.

    Not this checkout's HEAD: the results are measured in a clean clone of the
    tag and the tables are generated wherever they are committed, so HEAD says
    which checkout printed them and nothing about which code produced the
    numbers. `campaign_env.py` refused to start on a dirty tree or off the tag.
    """
    env = load("environment.json")
    if env is None:
        sha = _run("git", "rev-parse", "--short", "HEAD")
        return f"{sha}, **no environment.json: not a tagged campaign**"
    dry = " **(dry run)**" if env.get("dry_run") else ""
    return f"{env['commit_short']} (`{env['tag']}`){dry}"


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
env = load("environment.json", {})
#: Facts about the run read off the machine afterwards: when Chrome updated, and
#: why four ceiling rungs were measured a second time. Dated, sourced, no figures
#: of merit.
notes = load("campaign_notes.json", {})
stats = load("ladder_stats.json", {}).get("rungs", [])
paint = load("phyloio_paint_2.2.5.json", {})
paint_by = {r["leaves"]: r for r in paint.get("rows", [])}
paint_extra = load("phyloio_paint_extra.json", {})
paint_by.update({r["leaves"]: r for r in paint_extra.get("rows", [])})
endurance_extra = load("endurance_extra.json", [])
long_compare = load("phyloio_long_compare.json", {})
accuracy_repeats = load("accuracy_repeats.json", {})
repeats = load("phylodelta_repeats.json", [])
repeat_by = {r["leaves"]: r for r in repeats}
latency = load("slice_latency.json", [])
latency_mast = {r["leaves"]: r for r in load("slice_latency_mast.json", [])}
app_builds = (load("thread_builds_2_app.json") or {"rungs": []})["rungs"]
transfer_app = {r["leaves"]: r for r in load("transfer_app.json", {}).get("rows", [])}
transfer_app_gzip = {r["leaves"]: r for r in load("transfer_app_gzip.json", {}).get("rows", [])}
nav_rows = navigation.get("rows", [])
#: Published by npm, not measured: `npm view phyloio time`. The version beside it
#: is read from the package the run used.
PHYLOIO_RELEASED = "2026-01-30"
#: Every navigation figure is a frame count at this refresh (§34.14).
FRAME_MS = 1000 / 60


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
    4: (SUPPORT, "The detail behind Table 1's limits: which are budgets and which "
                 "are failures, given 30 minutes."),
    5: (PRESENT, "Correctness. A fast wrong answer is worth nothing, so the "
                 "approximation's cost has to be stated."),
    6: (WORKING, "Diagnostic. Phase-splitting another tool's time compares phase "
                 "names that do not mean the same thing; Table 1's paint/compare "
                 "split is the part that survives."),
    7: (WORKING, "The six samples behind Table 1's PhyloDelta column, with their "
                 "spread. Belongs in a sentence about method."),
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
                  "fails in most page loads."),
    16: (WORKING, "The attribution behind Table 15: the round trip is a few "
                  "milliseconds of a three-frame navigation. One sentence, not a "
                  "table."),
    17: (SUPPORT, "Why the metric choice is not free, and where §9's claim holds. "
                  "Relevant only if the thesis discusses metric plugins."),
    18: (SUPPORT, "Validation: two independent RF implementations in a fixed "
                  "ratio at every rung. A sentence, with the table in an "
                  "appendix. Table 22 is the one that pins the scale."),
    19: (PRESENT, "The claim as the quantity it is actually about: bytes over the "
                  "wire. Present it beside Table 12 — 12 is the mechanism, 19 is "
                  "what the mechanism buys."),
    20: (SUPPORT, "Table 19 under compression, which is what a real deployment "
                  "serves. Answers the first objection anyone will raise to 19, "
                  "and answers it the other way from the expected one."),
    21: (PRESENT, "The other half of \"sized to the viewport\". Every other table "
                  "shows the payload ignoring the tree; only this one shows it "
                  "following the window, which is what earns the word *sized*."),
    23: (PRESENT, "Paint and compare measured apart, three loads a rung, where "
                  "phylo.io paints but its comparison does not finish in 600 s. "
                  "Table 1's three † rows come from here."),
    22: (PRESENT, "Correctness again, but against implementations that share "
                  "nothing with this one. Table 18's agreement is with the same "
                  "paper's own code; this is the check an examiner will ask for."),
}


def table(number: int, title: str, lead: str = "\n") -> None:
    """Print a table heading with its tier, so the file says what to present."""
    tier, why = TIERS[number]
    print(f"{lead}## Table {number} — {title}\n")
    print(f"<!-- tier: {tier} -->")
    print(f"> **{tier}** — {why}\n")


#: Binary units throughout, because mixing them is how a table comes to state
#: two different things under one heading. `ps -o rss` reports KiB and the
#: harness divides by 1024, so the RSS figures were always binary and were
#: merely labelled wrongly; the byte counts below were divided by 1e6 and are
#: converted here rather than relabelled, which would have changed the meaning
#: of the number without changing the number.
KIB = 1024
MIB = 1024 * 1024


def kib(byte_count) -> str:
    return f"{byte_count / KIB:,.1f} KiB"


def mib(byte_count) -> str:
    return f"{byte_count / MIB:,.2f} MiB"


def heap_mib(reading):
    """A runner's `heap_bytes` in MiB, or None where the reading timed out."""
    value = reading.get("heap_bytes")
    return None if value is None else value / MIB


def fmt(value, unit="", nd=1, dash="—"):
    return dash if value is None else f"{value:,.{nd}f}{unit}"


#: The ceiling attempt's limit, as that run recorded it.
OVER_ATTEMPT = f"over {ceiling.get('attempt_ms', 0) / 1000:.0f} s"


def phyloio_reading(row):
    """phylo.io at one rung, from the runner that measured it best.

    Three loads where `phyloio_paint.mjs` covered the rung (Table 23), the single
    ceiling attempt elsewhere, so Tables 1, 2, 3 and 23 cannot disagree.
    """
    leaves, p = row["leaves"], row["phyloio"]
    if leaves in paint_by:
        r = paint_by[leaves]
        painted = [load for load in r["per_load"] if load["outcome"] == "painted"]
        heaps = [load["heap_bytes"] for load in painted if load.get("heap_bytes") is not None]
        done = [load["phases"]["toCompare"] for load in painted if load["compared"]]
        return {
            "ok": bool(painted), "n": len(painted), "of": r["loads"],
            "paint_s": r["paint_ms_median"] / 1000,
            "compare_s": median(done) / 1000 if len(done) == len(painted) and done else None,
            "heap": median(heaps) / MIB if heaps else None,
            "paths": r["paths_median"], "dom": r["dom_nodes_median"], "phases": None,
        }
    if not p.get("ok"):
        why = "crashed" if "crashed" in p["failed"] else OVER_ATTEMPT
        return {"ok": False, "why": why, "n": 0, "of": 1}
    ph = p.get("phases") or {}
    return {
        "ok": True, "n": 1, "of": 1, "paint_s": ph.get("postFetch", p["ms"]) / 1000,
        "compare_s": ph["toCompare"] / 1000 if ph.get("compareComplete") else None,
        "heap": heap_mib(p), "paths": (p.get("drawn") or {}).get("paths"),
        "dom": (p.get("dom") or {}).get("nodes"), "phases": ph,
    }


readings = {row["leaves"]: phyloio_reading(row) for row in rows}


print("# PhyloDelta vs Phylo.io — measured comparison\n")
print("## Environment\n")
print("| | |")
print("|---|---|")
machine = env["machine"]
tool = env["phyloio"]
times = env["runtimes"]
store = env["store"]
settings = env["settings"]
print(f"| Machine | {machine['chip']} laptop — **{machine['performance_cores']} performance + "
      f"{machine['efficiency_cores']} efficiency cores**, {machine['memory_gib']} GiB |")
print(f"| OS | macOS {env['os']['product']} (build {env['os']['build']}, "
      f"Darwin {env['os']['kernel']}) |")
print(f"| Browser | {ceiling['browser']}, **headless**, system Chrome via Playwright's "
      "`channel: \"chrome\"` |")
print("| Browser flags | " + ", ".join(f"`{f}`" for f in env["browser_flags"]) +
      " — **both tools, identically** |")
print(f"| Viewport | {ceiling['viewport']['width']} x {ceiling['viewport']['height']}; "
      "Table 21 varies the height |")
print(f"| **Tool compared against** | **phylo.io {tool['version']}** ({PHYLOIO_RELEASED}, "
      f"npm `{tool['name']}`), its own published `dist/`, unmodified, sha256 "
      f"`{tool['dist_sha256'][:12]}…` — the current release at the time of measurement |")
print(f"| This project | measured at commit {_commit()}, {env['started']} to {env['finished']} |")
print(f"| Runtimes | Python {times['python']} (`uv` {times['uv']}), Node {times['node']}, "
      f"Playwright {times['playwright']} |")
print("| Backend database | SQLite, in the store directory |")
print(f"| Store location | {store['file_system']} on a solid-state volume, **not** a RAM disk |")
print(f"| **Backend threads** | **{settings['PHYLODELTA_THREADS']} of the "
      f"{machine['performance_cores'] + machine['efficiency_cores']} cores** "
      f"(`PHYLODELTA_THREADS={settings['PHYLODELTA_THREADS']}`) |")
print(f"| MAST budget | `PHYLODELTA_METRIC_MEMORY={settings['PHYLODELTA_METRIC_MEMORY']}`, "
      "a campaign setting: the code has no default |")
print("| Transport | one origin, one fresh page per measurement; uncompressed "
      "except Table 20, which is gzip |")
power = "; ".join(sorted({env["power_at_start"], env["power_at_finish"]}))
print(f"| Power state | recorded, at the start and at the end: {power} |")
print()
print("**Every figure here comes from one clean clone of the tag above**, by "
      "`harness/run_campaign.sh`, on a store built from scratch. The one exception "
      "is the 2.1.1 row of the \"Highlight BCN\" probe, kept as history because "
      "that release is no longer the one under test.\n")
if env["moved_during_run"]:
    print(f"**The browser moved, and the record says so.** The campaign recorded "
          f"{env['browser']} at its start. {notes['chrome_update']} `campaign_env.py` "
          f"therefore refused at the end, on `{', '.join(env['moved_during_run'])}`, "
          f"and that refusal stands in `environment.json`. Every browser result "
          f"records the version that ran it, and all of them read {ceiling['browser']}.\n")
if notes.get("ceiling_rerun"):
    print(f"**The ceiling step was run twice.** {notes['ceiling_rerun']}\n")
print("**Measured after the campaign, from the same tag.** Four checks, each in its "
      "own file, which the tables say where they use them: 2,500 leaves run four more "
      "times (`accuracy_repeats.json`), the paint runner at 70,580 "
      "(`phyloio_paint_extra.json`), the 30-minute run at 70,580 and 564,640 "
      "(`endurance_extra.json`), and the comparison given 30 minutes "
      "(`phyloio_long_compare.json`).\n")
print("**The two entries that matter most for checking these numbers** are the "
      "browser flags and the phylo.io version. The heap cap decides *where* a tool "
      "fails, so Table 1's failures are statements about the tool at an 8 GiB cap, "
      "and Table 4's at 16 GiB, not at Chrome's default — and in Table 1 it is raised "
      "for both tools, which is what makes a failure the tool's own ceiling. The version "
      "matters because several findings are about phylo.io's behaviour: the "
      f"\"Highlight BCN\" failure (Table 15) is measured on {tool['version']}, and a "
      "later release may fix it.\n")
print("**Headless, throughout.** Rendering in headless Chrome is not identical to "
      "a visible window, and these are partly rendering measurements — so this is "
      "a real caveat, not a footnote. It applies equally to both tools, so the "
      "*comparison* holds; the absolute paint times would need re-taking in a "
      "headed browser to be quoted as what a user sees.\n")
_one = {r["leaves"]: r["build_s"] for r in pinned[1]["rungs"]}
_top = max(_one)
_s2, _s10 = _one[_top] / deploy_build[_top], _one[_top] / ten_thread[_top]
print(f"**Only {DEPLOY_THREADS} of the {machine['performance_cores'] + machine['efficiency_cores']} "
      f"cores are used for the backend**, deliberately. Table 9 is the measurement "
      f"behind that choice: at {_top:,} leaves two threads give {_s2:.2f}x at "
      f"{_s2 / 2:.0%} efficiency where ten give {_s10:.2f}x at {_s10 / 10:.0%}, so "
      f"eight further cores buy the last {_s10 / _s2:.2f}x at a steeply falling "
      "rate. Every build figure in these tables is therefore what a **two-core** "
      "deployment costs, not what this machine can do flat out.\n")


# --- 0. what to present ---------------------------------------------------
print("## Which of these to present\n")
print(f"{len(TIERS)} tables is more than a chapter can carry, and most were made to "
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
_bytes = transfer["rows"][-1]
print(f"*If only one table can be shown, it is 19.* It states the claim in the "
      f"quantity the claim is about — {_bytes['phylodelta']['data'] / KIB:,.1f} KiB "
      f"against {_bytes['phyloio']['data'] / MIB:,.1f} MiB at {_bytes['leaves']:,} "
      "leaves — and it is the only table whose ratio grows without bound while "
      "everything on this side stays flat.\n")
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
      "column shows only the two parsed trees, which is why it *drops* at "
      "17,645. It is a lower bound, not the tool's memory. Table 4's RSS "
      "figures, which cover the whole renderer including workers, are the "
      "honest memory numbers.\n")
print("Cold start to an interactive comparison. Phylo.io is split into *paint* "
      "(two trees drawn) and *compare* (its best-corresponding-node worker "
      "finished), because only the second is the same job PhyloDelta is doing: "
      "a slice arrives with its similarity values already in it.\n")
print("**PhyloDelta's column is the median of six samples** (Table 7), taken before "
      "any phylo.io load had run, not the one sample `ceiling.mjs` takes after each "
      "phylo.io attempt. That single sample is not fit to quote: a phylo.io attempt "
      "that overruns its deadline leaves its renderer working while PhyloDelta is "
      "measured, and one pass of those rows read up to "
      f"{max(r['phylodelta']['ms'] for r in load('ceiling_first_pass.json', {'rows': rows})['rows']) / 1000:.2f} s. "
      f"A second pass, with the same overlap, read at most "
      f"{max(r['phylodelta']['ms'] for r in rows if r.get('phylodelta', {}).get('ms')) / 1000:.2f} s, so "
      "the overlap is the setting of those readings and not an isolated cause. phylo.io "
      "is one load per rung, except 17,645, 35,290 and 70,580 (marked †), which are the "
      "median of three from Table 23.\n")
print(f"*`{OVER_ATTEMPT}` is the attempt's budget, not a failure of the tool: its renderer "
      "was still working when the attempt ended (Table 4). `crashed` is the "
      "renderer's own failure. `did not finish in 600 s` is the budget this table "
      "gives the comparison; Table 4 gives it 30 minutes.*\n")
print("| leaves | phylo.io paint | phylo.io compare | phylo.io main-thread heap | PhyloDelta, median of 6 | PhyloDelta heap | PhyloDelta advantage | server precompute |")
print("|---:|---:|---:|---:|---:|---:|---:|---:|")
for row in rows:
    leaves = row["leaves"]
    p, d = readings[leaves], repeat_by[leaves]
    mark = " †" if leaves in paint_by else ""
    if p["ok"]:
        paint_cell = fmt(p["paint_s"], " s")
        comp = fmt(p["compare_s"], " s", 0) if p["compare_s"] else "**did not finish in 600 s**"
        heap = fmt(p["heap"], " MiB")
    else:
        paint_cell = comp = heap = f"**{p['why']}**"
    # Compared against phylo.io's COMPARE time, not its paint: that is the
    # point at which it is doing the same job.
    ratio = f"**{p['compare_s'] * 1000 / d['median_ms']:,.0f}x**" if p.get("compare_s") else "—"
    if not p["ok"] or not p.get("compare_s"):
        ratio = "**only PhyloDelta in budget**"
    print(
        f"| {leaves:,}{mark} | {paint_cell} | {comp} | {heap} | "
        f"{d['median_ms'] / 1000:.2f} s | {heap_mib(d):.1f} MiB | {ratio} | "
        f"{fmt(precompute_s(leaves), ' s')} |"
    )

# --- 2. fairness ----------------------------------------------------------
table(2, "What each tool actually drew")
print("The check that makes Table 1 admissible. An earlier comparison in this "
      "project reported a ~34x speedup that was an artefact of the two tools "
      "rendering 91 and 2,002 nodes. **Both tools draw a roughly constant "
      "amount** — so the difference in Table 1 is not "
      "\"one of them drew less\".\n")
print("> The 17,645, 35,290 and 70,580 rows show phylo.io's **pre-comparison** render, the "
      "median of three loads: when the worker finishes it rebuilds and redraws both "
      "panels with the similarity colouring, and where it never finishes that second "
      "render never happens. That is why the counts drop at 17,645. The point "
      "of the table is unaffected — the counts stay in one range, never "
      "proportional to the tree. Node counts are CDP's `domCounters` in "
      "every row.\n")
print("| leaves | phylo.io SVG paths | phylo.io DOM nodes | PhyloDelta canvases | PhyloDelta tips drawn |")
print("|---:|---:|---:|---:|---|")
for row in rows:
    p, d = readings[row["leaves"]], row["phylodelta"]
    shown = (d.get("drawn") or {}).get("shown") or []
    tips = shown[0].split(" of ")[0].replace("showing ", "") if shown else "—"
    left = f"{p['paths']:,} | {p['dom']:,}" if p["ok"] else f"{p['why']} | {p['why']}"
    print(f"| {row['leaves']:,} | {left} | "
          f"{(d.get('drawn') or {}).get('canvases', '—')} | {tips} per panel |")

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
    leaves = row["leaves"]
    p, d = readings[leaves], repeat_by[leaves]
    finished = bool(p.get("compare_s"))
    heap = p.get("heap")
    growth = f"{heap / previous:.2f}x" if heap and previous and finished else "—"
    if p["ok"]:
        note = "" if finished else " *(compare unfinished — worker excluded)*"
    else:
        note = f" *({p['why']})*"
    print(f"| {leaves:,} | {fmt(heap, ' MiB')}{note} | {growth} | {heap_mib(d):.1f} MiB |")
    if heap and finished:
        previous = heap

# --- 4. failure -----------------------------------------------------------
if endurance:
    table(4, "Failure behaviour, given 30 minutes and 16 GiB")
    print("Table 1's limits are against a stated budget. This lifts it: 30 minutes "
          f"with a 16 GiB heap cap on a {machine['memory_gib']} GiB machine.\n")
    print("| leaves | outcome | time | peak renderer (MiB) |")
    print("|---:|---|---:|---:|")
    for r in sorted(endurance + endurance_extra, key=lambda r: r["leaves"]):
        ph = r.get("phases") or {}
        if ph.get("compareComplete"):
            outcome = "comparison finished"
        elif ph:
            # Runs at v0.1.0 left the page's load() at its default wait and
            # called its end `ok`, so these rows carry no budget of their own.
            waited = r.get("compare_budget_ms", 600_000) / 1000
            outcome = (f"painted in {ph['postFetch'] / 1000:.0f} s; **comparison unfinished "
                       f"when the page's own {waited:.0f} s wait ended**")
        elif "crashed" in r.get("why", ""):
            outcome = "**renderer process crashed**"
        else:
            outcome = "**nothing painted when the 30 minutes ended**"
        print(
            f"| {r['leaves']:,} | {outcome} | {r['ms'] / 60000:.1f} min | "
            f"{r['peak_renderer_mb']:,} MiB |"
        )
    print("\n*Peak memory is sampled every 2 s from process RSS, so it is a lower "
          "bound and the figures should not be read as an ordering.*\n")
    print("*The tag's `endurance.mjs` lifts the budget for the load as a whole, not for "
          "the comparison inside it: it calls the page's `load()` without a compare "
          "budget, and that defaults to 600 s. Its `ok` therefore does not mean the "
          "comparison finished, which is why this table reads `compareComplete`.*\n")
    if long_compare:
        print("**The comparison itself, given 30 minutes.** The same page, with `load()` "
              "told 1,800 s. One load per rung, run after the campaign from the same tag.\n")
        print("| leaves | paint | comparison | time | peak renderer (MiB) |")
        print("|---:|---:|---|---:|---:|")
        for r in long_compare["rows"]:
            ph = r.get("phases") or {}
            if ph.get("compareComplete"):
                cell = f"**finished in {ph['toCompare'] / 1000:.0f} s**"
            elif r.get("ok"):
                cell = "**unfinished at 30 minutes**"
            elif "crashed" in r.get("why", ""):
                cell = "**renderer process crashed**"
            else:
                cell = "**stopped by the outer 35-minute limit**"
            paint_cell = f"{ph['postFetch'] / 1000:.1f} s" if ph.get("postFetch") else "—"
            print(f"| {r['leaves']:,} | {paint_cell} | {cell} | {r['ms'] / 60000:.1f} min | "
                  f"{r['peak_renderer_mb']:,} MiB |")
        print()
        print(long_compare["summary"] + "\n")

# --- 5. accuracy ----------------------------------------------------------
accuracy = []
for path in RESULTS.glob("bcn_accuracy*.json"):
    accuracy.append(json.loads(path.read_text()))
accuracy.sort(key=lambda a: a["leaves"])
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
            f"| {a['leaves']:,} | {n:,} | {a['exact_match']:,} ({a['exact_match']/n:.1%}) | "
            f"{a['worse']:,} ({a['worse']/n:.1%}) | {a['gap_median']:.3f} | {a['gap_worst']:.3f} | "
            f"{a['higher_than_exact']} |"
        )
    print("\n*`beat exact` must be 0: an exhaustive search cannot be beaten by a "
          "subset of the same candidates. It is reported as a check on the "
          "method, not as a result.*\n")
    print("*`clades` is the clades both sides scored. A clade phylo.io leaves "
          "unscored has no gap to compare, so it drops out here.*\n")
    if accuracy_repeats:
        print(accuracy_repeats["summary"] + "\n")

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
    if not p.get("ok") and row["leaves"] in paint_by:
        # The median load's phases: the ceiling attempt itself ended at its limit.
        r = paint_by[row["leaves"]]
        p = {"ok": True, "phases": next(x["phases"] for x in r["per_load"]
                                        if x.get("paint_ms") == r["paint_ms_median"])}
    if not p.get("ok"):
        why = readings[row["leaves"]].get("why")
        print(f"| {row['leaves']:,} | — | — | — | **{why}** | — |")
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
    print("Six samples per rung after a discarded warm-up: the source of Table 1's "
          "PhyloDelta column.\n")
    print("| leaves | nodes | median | min | max | heap |")
    print("|---:|---:|---:|---:|---:|---:|")
    for r in repeats:
        print(
            f"| {r['leaves']:,} | {r['leaves'] * 2 - 1:,} | **{r['median_ms'] / 1000:.2f} s** | "
            f"{r['min_ms'] / 1000:.2f} s | {r['max_ms'] / 1000:.2f} s | {heap_mib(r):.1f} MiB |"
        )

# --- 5d. the server side ---------------------------------------------------
if server:
    two_thread = deploy_build
    table(8, "The precompute PhyloDelta pays instead")
    print("Measured through the real upload path: POST the bundle, a worker "
          "claims it, poll until ready. Includes ingest, reconciliation, the "
          "correspondence search and the metrics asked for. **Twice**, because the "
          "two answers differ: (a) `rf` alone, which is what `DEFAULT_UPLOAD_METRICS` "
          "builds and the upload form's default; (b) `rf,mast`, one upload computed by "
          "two metrics, which the app lists as two comparisons (§52), with MAST run "
          "where its memory estimate fits the budget and declined where it does not. "
          "Each build's metrics are read back from the pair.\n")
    print("| leaves | (a) `rf`, 2 threads | (a) `rf`, 10 threads | (b) `rf,mast`, 2 threads | MAST in (b) | bundle size |")
    print("|---:|---:|---:|---:|---|---:|")
    app_by = {r["leaves"]: r for r in app_builds}
    for leaves in sorted(server):
        r, app = server[leaves], app_by[leaves]
        failed = (app.get("metrics_failed") or {}).get("mast")
        if failed:
            need = re.search(r"about ([\d.,]+ GiB)", failed)
            state = f"declined (needs ~{need.group(1)}, an estimate)"
        else:
            state = "computed" if "mast" in app["metrics_ready"] else "**missing**"
        print(f"| {leaves:,} | **{two_thread[leaves]:.1f} s** | {ten_thread[leaves]:.1f} s | "
              f"{app['build_s']:.1f} s | {state} | {r['bytes'] / MIB:.1f} MiB |")
    print("\n*The ~2 s floor at small sizes is the worker's poll interval, not "
          "work.*")

# Emitted only once both pinned runs exist, so a half-finished experiment
# cannot appear as a finished table.
if all(pinned.values()):
    table(9, "Build time at pinned thread counts")
    print("The same builds with the count pinned, `rf` only, through the same "
          "upload path, each on its own store. **Every row read its thread count back "
          "from the pair it built**, and the run refuses if the answer differs: "
          f"{sum(len(pinned[n]['rungs']) for n in pinned)} builds, none of them "
          "refused.\n")
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
    mono = all(one[x] / ten_thread[x] <= one[y] / ten_thread[y] for x, y in zip(big, big[1:], strict=False))
    print(f"\n**Read the larger rows.** From {lo:,} to {hi:,} two threads rise "
          f"{one[lo]/two[lo]:.2f}x -> {one[hi]/two[hi]:.2f}x and ten "
          f"{one[lo]/ten_thread[lo]:.2f}x -> {one[hi]/ten_thread[hi]:.2f}x"
          f"{'' if mono else f', peaking at {max(one[n]/ten_thread[n] for n in big):.2f}x, so the ten-thread gain is not monotone at the top of the ladder'}. "
          f"The gain grows with size because below ~70,000 leaves the *serial* parts "
          f"— parse, reconcile, ingest, and the 2 s poll — are most of the elapsed "
          f"time, and threading the search cannot touch them. Amdahl's law, visible "
          f"directly.\n")
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
    by = {r["threads"]: r for r in scaling["rungs"]}
    p_cores = machine["performance_cores"]
    knee, full = by[p_cores], by[machine["performance_cores"] + machine["efficiency_cores"]]
    print(f"The knee is at **{p_cores} threads**, the number of performance cores on "
          f"this machine. One to {p_cores} threads buys {knee['speedup']:.2f}x at "
          f"{knee['efficiency']:.0%} efficiency; {p_cores} to {full['threads']} buys only "
          f"another {full['speedup'] / knee['speedup']:.2f}x and drops efficiency to "
          f"{full['efficiency']:.0%}. On a shared machine {p_cores} threads is the better "
          f"trade: {knee['seconds'] / full['seconds']:.1f}x slower than {full['threads']}, "
          f"for {full['threads'] / p_cores:.1f}x fewer cores.")

memory = load("build_memory.json")
memory_ten = load("build_memory_10threads.json")
if memory:
    table(11, "What the server needs while it builds")
    print("Peak RSS of the worker process, sampled every 200 ms against its "
          f"idle baseline of {memory['idle_rss_mb']:,.0f} MiB. Measured in a "
          "throwaway store so nothing else was disturbed.\n")
    print("**The search is quadratic in time but LINEAR in memory** — every "
          "doubling of leaves roughly doubles the footprint. The pruning bound "
          "means it never materialises an n x n matrix: it holds the two trees' "
          "columns, which are memory-mapped, and one scratch buffer per "
          "thread. For contrast, building these trees with NJ would need "
          "~466 GiB of distance matrix at 500,000 taxa.\n")
    if memory_ten:
        print("Both thread settings are shown, compared on **absolute peak "
              "RSS**, the figure neither idle baseline can distort.\n")
        ten_by = {r["leaves"]: r for r in memory_ten["rungs"]}
        print("| leaves | peak RSS (2 thr, MiB) | peak RSS (10 thr, MiB) | difference | marginal (2 thr) | growth |")
        print("|---:|---:|---:|---:|---:|---:|")
        previous = None
        for row in memory["rungs"]:
            other = ten_by.get(row["leaves"])
            peak = row["peak_rss_mb"]
            marginal = row["over_idle_mb"]
            # "difference", not "saved": measured on an idle machine the two
            # thread counts are within 0-3%, and an earlier version of this
            # table reported a 25-39% saving that came from a contaminated
            # 2-thread figure. A column headed "saved" asserts a direction the
            # numbers do not support.
            saved = f"{1 - peak / other['peak_rss_mb']:+.0%}" if other else "—"
            other_peak = f"{other['peak_rss_mb']:,.0f} MiB" if other else "—"
            # Growth is taken on the MARGINAL figure, not on peak RSS: peak
            # carries a fixed ~33 MiB interpreter baseline that dilutes every
            # ratio and would make linear growth read as 1.65x per doubling.
            growth = f"{marginal / previous:.2f}x" if previous else "—"
            print(
                f"| {row['leaves']:,} | **{peak:,.0f} MiB** | {other_peak} | "
                f"{saved} | {marginal:,.0f} MiB | {growth} |"
            )
            previous = marginal or None
        spread = [abs(1 - r["peak_rss_mb"] / ten_by[r["leaves"]]["peak_rss_mb"])
                  for r in memory["rungs"] if r["leaves"] >= 17_645]
        print(f"\n**The thread count barely affects memory.** From 17,645 leaves up "
              f"the two runs differ by at most {max(spread):.0%}, in no fixed direction. "
              "The per-thread scratch buffers are small against the memory-mapped "
              "columns. Below that the peaks sit a few MiB above idle and the 200 ms "
              "sampling decides the sign of the difference.\n")
        print("*Every byte figure in these tables is binary — KiB, MiB, GiB "
              "(2^10, 2^20, 2^30). `ps -o rss` reports KiB natively; heap and "
              "transfer counts are raw byte counts divided by 2^20. Mixing "
              "decimal and binary is how a table comes to state two different "
              "things under one heading, and this one did for a while.*\n")
        print("*Build times are omitted here. This run measures memory, and "
              "Table 8's figures are the ones to quote for time.*")
    else:
        print("| leaves | build | peak RSS | over idle | growth |")
        print("|---:|---:|---:|---:|---:|")
        previous = None
        for r in memory["rungs"]:
            over = r["over_idle_mb"]
            growth = f"{over / previous:.2f}x" if previous else "—"
            print(
                f"| {r['leaves']:,} | {r['build_s']:.1f} s | {r['peak_rss_mb']:,.0f} MiB | "
                f"**{over:,.0f} MiB** | {growth} |"
            )
            previous = over or None

# --- 5e. the mechanism, directly ------------------------------------------
latency = load("slice_latency.json", [])
if latency:
    table(12, "The request a panel actually makes")
    first, last = latency[0], latency[-1]
    print("The **cause**, where every other table shows the consequence. The "
          "same GET the frontend issues, at every tree size, read-only. "
          "Latency and payload are set by the viewport budget, so neither "
          f"tracks the tree: **{last['leaves'] / first['leaves']:.0f}x more leaves, the "
          "same few milliseconds and the same few kilobytes.**\n")
    print("Measured twice, each with `correspondence=metric` as the app asks: on the "
          "`rf` store, and with `metric=mast` on the store built with `rf,mast` — the "
          "slice of a MAST comparison, coloured by MAST's own correspondence (§52). "
          "Where MAST was declined the pair has no such metric and the server says so "
          "by name.\n")
    print("| leaves | median | min | max | response | gzip | leaves drawn | `metric=mast` median | response | gzip |")
    print("|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    for r in latency:
        m = latency_mast.get(r["leaves"], {})
        right = (f"{m['median_ms']:.1f} ms | {m['bytes'] / KIB:.1f} KiB | "
                 f"{m['gzip_bytes'] / KIB:.1f} KiB"
                 if m.get("median_ms") is not None else "declined | — | —")
        print(
            f"| {r['leaves']:,} | **{r['median_ms']:.1f} ms** | {r['min_ms']:.1f} ms | "
            f"{r['max_ms']:.1f} ms | {r['bytes'] / KIB:.1f} KiB | "
            f"{r['gzip_bytes'] / KIB:.1f} KiB | {r['displayed_leaves']} | {right} |"
        )
    print(
        f"\n*From {first['leaves']:,} to {last['leaves']:,} leaves — a "
        f"{last['leaves'] / first['leaves']:.0f}x increase — the median moves "
        f"{first['median_ms']:.1f} ms to {last['median_ms']:.1f} ms and the "
        f"payload {first['bytes'] / KIB:.1f} KiB to {last['bytes'] / KIB:.1f} KiB. "
        "Seven samples per rung after a warm-up, since the first touch of a "
        "store memory-maps it.*")

# --- 6. the honest ledger -------------------------------------------------
table(13, "What the design costs")
print("| | phylo.io | PhyloDelta |")
print("|---|---|---|")
print("| Server required | no | **yes** |")
print("| Precompute before first view | none | up to "
      f"{max(deploy_build.values()):.0f} s at {DEPLOY_THREADS} threads, `rf` alone; "
      f"{max(r['build_s'] for r in app_builds):.0f} s as the app uploads it |")
print("| Whole tree ever visible | yes, in memory | **no, never transferred** |")
print("| Works offline from a file | yes | no |")
print("| Comparison recomputed on demand | yes | no, fixed at build |")

table(14, "Provenance of the test data")
print("| rung | origin |")
print("|---:|---|")
print("| 1,000 – 10,000 | pruned subsamples of the real vibrio NJ/UPGMA pair |")
print("| 17,645 | **the real pair, unmodified** |")
print("| 35,290 – 564,640 | nested relabelled copies of the real pair, preserving depth and imbalance |")
print("\n*Read from the Newick text by `tools/ladder_stats.py`, not through the "
      "parser under test. Depth is edges from the root to the deepest leaf. Tree a "
      "is NJ and tree b UPGMA.*\n")
print("| rung | leaves a | leaves b | shared | clades a | clades b | depth a | depth b |")
print("|---:|---:|---:|---:|---:|---:|---:|---:|")
for r in stats:
    a, b = r["a"], r["b"]
    print(f"| {r['rung']:,} | {a['leaves']:,} | {b['leaves']:,} | {r['shared_fraction']:.4%} "
          f"| {a['clades']:,} | {b['clades']:,} | {a['max_depth']:,} | {b['max_depth']:,} |")
_partial = [r for r in stats if r["shared_fraction"] < 1]
print(f"\n*Pruned rungs share 100% of their leaves. From {_partial[0]['rung']:,} up one "
      f"real leaf, ST 211, is in the UPGMA tree only (§2.6) and every nested copy "
      f"carries it, so {_partial[-1]['shared_fraction']:.4%} is shared and "
      f"{_partial[-1]['b']['leaves'] - _partial[-1]['a']['leaves']:,} leaves are not at "
      "the top rung. PhyloDelta reconciles them away; phylo.io is handed them. Depth "
      f"runs {min(r['a']['max_depth'] for r in stats)} to "
      f"{max(r['a']['max_depth'] for r in stats)} on the NJ side and "
      f"{min(r['b']['max_depth'] for r in stats)} to "
      f"{max(r['b']['max_depth'] for r in stats)} on the UPGMA side. Real MLST data stops "
      "at 27,962 leaves (clostridium), so rungs above 17,645 are synthetic and are used "
      "only for performance claims.*")


# --- 7. navigating, once loaded -------------------------------------------
if nav_rows:
    table(15, "Navigation responsiveness, once the comparison is open")
    print("*Median milliseconds from the action to a painted result, with the frame "
          f"count at {FRAME_MS:.2f} ms beside it, up to {navigation['samples']} operations "
          "per cell after up to 3 discarded warm-ups, one page load per tool per rung.*\n")
    print("**Every figure here is a frame count.** The clock stops after two nested "
          "`requestAnimationFrame` callbacks, so a sample is quantised to the display, "
          "and a 2 ms difference in real work moves it a whole frame (§34.14). The gap "
          "between the two tools cannot be resolved by this harness. The claim that "
          "survives is that both answer well inside the 100 ms an interaction is "
          "allowed.\n")
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
        ms = got.get("median_ms")
        if ms is None:
            return "**fails**"
        return f"{ms:.1f} ms ({round(ms / FRAME_MS)} f) n={got['n']}"

    for row in nav_rows:
        pi, pd = row.get("phyloio", {}), row.get("phylodelta", {})
        n = row["leaves"]
        print(f"| {n:,} | {nav(pi, 'expand', n, 'phyloio')} | {nav(pi, 'back', n, 'phyloio')} "
              f"| {nav(pi, 'jump', n, 'phyloio')} "
              f"| {nav(pd, 'expand')} | {nav(pd, 'back')} | {nav(pd, 'jump')} |")

    last_done = max(n for n in readings if readings[n].get("compare_s"))
    print(f"\n**\"No comparison\" is not slow navigation.** phylo.io paints both trees at "
          "17,645 leaves but its best-corresponding-node worker never finishes there "
          "inside the 600 s budget (Tables 1 and 23), so in compare mode there is nothing "
          f"to navigate. Its navigation is therefore measurable only to **{last_done:,} "
          f"leaves**, where the comparison completes in {readings[last_done]['compare_s']:.0f} s. "
          "PhyloDelta is measured at 17,645 anyway, because holding flat is the claim.\n")
    print("**Both tools are driven one layer below the click** — phylo.io through "
          "`container.trigger_(action, …)`, which is exactly what its context-menu items call, and "
          "PhyloDelta through the actions its menu items call. Synthesising a click on a WebGL "
          "canvas would have charged hit-testing to one side only. What is excluded is the same for "
          "both: opening a menu and pressing an item.\n")
    _pi = [n for r in nav_rows for n in r["phyloio"].get("sizes", [])]
    _pd = [n for r in nav_rows for n in r["phylodelta"].get("sizes", [])]
    print(f"**The operations are not equivalent in what they reveal.** phylo.io holds the "
          f"whole tree, so it collapses and expands clades of {min(_pi):,} to {max(_pi):,} "
          f"leaves and draws all of them. PhyloDelta's targets are the wedges in the "
          f"current slice, {max(_pd):,} leaves down to {min(_pd):,}, and expanding one "
          "draws about fifty tips.\n")

    # What the cache actually contributed, and where the time goes instead.
    table(16, "Where a PhyloDelta navigation's time goes")
    print("*Fetch times are Resource Timing, so they are not quantised to the frame. A "
          "jump is one request, `/slice?around=` (§40); the expand and back fetches are "
          "the requests inside the step.*\n")
    print("| leaves | expand total | of which fetch | back total | of which fetch | "
          "back, cache emptied | of which fetch | jump total | of which fetch |")
    print("|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    for row in nav_rows:
        pd = row["phylodelta"]
        f = pd["fetch_ms"]
        def med(o):
            return fmt((o or {}).get("median_ms"), " ms")
        print(f"| {row['leaves']:,} | {med(pd.get('expand'))} | {med(f.get('expand'))} "
              f"| {med(pd.get('back'))} | {med(f.get('back'))} "
              f"| {med(pd['uncached'].get('back'))} | {med(f.get('cold_back'))} "
              f"| {med(pd.get('jump'))} | {med(f.get('jump'))} |")
    print("\n*Cached and uncached are interleaved in one page against the same target, because "
          "measuring them in separate browsers reported the uncached run as three times FASTER — "
          "the first run was paying for a cold server and the second inherited a warm one. The "
          "uncached pass runs first, so any residual warming works against the cache.*\n")
    _expand = [r["phylodelta"]["expand"]["median_ms"] for r in nav_rows]
    _fetch = [r["phylodelta"]["fetch_ms"]["expand"]["median_ms"] for r in nav_rows]
    print(f"**The cache works and it barely matters.** On a hit the network cost of a "
          f"navigation is **0 ms**, which is the cache doing exactly its job — and the "
          f"navigation takes the same total time, because the round trip was never the "
          f"cost. An uncached fetch is {min(_fetch):.1f}–{max(_fetch):.1f} ms of a "
          f"~{median(_expand):.0f} ms navigation, and the remainder is two frames of "
          "detector plus building the tree and drawing it. Every headline figure in "
          "Tables 1–14 was measured with no caching at all, so they are a floor rather "
          "than a best case.\n")

    # phylo.io's jump does not survive compare mode.
    broken = [r for r in nav_rows
              if (r.get("phyloio", {}).get("failure_count") or 0) > 0]
    if broken:
        first = broken[0]["phyloio"]["failures"][0]
        print("\n### Table 15 note — phylo.io's \"Highlight BCN\" is intermittent\n")
        tried = sum(r["phyloio"].get("failure_count") or 0 for r in broken)
        print(f"All {tried} attempts in the navigation run above failed, at each of the "
              f"{len(broken)} rungs with a comparison, with the same error:\n")
        print(f"> `{first.get('error')}`\n")
        print("**But that is one page load per rung, and the failure is intermittent.** "
              "A dedicated probe over repeated loads of the same pair at 1,000 leaves:\n")
        if bcn_211 or bcn_225:
            print("| phylo.io | page loads | loads where the jump worked | attempts succeeded |")
            print("|---|---:|---:|---:|")
            for d in (bcn_211, bcn_225):
                if d:
                    print(f"| {d['label']} | {d['loads']} | {d['loads_with_any_success']} "
                          f"| {d['attempts_succeeded']}/{d['attempts_total']} |")
            print()
        worked = [load for load in bcn_225["per_load"] if load["succeeded"]]
        print(f"The honest claim is that the jump fails in most loads, not that it never "
              f"works. It is **not** all-or-nothing within a load: in the "
              f"{len(worked)} of {bcn_225['loads']} loads where it worked at all, "
              f"{sum(w['succeeded'] for w in worked)} of "
              f"{sum(w['attempted'] for w in worked)} attempts succeeded. Table 15 reports "
              "one load per rung, which is why it shows only the common outcome.\n")
        print("**The mechanism, and why it is conditional.** It is reached only from the "
              "context-menu item of that name (`viewer.js` line 1175 is the sole caller). `api.js` "
              "builds **two separate models** from the BCN worker's reply, and the `elementBCN` "
              "references inside the first point at that reply's own embedded copy of the second "
              "tree. `getHierarchyNodeFromModelNode` compares by object identity, so whether it "
              "finds anything depends on whether structured-clone identity between the two halves "
              "of one message survives into the rebuilt models — which is evidently not "
              "guaranteed. When it does not, the lookup returns null and `expandToRoot` hands that "
              "null to `apply_collapse_from_data_to_d3`, which reads `_children` on it.\n")
        if ceiling_225:
            done = ceiling_225["per_load"][0]["completed"]
            print(f"The ceiling was measured directly on {ceiling_225['label']}: at "
                  f"**{ceiling_225['leaves']:,} leaves** a further load's comparison "
                  f"**{'completed' if done else 'did not complete'}** inside a 600 s budget. "
                  "That is the one claim the whole of Table 1 rests on.\n")
        print("It still sharpens the comparison rather than softening it: the cross-tree jump is "
              "the operation PhyloDelta's design is most open to criticism over — it costs "
              "a slice the panel has never held — and it is the one the comparison tool "
              "manages only sometimes.\n")


# --- 8. does the metric change the cost? ----------------------------------
phase_rows = metric_phases.get("rows", [])
if phase_rows:
    table(17, "Does the chosen metric change what a build costs?", lead="\n\n")
    print("*Seconds, from the worker's own per-metric timings at "
          "`PHYLODELTA_THREADS=2`. \"Shared\" is what every metric in a set pays "
          "once: parse, reconcile, correspondence, store.*\n")
    # Every metric the widest build asked for, in the order it asked: from v0.2.0
    # that is all five, MAST and SPR included (§52-§54).
    shown = max(
        (b["metrics"] for r in phase_rows for b in r["builds"]), key=len
    )
    print("| leaves | shared work | " + " | ".join(shown) + " | total | metrics as % of total |")
    print("|---:|---:|" + "---:|" * len(shown) + "---:|---:|")

    def secs(value):
        # `is not None`, not truthiness: a real 0.0 s must not print as "—".
        return f"{value:,.1f} s" if value is not None else "—"

    for row in phase_rows:
        widest = max(row["builds"], key=lambda b: len(b["metrics"]))
        per = widest.get("per_metric", {})

        def one(name, per=per):
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
        print(f"| {row['leaves']:,} | {secs(shared)} | "
              + " | ".join(one(m) for m in shown)
              + f" | {secs(total)} | {share} |")

    top = max(phase_rows, key=lambda r: r["leaves"])
    top_widest = max(top["builds"], key=lambda b: len(b["metrics"]))
    top_per = top_widest.get("per_metric", {})
    cheap = sum(
        top_per[m]["seconds"] for m in ("rf", "rf-treediff")
        if isinstance(top_per.get(m), dict) and "seconds" in top_per[m]
    )
    trip = (top_per.get("triplet") or {}).get("seconds")
    mid = next(r for r in phase_rows if r["leaves"] == 141_160)
    mid_widest = max(mid["builds"], key=lambda b: len(b["metrics"]))
    mid_per = mid_widest["per_metric"]
    top_total = top_widest.get("total_s") or 0
    trip_share = f"{trip / top_total * 100:.0f}%" if trip and top_total else "—"
    mid_trip = (mid_per.get("triplet") or {}).get("seconds")
    mid_shared = mid_widest.get("shared_s")
    # Worked out, not written down: the claim has to follow the numbers when
    # they are re-measured (triplet runs twice per build since §54).
    mid_claim = (
        f"costs {mid_trip:.1f} s against {mid_shared:.1f} s for all the shared work, adding "
        f"{mid_trip / mid_shared * 100:.0f}% to it"
        if mid_trip and mid_shared else "was not measured"
    )
    print(f"\n**The answer reverses with size, so \"does the metric matter\" has no single "
          f"answer.** `rf` and `rf-treediff` are free at every scale — together {cheap:,.1f} s of a "
          f"{top_total:,.0f} s build at {top['leaves']:,} leaves. `triplet` is not: at 141,160 it "
          f"{mid_claim}. By "
          f"{top['leaves']:,} `triplet` alone is {trip_share} of the build (the "
          f"table's last column counts every metric together), because the shared work is "
          f"O(n^2) and the metric is near-linear, so correspondence overtakes it.\n")
    spr = [(r["leaves"], (max(r["builds"], key=lambda b: len(b["metrics"]))["per_metric"]
                          .get("spr") or {}).get("seconds")) for r in phase_rows]
    spr = [(n, s) for n, s in spr if s is not None]
    if spr:
        n, s = spr[-1]
        print(f"`spr`, by rspr's linear-time approximation (§53), stays small: {s:.1f} s at "
              f"{n:,} leaves. `mast` runs where its memory estimate fits the campaign's "
              f"budget and is **refused** by name above it (§50), so its column stops.\n")
    print("So §9's claim that several metrics cost little more than one is **true "
          "asymptotically and misleading in the middle** — which is where most real trees sit. "
          "The claim should be stated about the *shared* work, which is what is actually shared, "
          "rather than about metrics in general.\n")
    print("**Measured from the worker's log, not from wall-clock differences.** The metric "
          "sets are uploaded in a fixed order, so the \"+triplet\" build is always last, and the "
          "first pass showed it at a suspiciously uniform 1.7-2x the others — the shape of an "
          "ordering artefact rather than a cost. Per-metric timings carry no such confound.\n")
    print(f"*The shared work at {top['leaves']:,} leaves here, {top_widest['shared_s']:.1f} s, "
          f"sits beside Table 9's {deploy_build[top['leaves']]:.1f} s for a whole `rf` build at two "
          "threads: the same work, from the worker's log and from the wall clock.*\n")

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
            # The invariant is a FACTOR, not equality: this store reports the
            # full symmetric difference since the rf metric's v2 and TreeDiff
            # still halves it (§34.19). Written as the factor rather than
            # normalised away so that build data predating v2 shows up here as
            # a disagreement, which is what it is.
            (agree if a == 2 * b else disagree).append((row["leaves"], a, b))
    # Build data written before the rf metric's v2 holds the halved value, so
    # every row fails `rf == 2 * treediff` by being *equal* instead. That is a
    # stale input, not a disagreement between the implementations, and printing
    # it as a column of NOs under prose about agreement would be worse than
    # printing nothing: it reads as a regression in the code.
    stale = bool(disagree) and not agree and all(a == b for _, a, b in disagree)
    if stale:
        table(18, "Two RF implementations against each other")
        print("> **NOT RE-MEASURED.** `metric_builds.json` was written before the "
              "`rf` metric's v2 and holds the halved value: every row has "
              "`rf == rf-treediff`, which was the v1 invariant and is no longer "
              "the right one (§34.19). The implementations have not stopped "
              "agreeing — the input predates the question. Re-run "
              "`tools/measure_metric_builds.py` against a built store and this "
              "table returns; Table 22 checks the same thing against DendroPy "
              "and ETE3 on data that *is* current.\n")
    elif agree or disagree:
        table(18, "Two RF implementations against each other")
        print("| leaves | built-in `rf` | `rf-treediff` | x2 | as expected |")
        print("|---:|---:|---:|---:|:---:|")
        seen = set()
        for leaves, a, b in agree + disagree:
            if leaves in seen:
                continue
            seen.add(leaves)
            print(f"| {leaves:,} | {a:,.0f} | {b:,.0f} | {2 * b:,.0f} | "
                  f"{'yes' if a == 2 * b else '**NO**'} |")
        print(f"\n*{len(agree)} of {len(agree) + len(disagree)} builds match `rf == 2 x "
              f"rf-treediff`.* "
              "Different algorithms over different representations by different authors — "
              "TreeDiff is the reference implementation of the paper this project follows (§1.10) "
              f"— so agreement at {2 * max(l for l, _, _ in agree + disagree) - 1:,} nodes is a "
              "check on both, and a disagreement would have meant one of them was wrong.\n")
        print("**What this table cannot check is the scale**, which is why Table 22 exists. "
              "TreeDiff reports half the symmetric difference and this store used to do the "
              "same; the two agreed at every rung while both differed from the published "
              "definition by a factor of two, and nothing here could have revealed it. Agreement "
              "between two implementations of one paper is evidence that the code is faithful, "
              "not that the quantity is the one the field means.\n")

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
    print("**The last two columns are a MAST comparison in the app**: the store built "
          "with `rf,mast`, opened as its MAST comparison (`m=mast`) where MAST ran and "
          "as its RF one where it was declined. Whether the slices carried MAST is read "
          "from the requests themselves (`metric=mast`).\n")

    def carried(entry):
        slices = [a["url"] for a in entry["phylodelta"]["api"] if "/slice" in a["url"]]
        return "yes" if slices and all("metric=mast" in u for u in slices) else "no"

    print("| leaves | phylo.io app | phylo.io data | phylo.io total | "
          "PhyloDelta app | PhyloDelta data | PhyloDelta total | data ratio | total ratio | "
          "data, app path | slice carried MAST |")
    print("|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|:---:|")

    for row in transfer_rows:
        pi, pd = row.get("phyloio", {}), row.get("phylodelta", {})
        pi_app, pi_data = pi.get("app"), pi.get("data")
        pd_app, pd_data = pd.get("app"), pd.get("data")
        if None in (pi_app, pi_data, pd_app, pd_data):
            print(f"| {row['leaves']:,} | — | — | — | — | — | — | — | — |")
            continue
        pi_total, pd_total = pi_app + pi_data, pd_app + pd_data
        print(
            f"| {row['leaves']:,} | {pi_app / MIB:,.2f} MiB | {pi_data / MIB:,.2f} MiB "
            f"| {pi_total / MIB:,.2f} MiB | {pd_app / MIB:,.2f} MiB "
            f"| **{pd_data / KIB:,.1f} KiB** | {pd_total / MIB:,.2f} MiB "
            f"| **{pi_data / pd_data:,.0f}x** | {pi_total / pd_total:,.0f}x "
            f"| {transfer_app[row['leaves']]['phylodelta']['data'] / KIB:,.1f} KiB "
            f"| {carried(transfer_app[row['leaves']])} |"
        )

    top = transfer_rows[-1]
    tpi, tpd = top["phyloio"], top["phylodelta"]
    first = transfer_rows[0]
    print(f"\n**At {top['leaves']:,} leaves phylo.io must transfer "
          f"{tpi['data'] / MIB:,.1f} MiB of tree and still cannot open the "
          f"comparison** (Table 1). PhyloDelta transfers "
          f"{tpd['data'] / KIB:,.1f} KiB and shows it. The data column is the one "
          f"that matters for the claim: it is flat — "
          f"{first['phylodelta']['data'] / KIB:,.1f} KiB at "
          f"{first['leaves']:,} leaves and {tpd['data'] / KIB:,.1f} KiB at "
          f"{top['leaves']:,} — against a download that grows linearly with the "
          f"tree.\n")
    chunks = sorted((u["bytes"] for u in tpi["byUrl"] if u["url"].endswith(".js")), reverse=True)
    print("**The application bundles run the other way, and by more than "
          f"expected.** phylo.io's is {tpi['app'] / MIB:,.2f} MiB — `phylo.js` at "
          f"{chunks[0] / MIB:.2f} MiB plus two worker chunks at {chunks[1] / MIB:.2f} and "
          f"{chunks[2] / MIB:.2f} MiB — against PhyloDelta's "
          f"{tpd['app'] / MIB:,.2f} MiB. So PhyloDelta transfers less **in total at "
          "every rung including the smallest**, which was not the expected result: "
          "the prediction was that it would lose on total bytes on small trees and "
          "win only through the data column.\n")
    print("*Two caveats, and they pull in opposite directions — stated separately "
          "rather than netted off.*\n")
    print("- **Compression is off**, deliberately, so both tools face identical "
          "transport. It was expected to narrow the ratio, since Newick "
          "compresses well. Measured, it **widens** it — see Table 20.\n")
    catalogue = next(a["bytes"] for a in tpd["api"] if a["url"].endswith("/datasets"))
    print(f"- **In favour of it:** PhyloDelta's data figure includes a {catalogue / KIB:.1f} KiB "
          "`GET /api/v1/datasets` catalogue whose size tracks **how many comparisons "
          "the store holds**, not tree size. The benchmark store holds every ladder "
          "rung, so a single-comparison deployment transfers less than is shown.\n")

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
    def slices_only(entry):
        return sum(a["bytes"] for a in entry["phylodelta"]["api"] if "/slice" in a["url"])

    print("| leaves | phylo.io data | PhyloDelta data | of which the two slices | "
          "ratio, gzip | ratio, raw | data, app path | of which the two slices | under 10 KiB |")
    print("|---:|---:|---:|---:|---:|---:|---:|---:|:---:|")
    for row in gz_rows:
        pi, pd = row["phyloio"], row["phylodelta"]
        was = raw_by_leaves[row["leaves"]]
        app = transfer_app_gzip[row["leaves"]]
        under = "yes" if max(pd["data"], app["phylodelta"]["data"]) < 10 * KIB else "**no**"
        print(f"| {row['leaves']:,} | {pi['data'] / MIB:,.2f} MiB "
              f"| **{pd['data'] / KIB:,.1f} KiB** | {slices_only(row) / KIB:,.1f} KiB "
              f"| **{pi['data'] / pd['data']:,.0f}x** "
              f"| {was['phyloio']['data'] / was['phylodelta']['data']:,.0f}x "
              f"| {app['phylodelta']['data'] / KIB:,.1f} KiB "
              f"| {slices_only(app) / KIB:,.1f} KiB | {under} |")

    worst = max(r["phylodelta"]["data"] for r in gz_rows)
    worst_app = max(r["phylodelta"]["data"] for r in transfer_app_gzip.values())
    slice_worst = max(slices_only(r) for r in list(gz_rows) + list(transfer_app_gzip.values()))
    once = worst - slices_only(max(gz_rows, key=lambda r: r["phylodelta"]["data"]))
    print(f"\n**The data column is not under 10 KiB at every rung.** Opening a comparison "
          f"transfers up to {worst / KIB:.1f} KiB compressed on the `rf` store and "
          f"{worst_app / KIB:.1f} KiB on the app's path. Of the largest, the two slices — the "
          f"view itself — are {slices_only(max(gz_rows, key=lambda r: r['phylodelta']['data'])) / KIB:.1f} KiB, "
          f"and {once / KIB:.1f} KiB is requests made once when a comparison opens: the metric "
          f"catalogue, the dataset catalogue, `/me`, status and the comparison header. Across "
          f"both paths the two slices never exceed {slice_worst / KIB:.1f} KiB.\n")
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
          f"{gz_app_pi / MIB:,.2f} MiB against {gz_app_pd / MIB:,.2f} MiB, still "
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
                f"{c['bytes'] / KIB:,.1f} KiB / {c['displayed_leaves']} tips"
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
              f"tips and the payload from {lo_cell['bytes'] / KIB:,.1f} KiB to "
              f"{hi_cell['bytes'] / KIB:,.1f} KiB. Above the floor the ratio of "
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
                  f"{a['bytes'] / KIB:,.1f} KiB and {b['bytes'] / KIB:,.1f} KiB. "
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


# --- 10. the distance against implementations that share nothing -----------
rf_external = load("rf_external.json", {})
if rf_external.get("rows"):
    table(22, "The RF distance across four implementations")
    print(f"*Produced by `harness/rf_external.py` against DendroPy "
          f"{rf_external['dendropy']} and ETE3 {rf_external['ete3']}, with "
          "TreeDiff's `rf_postorder` beside them. Every tool is given the same "
          "two trees: rooted, and reconciled to their shared leaf set.*\n")
    print("| leaves | PhyloDelta `rf` | normalised | DendroPy | ETE3 | `rf-treediff` (half) | equal |")
    print("|---:|---:|---:|---:|---:|---:|:---:|")
    agreed = 0
    for row in rf_external["rows"]:
        td = row.get("treediff")
        ok = (row["phylodelta"] == row["dendropy_rooted"] == row["ete3_rooted"]
              and (td is None or 2 * td == row["phylodelta"]))
        agreed += ok
        norm = row.get("phylodelta_normalised")
        print(f"| {row['leaves']:,} | **{row['phylodelta']:,}** | "
              f"{'—' if norm is None else f'{norm:.3f}'} | "
              f"{row['dendropy_rooted']:,} | {row['ete3_rooted']:,} | "
              f"{'—' if td is None else format(td, ',')} | "
              f"{'yes' if ok else '**NO**'} |")
    print(f"\n**Exact agreement at every rung.** {agreed} of "
          f"{len(rf_external['rows'])} rungs have PhyloDelta equal to both "
          "DendroPy and ETE3, and equal to twice `rf-treediff`. The clade sets "
          "were never in question — Table 18 had already checked those — but the "
          "*scale* was, and this is what fixed it.\n")
    print("**This table is why the metric changed.** It used to show PhyloDelta "
          "at exactly half of DendroPy and ETE3 at every rung: the store "
          "reported half the symmetric difference, following TreeDiff, while "
          "every document here and the thesis itself defined RF as the whole of "
          "it. Table 18 could not have caught that, because TreeDiff is the "
          "reference implementation of the same paper and shares the "
          "convention — two implementations of one definition agreeing tells you "
          "the code is faithful, not that the definition is the field's. The "
          "`rf` metric is now at version 2 and reports the full difference; "
          "stored comparisons from version 1 are refused by name rather than "
          "re-labelled.\n")
    print("**The normalisation was the half that was actually wrong.** Version 1 "
          "divided the *halved* RF by the maximum of the *full* RF, so the ratio "
          "could not exceed 0.5 whatever the trees — and the test that should "
          "have caught it asserted `> 0.49` for two near-unrelated trees, reading "
          "the ceiling as \"near-maximal\". The vibrio pair reported 0.193 and "
          "now reports 0.387; two unrelated trees now reach 0.9999 instead of "
          "sitting just under the ceiling.\n")
    unrooted = [r for r in rf_external["rows"] if "dendropy_unrooted" in r]
    if unrooted:
        first = unrooted[0]
        print(f"**Two settings decide whether the comparison is like-for-like**, "
              f"and both produce a plausible near-miss rather than an error when "
              f"wrong. *Rooting*: this store counts rooted clades, and DendroPy's "
              f"unrooted mode gives {first['dendropy_unrooted']:,} rather than "
              f"{first['dendropy_rooted']:,} at {first['leaves']:,} leaves, while "
              f"ETE3 unroots by default. *Reconciliation*: handing the 17,645 pair "
              f"over as it sits on disk adds four bipartitions, because ST 211 is in "
              f"only one of the two trees (\u00a72.6).\n")


# --- 11. does the current release paint where the ladder says it failed? -----
paint = load("phyloio_paint_2.2.5.json", {})
if paint.get("rows"):
    table(23, "phylo.io 2.2.5: paint and compare, measured separately")
    print(f"*`harness/phyloio_paint.mjs` against {paint['label']}, {paint['browser']}, "
          f"bench commit `{paint['bench_commit']}`. {paint['rows'][0]['loads']} page loads per "
          f"rung, {paint['attempt_budget_ms'] / 1000:.0f} s per load, "
          f"{paint['compare_budget_ms'] / 1000:.0f} s for the comparison.*\n")
    print("Tables 1, 2 and 3 take these rows from here, because one load cannot "
          "say whether a paint or a comparison is reliable and three can.\n")
    print("| leaves | loads | painted | paint (median) | SVG paths | compare finished in 600 s |")
    print("|---:|---:|---:|---:|---:|:---:|")
    for row in paint["rows"] + paint_extra.get("rows", []):
        ms = row["paint_ms_median"]
        print(f"| {row['leaves']:,} | {row['loads']} | "
              f"**{row['painted']} of {row['loads']}** | "
              f"{'—' if ms is None else f'{ms / 1000:.1f} s'} | "
              f"{row['paths_median'] or '—'} | "
              f"{'yes' if row['compare_completed'] else '**no**'} |")
    every = paint["rows"] + paint_extra.get("rows", [])
    all_paint = sum(r["painted"] for r in every)
    all_loads = sum(r["loads"] for r in every)
    finished = sum(r["compare_completed"] for r in every)
    print(f"\n**It paints, reliably; its comparison is the slow half.** {all_paint} of "
          f"{all_loads} loads painted and {finished} of {all_loads} finished the comparison in "
          f"{paint['compare_budget_ms'] / 1000:.0f} s. Table 4 gives the comparison longer. "
          "A slice here arrives with its similarity values already in it.\n")
    if paint_extra:
        print(paint_extra["summary"] + "\n")

/**
 * Does phylo.io finish at all, and at what cost?
 *
 * The ladder reported "did not complete in 240 s", which is a budget and not a
 * crash — and "we stopped it" is the one line an examiner presses on. This
 * gives it **30 minutes** per rung and records peak renderer memory, turning a
 * refusal to wait into a number.
 *
 * The renderer is capped at 16 GB of a 24 GB machine rather than left
 * unbounded: an unbounded run would page the whole laptop and measure swap
 * rather than the tool. If the cap is reached that is itself the answer, and
 * it is recorded as such.
 */
import { readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { execSync } from "node:child_process";
import { chromium } from "playwright";
import { start } from "./serve.mjs";

const BENCH = join(fileURLToPath(new URL(".", import.meta.url)), "..");
const PORT = 8097;
//: Given to the comparison itself. The page's `load()` waits 600 s unless told
//: otherwise, and this used not to tell it, so a run described as 30 minutes
//: stopped at 10 and reported that as completing (§34.21).
const BUDGET_MS = Number(process.env.BENCH_BUDGET_S ?? 30 * 60) * 1000;
//: Above paint plus the comparison, so that the budget is what ends a run.
const OUTER_MS = BUDGET_MS + 5 * 60 * 1000;
const RUNGS = (process.env.BENCH_RUNGS ?? "141160 282320").split(" ").map(Number);
//: Its own file per run: the campaign's `endurance_extra` step writes the sizes
//: the default leaves out, beside this one rather than over it (§34.22).
const OUT = process.env.BENCH_OUT ?? "endurance.json";

/**
 * The largest renderer of the Chrome this run launched, in MiB.
 *
 * Found through the process tree, from the browser Playwright drives (the only
 * one started with `--remote-debugging-pipe`). This used to take the largest
 * `--type=renderer` on the machine, so any other Chrome open during the run
 * would have been reported as phylo.io's memory.
 */
function peakRendererMb() {
  try {
    const procs = execSync("ps -Ao pid=,ppid=,rss=,command=", { encoding: "utf8" })
      .split("\n")
      .map((line) => line.trim().match(/^(\d+)\s+(\d+)\s+(\d+)\s+(.*)$/))
      .filter(Boolean)
      .map(([, pid, ppid, rss, command]) => ({ pid, ppid, rss: Number(rss), command }));
    const ours = new Set(
      procs.filter((p) => p.command.includes("--remote-debugging-pipe")).map((p) => p.pid),
    );
    for (let grew = true; grew; ) {
      grew = false;
      for (const p of procs) {
        if (ours.has(p.ppid) && !ours.has(p.pid)) {
          ours.add(p.pid);
          grew = true;
        }
      }
    }
    const renderers = procs.filter((p) => ours.has(p.pid) && p.command.includes("--type=renderer"));
    return Math.round(Math.max(0, ...renderers.map((p) => p.rss)) / 1024);
  } catch {
    return 0;
  }
}

const server = await start(PORT);
const results = [];

//: Page loads per rung per tool (§34.24). A phylo.io load can run for the whole
//: budget, so this step is long: up to five times 35 minutes a rung. It is a
//: step of its own in the campaign and resumes from there.
const LOADS = Number(process.env.BENCH_LOADS || 5);

//: PhyloDelta is held open this long after both panels report a slice, sampled
//: as often as phylo.io's renderer is, so its peak is read over the same kind
//: of window rather than at one instant.
const PHYLODELTA_HOLD_MS = 10_000;

const built = (() => {
  try {
    return JSON.parse(readFileSync(join(BENCH, "results", "server_build.json"), "utf8"));
  } catch {
    return [];
  }
})();

function launchChrome() {
  return chromium.launch({
    channel: "chrome",
    args: ["--js-flags=--max-old-space-size=16384", "--disable-dev-shm-usage"],
  });
}

async function runPhyloio(leaves) {
  const browser = await launchChrome();
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
  let peak = 0;
  const watch = setInterval(() => (peak = Math.max(peak, peakRendererMb())), 2000);
  const t0 = Date.now();
  let outcome;

  try {
    await page.goto(`http://localhost:${PORT}/harness/phyloio.html`, { timeout: 120_000 });
    await page.waitForFunction(() => window.__benchReady === true, undefined, { timeout: 120_000 });
    const phases = await Promise.race([
      page.evaluate(
        ([a, b, budget]) => window.__bench.load(a, b, budget),
        [`/trees/ladder/ladder-${String(leaves).padStart(6, "0")}-a.nwk`,
         `/trees/ladder/ladder-${String(leaves).padStart(6, "0")}-b.nwk`,
         BUDGET_MS],
      ),
      new Promise((_, reject) =>
        setTimeout(() => reject(new Error(`${OUTER_MS / 60000} min limit`)), OUTER_MS),
      ),
    ]);
    const drawn = await page.evaluate(() => ({
      paths: document.querySelectorAll("path").length,
      texts: document.querySelectorAll("text").length,
    }));
    // `ok` is the comparison finishing. `load()` returning says only that the
    // wait ended.
    outcome = { ok: phases.compareComplete, ms: Date.now() - t0, phases, drawn };
    if (!outcome.ok) outcome.why = `comparison unfinished after ${BUDGET_MS / 60000} min`;
  } catch (failed) {
    outcome = { ok: false, ms: Date.now() - t0, why: String(failed.message || failed).split("\n")[0] };
  } finally {
    clearInterval(watch);
  }
  outcome.compare_budget_ms = BUDGET_MS;
  outcome.peak_renderer_mb = Math.max(peak, peakRendererMb());
  await browser.close().catch(() => {});
  return outcome;
}

/** PhyloDelta's renderer over a load and a short hold, by the same sampler. */
async function runPhylodelta(leaves) {
  const rung = built.find((r) => r.leaves === leaves && r.status === "ready");
  if (!rung) return { ok: false, ms: 0, why: "not built", peak_renderer_mb: 0 };
  const browser = await launchChrome();
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
  let peak = 0;
  const watch = setInterval(() => (peak = Math.max(peak, peakRendererMb())), 200);
  const t0 = Date.now();
  let outcome;
  try {
    await page.goto(`http://localhost:${PORT}/#/c/${rung.id}`, { timeout: 120_000 });
    await page.waitForFunction(
      () =>
        [...document.querySelectorAll(".side-counts")].filter((n) =>
          /showing/.test(n.textContent || ""),
        ).length === 2,
      undefined,
      { timeout: 120_000 },
    );
    const ms = Date.now() - t0;
    await new Promise((resume) => setTimeout(resume, PHYLODELTA_HOLD_MS));
    outcome = { ok: true, ms };
  } catch (failed) {
    outcome = { ok: false, ms: Date.now() - t0, why: String(failed.message || failed).split("\n")[0] };
  } finally {
    clearInterval(watch);
  }
  outcome.peak_renderer_mb = Math.max(peak, peakRendererMb());
  await browser.close().catch(() => {});
  return outcome;
}

function save() {
  writeFileSync(join(BENCH, "results", OUT), JSON.stringify(results, null, 2));
}

for (const leaves of RUNGS) {
  for (let load = 0; load < LOADS; load += 1) {
    for (const [tool, run] of [["phylodelta", runPhylodelta], ["phyloio", runPhyloio]]) {
      const outcome = await run(leaves);
      outcome.leaves = leaves;
      outcome.tool = tool;
      outcome.load = load;
      results.push(outcome);
      save();
      writeFileSync(
        1,
        `${leaves.toLocaleString().padStart(9)} ${tool.padEnd(10)} load ${load + 1}/${LOADS}  ${
          outcome.ok ? `ok in ${(outcome.ms / 1000).toFixed(0)}s` : `gave up: ${outcome.why}`
        }  peak renderer ${outcome.peak_renderer_mb.toLocaleString()} MB\n`,
      );
    }
  }
}
server.close();
// The limit's timer outlives a run that ends early, and would hold the process
// open for up to 35 minutes more.
process.exit(0);

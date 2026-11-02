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
import { writeFileSync } from "node:fs";
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

for (const leaves of RUNGS) {
  const browser = await chromium.launch({
    channel: "chrome",
    args: ["--js-flags=--max-old-space-size=16384", "--disable-dev-shm-usage"],
  });
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

  outcome.leaves = leaves;
  outcome.compare_budget_ms = BUDGET_MS;
  outcome.peak_renderer_mb = peak;
  results.push(outcome);
  writeFileSync(join(BENCH, "results", "endurance.json"), JSON.stringify(results, null, 2));
  writeFileSync(
    1,
    `${leaves.toLocaleString().padStart(9)}  ${
      outcome.ok ? `COMPLETED in ${(outcome.ms / 1000).toFixed(0)}s` : `gave up: ${outcome.why}`
    }  peak renderer ${peak.toLocaleString()} MB\n`,
  );
  await browser.close().catch(() => {});
}
server.close();
// The limit's timer outlives a run that ends early, and would hold the process
// open for up to 35 minutes more.
process.exit(0);

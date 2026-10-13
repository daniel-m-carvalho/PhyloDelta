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
const BUDGET_MS = 30 * 60 * 1000;
const RUNGS = [141160, 282320];

function peakRendererMb() {
  try {
    const out = execSync(
      "ps -Ao rss=,command= | grep '[C]hrome.*--type=renderer' | awk '{print $1}' | sort -rn | head -1",
      { encoding: "utf8" },
    ).trim();
    return out ? Math.round(Number(out) / 1024) : 0;
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
        ([a, b]) => window.__bench.load(a, b),
        [`/trees/ladder/ladder-${String(leaves).padStart(6, "0")}-a.nwk`,
         `/trees/ladder/ladder-${String(leaves).padStart(6, "0")}-b.nwk`],
      ),
      new Promise((_, reject) => setTimeout(() => reject(new Error("30 min budget")), BUDGET_MS)),
    ]);
    const drawn = await page.evaluate(() => ({
      paths: document.querySelectorAll("path").length,
      texts: document.querySelectorAll("text").length,
    }));
    outcome = { ok: true, ms: Date.now() - t0, phases, drawn };
  } catch (failed) {
    outcome = { ok: false, ms: Date.now() - t0, why: String(failed.message || failed).split("\n")[0] };
  } finally {
    clearInterval(watch);
  }

  outcome.leaves = leaves;
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

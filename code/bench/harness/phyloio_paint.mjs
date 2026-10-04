/**
 * phylo.io 2.2.5: does it paint at 17,645 and 35,290 leaves, and how often?
 *
 * **Why this runner exists.** The ladder (`ceiling.json`) was re-measured on
 * 2.2.5 and records `phylo.io exceeded 660s` from 17,645 up, with no paint
 * figure — the outer deadline covers load *and* comparison, so a run that
 * paints and then fails to compare is recorded only as a failure. The earlier
 * 2.1.1 ladder had caught the paint separately (9.3 s at 17,645, 25.1 s at
 * 35,290), and those two numbers were still being quoted beside 2.2.5 rows
 * everywhere else: one table reporting two versions, with the paint rows from
 * the older one.
 *
 * So this measures the paint alone, on 2.2.5, as its own question. It is
 * deliberately *not* a change to `ceiling.mjs`: that runner's budgets are what
 * every published row was measured under, and loosening them to recover one
 * cell would re-scale the rest.
 *
 * **Protocol, matching `ceiling.mjs` so the numbers are comparable:** same
 * `phyloio.html` harness, same `launch()` flags, same 1440x900 viewport, the
 * same two nested animation frames before reading, and the same element census.
 * `load()` already reports both halves — `total` is the time to paint and
 * `compareComplete` says whether the worker landed — so the only change needed
 * is an **outer deadline longer than the inner budget**. `ceiling.mjs` wraps the
 * whole attempt in 660 s against an inner 600 s, which leaves 60 s for a paint
 * that takes 25 s and a worker that will use all 600; whichever part overruns,
 * the result is one word. Here the outer wait is 700 s, so paint and compare are
 * recorded separately whatever happens to either.
 *
 *     PHYLOIO_HOME=../vendor/phyloio-2.2.5 node harness/phyloio_paint.mjs
 */
import { writeFileSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { execSync } from "node:child_process";
import { launch, versionOf } from "./browser.mjs";
import { start } from "./serve.mjs";
import { attach, heapBytes } from "./metrics_cdp.mjs";

const BENCH = join(fileURLToPath(new URL(".", import.meta.url)), "..");
const PORT = 8099;
const VIEWPORT = { width: 1440, height: 900 };

//: The two rungs whose paint figures the thesis still quotes from 2.1.1.
const RUNGS = [17645, 35290];

//: Three loads per rung. The jump probe found phylo.io failures to be
//: all-or-nothing *per page load* rather than per operation (§34.14), so a
//: single load cannot distinguish "cannot do this size" from "did not this
//: time" — which is the whole question here.
const LOADS = 3;

//: Page load and harness readiness only — not the measurement.
const PAINT_MS = 300_000;
//: The ladder's comparison budget, unchanged, so a "did it compare" answer here
//: means the same thing it means in Table 1.
const COMPARE_MS = 600_000;
//: Outer deadline, comfortably above COMPARE_MS so that the inner budget is the
//: thing that expires. This is the fix: 660 s against 600 s was too tight to
//: leave room for the paint it was also meant to be timing.
const ATTEMPT_MS = 700_000;

const nwk = (leaves, side) =>
  `/trees/ladder/ladder-${String(leaves).padStart(6, "0")}-${side}.nwk`;

const commit = (() => {
  try {
    const sha = execSync("git rev-parse --short HEAD", { cwd: BENCH }).toString().trim();
    const dirty = execSync("git status --porcelain", { cwd: BENCH }).toString().trim();
    return dirty ? `${sha} + uncommitted changes` : sha;
  } catch {
    return "unknown";
  }
})();

async function oneLoad(leaves) {
  const browser = await launch();
  const page = await browser.newPage({ viewport: VIEWPORT });
  const client = await attach(page);
  try {
    const before = await heapBytes(client);
    await page.goto(`http://localhost:${PORT}/harness/phyloio.html`, { timeout: PAINT_MS });
    await page.waitForFunction(() => window.__benchReady === true, undefined, {
      timeout: PAINT_MS,
    });

    // --- one call: it reports the paint and the comparison separately
    let phases = null;
    try {
      phases = await Promise.race([
        page.evaluate(
          ([a, b, budget]) => window.__bench.load(a, b, budget),
          [nwk(leaves, "a"), nwk(leaves, "b"), COMPARE_MS],
        ),
        new Promise((_, reject) =>
          setTimeout(() => reject(new Error(`attempt exceeded ${ATTEMPT_MS / 1000}s`)), ATTEMPT_MS),
        ),
      ]);
    } catch (failed) {
      return { outcome: describe(failed), paint_ms: null, drawn: null, compared: null };
    }

    await page.evaluate(
      () => new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r))),
    );
    const drawn = await page.evaluate(() => ({
      svg: document.querySelectorAll("svg").length,
      paths: document.querySelectorAll("path").length,
      texts: document.querySelectorAll("text").length,
      nodes: document.querySelectorAll("*").length,
    }));
    const after = await heapBytes(client);

    return {
      outcome: drawn.paths > 0 || drawn.texts > 0 ? "painted" : "drew nothing",
      paint_ms: phases === null ? null : Math.round(phases.total),
      phases,
      drawn,
      heap_mb: before === null || after === null ? null : +((after - before) / 1e6).toFixed(1),
      compared: phases === null ? null : phases.compareComplete,
    };
  } catch (failed) {
    return { outcome: describe(failed), paint_ms: null, drawn: null, compared: null };
  } finally {
    await browser.close().catch(() => {});
  }
}

/** Keep the harness's own failure mode, not a flattened "failed". */
function describe(failed) {
  const text = String(failed?.message ?? failed);
  if (/Target crashed/i.test(text)) return "renderer crashed";
  if (/[Tt]imeout/.test(text)) return `timeout >${PAINT_MS / 1000}s`;
  return text.split("\n")[0].slice(0, 140);
}

const median = (xs) =>
  xs.length ? [...xs].sort((a, b) => a - b)[Math.floor(xs.length / 2)] : null;

const server = await start(PORT);
const probe = await launch();
const browser = versionOf(probe);
await probe.close();

console.log(`\n${browser} · viewport ${VIEWPORT.width}x${VIEWPORT.height}`);
console.log(`phylo.io from ${process.env.PHYLOIO_HOME ?? "(default)"}`);
console.log(`bench commit ${commit}\n`);

const rows = [];
for (const leaves of RUNGS) {
  const loads = [];
  for (let i = 0; i < LOADS; i++) {
    const result = await oneLoad(leaves);
    loads.push(result);
    console.log(
      `${leaves.toLocaleString().padStart(7)} load ${i + 1}/${LOADS}: ` +
        `${result.outcome}` +
        `${result.paint_ms === null ? "" : ` · paint ${(result.paint_ms / 1000).toFixed(1)}s`}` +
        `${result.drawn ? ` · ${result.drawn.paths} paths, ${result.drawn.nodes} DOM nodes` : ""}` +
        ` · compare ${
          result.compared === null
            ? "not reached"
            : result.compared
              ? `completed in ${(result.phases.toCompare / 1000).toFixed(0)}s`
              : `unfinished in ${COMPARE_MS / 1000}s`
        }`,
    );
  }
  const ok = loads.filter((l) => l.outcome === "painted");
  rows.push({
    leaves,
    loads: LOADS,
    painted: ok.length,
    paint_ms_median: median(ok.map((l) => l.paint_ms)),
    paths_median: median(ok.map((l) => l.drawn.paths)),
    dom_nodes_median: median(ok.map((l) => l.drawn.nodes)),
    compare_completed: loads.filter((l) => l.compared === true).length,
    per_load: loads,
  });
}

writeFileSync(
  join(BENCH, "results", "phyloio_paint_2.2.5.json"),
  JSON.stringify(
    {
      label: "2.2.5",
      browser,
      viewport: VIEWPORT,
      phyloio_home: process.env.PHYLOIO_HOME ?? null,
      bench_commit: commit,
      attempt_budget_ms: ATTEMPT_MS,
      compare_budget_ms: COMPARE_MS,
      rows,
    },
    null,
    1,
  ) + "\n",
);
console.log("\nwritten to results/phyloio_paint_2.2.5.json");
await server.close?.();
process.exit(0);

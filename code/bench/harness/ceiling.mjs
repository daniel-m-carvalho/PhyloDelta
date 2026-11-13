/**
 * The headline measurement: how far each tool gets up a tree-size ladder.
 *
 * Both tools are given the **same pair at each rung**, from the same origin,
 * uncompressed, in the same real Chrome, one rung per fresh page. What is
 * timed is a cold start to an interactive comparison — bundle, data and first
 * paint — because that is the thing a user waits for, and because splitting it
 * finer would compare phase names that mean different things in the two tools.
 *
 * **The trap this is written against.** An earlier comparison reported the old
 * demo as ~34x faster; instrumentation later showed it had drawn 91 and 13
 * graph nodes against phylo.io's 2,002 (see DECISIONS, Corrections). So every
 * row records *what was actually drawn* — SVG elements for phylo.io, WebGL
 * canvases plus the slice's own reported leaf counts for PhyloDelta — and the
 * write-up must state the asymmetry rather than let a reader assume there is
 * none. PhyloDelta drawing less IS the design; it is a finding, not a win to
 * be quietly banked.
 *
 * Memory is read through CDP after a forced GC (`metrics_cdp.mjs`), never
 * `performance.memory`, which reported phylo.io at 22 MB before and after
 * building 2,002 SVG elements.
 */
import { readFileSync, writeFileSync, appendFileSync, mkdirSync, existsSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { launch, versionOf, withDeadline } from "./browser.mjs";
import { start } from "./serve.mjs";
import { attach, heapBytes, domCounters } from "./metrics_cdp.mjs";

const HERE = fileURLToPath(new URL(".", import.meta.url));
const BENCH = join(HERE, "..");
const PORT = 8099;

//: A rung is abandoned after this. Long enough that "slow" is reported as slow
//: rather than as failure — the point of the ladder is to find a real ceiling,
//: not to discover where an impatient timeout was set.
const BUDGET_MS = 180_000;

//: How long phylo.io's comparison worker is given after it has painted.
const COMPARE_MS = 600_000;

//: Hard ceiling on one (tool, rung) attempt, INCLUDING instrumentation. The
//: per-step Playwright timeouts do not cover a CDP call, which is how the
//: first version stalled for 44 minutes inside a forced GC. Above the steps it
//: bounds: at 660 s it was shorter than 70,580 leaves' 75 s paint plus the
//: comparison, so that rung reported the limit and not the tool (§34.21).
const ATTEMPT_MS = BUDGET_MS + COMPARE_MS + 60_000;

//: Page loads per rung per tool (§34.24). Each is a fresh browser. Where
//: phylo.io's comparison does not finish in its budget, five loads are five
//: outcomes, reported as such ("did not finish in 5 of 5"), not reduced.
const LOADS = Number(process.env.BENCH_LOADS || 5);

/** Unbuffered: a run this long is useless if its progress is invisible. */
function say(line) {
  writeFileSync(1, line + "\n");
}

const VIEWPORT = { width: 1440, height: 900 };

async function measure(page, client, run) {
  const before = await heapBytes(client);
  const started = Date.now();
  const detail = await run();
  const elapsed = Date.now() - started;
  // Two frames, so the reading is taken after the browser has actually
  // painted rather than after the last script statement.
  await page.evaluate(
    () => new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r))),
  );
  const after = await heapBytes(client);
  return {
    ms: elapsed,
    // null, not NaN, when a reading timed out: the cell should say "not
    // measured" rather than quietly become a number-shaped nothing.
    heap_bytes: before === null || after === null ? null : after - before,
    dom: await domCounters(client).catch(() => null),
    ...detail,
  };
}

/** phylo.io: load both Newick files and let it build its SVG. */
async function runPhyloio(launchOwned, rung) {
  const browser = await launchOwned();
  const page = await browser.newPage({ viewport: VIEWPORT });
  const client = await attach(page);
  try {
    await page.goto(`http://localhost:${PORT}/harness/phyloio.html`, { timeout: BUDGET_MS });
    await page.waitForFunction(() => window.__benchReady === true, undefined, { timeout: BUDGET_MS });
    return await measure(page, client, async () => {
      const phases = await page.evaluate(
        ([a, b, budget]) => window.__bench.load(a, b, budget),
        [`/trees/ladder/${rung.a}`, `/trees/ladder/${rung.b}`, COMPARE_MS],
      );
      const drawn = await page.evaluate(() => ({
        svg: document.querySelectorAll("svg").length,
        paths: document.querySelectorAll("path").length,
        texts: document.querySelectorAll("text").length,
      }));
      return { phases, drawn, ok: drawn.paths > 0 || drawn.texts > 0 };
    });
  } finally {
    await browser.close().catch(() => {});
  }
}

/** PhyloDelta: open the comparison and wait for both panels to report a slice. */
async function runPhylodelta(launchOwned, rung) {
  const browser = await launchOwned();
  const page = await browser.newPage({ viewport: VIEWPORT });
  const client = await attach(page);
  try {
    return await measure(page, client, async () => {
      await page.goto(`http://localhost:${PORT}/#/c/${rung.id}`, { timeout: BUDGET_MS });
      // The panels' own claim — "showing N of M leaves" — is the readiness
      // signal, because it is the thing a user reads to know the view is real.
      await page.waitForFunction(
        () =>
          [...document.querySelectorAll(".side-counts")].filter((n) =>
            /showing/.test(n.textContent || ""),
          ).length === 2,
        undefined,
        // Playwright's second argument is the page function's ARG; options are
        // third. Passing {timeout} second silently left the 30s default in
        // force — it changed no outcome here, but only by luck.
        { timeout: BUDGET_MS },
      );
      const drawn = await page.evaluate(() => ({
        canvases: document.querySelectorAll("canvas").length,
        shown: [...document.querySelectorAll(".side-counts")].map((n) =>
          (n.textContent || "").replace(/\s+/g, " ").trim(),
        ),
      }));
      return { drawn, ok: drawn.canvases > 0 };
    });
  } finally {
    await browser.close().catch(() => {});
  }
}

async function attempt(label, fn) {
  try {
    return await withDeadline(fn, ATTEMPT_MS, label);
  } catch (failed) {
    const why = String(failed.message || failed).split("\n")[0];
    return { ok: false, failed: /Timeout|timeout/.test(why) ? `timeout >${BUDGET_MS / 1000}s` : why };
  }
}

const built = JSON.parse(readFileSync(join(BENCH, "results", "server_build.json"), "utf8"));
const server = await start(PORT);
const probe = await launch();
const BROWSER = versionOf(probe);
await probe.close();
const rows = [];

mkdirSync(join(BENCH, "results"), { recursive: true });
const stream = join(BENCH, "results", "ceiling.jsonl");
writeFileSync(stream, "");

say(`\n${BROWSER} · viewport ${VIEWPORT.width}x${VIEWPORT.height} · budget ${BUDGET_MS / 1000}s\n`);
say(`${"leaves".padStart(9)}  ${"phylo.io".padEnd(26)}  PhyloDelta`);

// An optional size argument measures one rung and merges it into the
// existing results, so adding the 564,640 rung does not cost a re-run of the
// nine that are already measured.
const only = process.argv[2] ? Number(process.argv[2]) : null;
const previous = only !== null && existsSync(join(BENCH, "results", "ceiling.json"))
  ? JSON.parse(readFileSync(join(BENCH, "results", "ceiling.json"), "utf8")).rows
  : [];

try {
  for (const rung of built.filter(
    (r) => r.status === "ready" && (only === null || r.leaves === only),
  )) {
    const spec = {
      id: rung.id,
      a: `ladder-${String(rung.leaves).padStart(6, "0")}-a.nwk`,
      b: `ladder-${String(rung.leaves).padStart(6, "0")}-b.nwk`,
    };
    // PhyloDelta's loads first: a phylo.io attempt that overran its deadline
    // could otherwise leave a renderer working while PhyloDelta is measured.
    const phylodeltaLoads = [];
    for (let i = 0; i < LOADS; i += 1) {
      phylodeltaLoads.push(await attempt("phylodelta", (owned) => runPhylodelta(owned, spec)));
    }
    const phyloioLoads = [];
    for (let i = 0; i < LOADS; i += 1) {
      phyloioLoads.push(await attempt("phylo.io", (owned) => runPhyloio(owned, spec)));
    }
    // The first load of each stands where the single attempt used to, so a
    // reader of one row sees one load; `loads` holds all of them.
    const phyloio = { ...phyloioLoads[0], loads: phyloioLoads };
    const phylodelta = { ...phylodeltaLoads[0], loads: phylodeltaLoads };

    const row = { leaves: rung.leaves, server_s: +rung.build_s.toFixed(1), phyloio, phylodelta };
    rows.push(row);
    // Appended as it goes: a run this long must survive being interrupted.
    appendFileSync(stream, JSON.stringify(row) + "\n");
    const show = (r) => {
      if (!r.ok) return `FAIL ${r.failed}`.slice(0, 30);
      const paint = r.phases ? (r.phases.postFetch / 1000).toFixed(1) : (r.ms / 1000).toFixed(1);
      const cmp = r.phases
        ? r.phases.compareComplete
          ? ` cmp ${(r.phases.toCompare / 1000).toFixed(0)}s`
          : " cmp INCOMPLETE"
        : "";
      const heap = r.heap_bytes == null ? "n/a" : (r.heap_bytes / 2 ** 20).toFixed(1);
      return `${paint}s ${heap.padStart(5)}MiB${cmp}`;
    };
    for (let i = 0; i < LOADS; i += 1) {
      say(
        `${(i ? "" : rung.leaves.toLocaleString()).padStart(9)}  ${show(phyloioLoads[i]).padEnd(26)}  ${show(phylodeltaLoads[i])}`,
      );
    }
  }
} finally {
  server.close();
}

const merged = [...previous.filter((r) => !rows.some((n) => n.leaves === r.leaves)), ...rows].sort(
  (a, b) => a.leaves - b.leaves,
);
writeFileSync(
  join(BENCH, "results", "ceiling.json"),
  JSON.stringify(
    { browser: BROWSER, viewport: VIEWPORT, budget_ms: BUDGET_MS, attempt_ms: ATTEMPT_MS, loads: LOADS, rows: merged },
    null,
    2,
  ),
);
say(`\nwritten to results/ceiling.json`);
process.exit(0);

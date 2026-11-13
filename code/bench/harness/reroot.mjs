/**
 * Re-rooting: from the action to the re-rooted comparison on screen (§34.24, §56).
 *
 * Both tools have to compute the comparison again after a re-root — every
 * metric here, and phylo.io's similarity, is rooted — so this measures what the
 * design costs at the one moment it has to redo the expensive half.
 *
 * **phylo.io** recomputes in the page: `trigger_("reroot", …)`, which is what its
 * context menu's "Reroot" calls, re-roots the model and calls
 * `compute_topology_and_render_bounded_viewer(true)`, which starts the
 * similarity worker again over both trees. The clock stops when the worker
 * clears `message_loader`, as the first comparison is timed, and two frames
 * later. Measured where its comparison completes; a load whose comparison never
 * completes has nothing to re-root and is reported as such.
 *
 * **PhyloDelta** builds a new comparison on the server (§56): the clock covers the
 * request, the build, the app's own polling, and opening the new comparison
 * until both panels report a slice, which carries its similarity values. It
 * starts from `window.__phylodeltaApp.reroot`, the path the confirm button in
 * the re-root dialog takes, so nothing a user waits for is left out. The new
 * comparison is deleted after each run, through the API, so five runs do not
 * leave five copies of the largest rung in the store.
 *
 * The clade is the same for both tools and every run: `reroot_targets.json`,
 * by stored id for PhyloDelta and by leaf set for phylo.io. Never the root or a
 * child of the root, which a re-root refuses.
 *
 *   node harness/reroot.mjs [leaves]
 */
import { readFileSync, writeFileSync, existsSync, mkdirSync, appendFileSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { launch, versionOf, withDeadline } from "./browser.mjs";
import { start } from "./serve.mjs";

const HERE = fileURLToPath(new URL(".", import.meta.url));
const BENCH = join(HERE, "..");
const PORT = 8096;
const VIEWPORT = { width: 1440, height: 900 };

//: Runs per rung per tool, each in a fresh browser (§34.24).
const RUNS = Number(process.env.BENCH_LOADS || 5);
//: phylo.io's first comparison, and then its re-rooted one, are each given this.
const COMPARE_MS = 600_000;
//: PhyloDelta's re-root, build included. The largest rung builds in ~8 minutes
//: at two threads (Table 8).
const PHYLODELTA_MS = 1_800_000;
const ATTEMPT_MS = 2 * COMPARE_MS + 300_000;
//: Where phylo.io's comparison can complete at all (Table 1); above it there
//: is no comparison to re-root.
const PHYLOIO_RUNGS = [1000, 2500, 5000, 10000, 17645];

function say(line) {
  writeFileSync(1, line + "\n");
}

const nwk = (leaves, side) => `/trees/ladder/ladder-${String(leaves).padStart(6, "0")}-${side}.nwk`;

async function phyloioRun(launchOwned, target) {
  const browser = await launchOwned();
  const page = await browser.newPage({ viewport: VIEWPORT });
  try {
    await page.goto(`http://localhost:${PORT}/harness/navigation.html`, { timeout: 300_000 });
    await page.waitForFunction(() => window.__navReady === true, undefined, { timeout: 300_000 });
    const loaded = await page.evaluate(
      ([a, b, budget]) => window.__nav.load(a, b, budget),
      [nwk(target.leaves, "a"), nwk(target.leaves, "b"), COMPARE_MS],
    );
    if (!loaded.ready) return { ok: false, outcome: "no comparison", why: "the first comparison never completed" };
    const got = await page.evaluate(
      ([labels, budget]) => window.__nav.reroot(labels, budget),
      [target.labels, COMPARE_MS],
    );
    if (got.error) return { ok: false, outcome: "threw", why: got.error };
    if (!got.finished) return { ok: false, outcome: "did not finish", ms: got.ms };
    return { ok: true, outcome: "re-rooted", ms: got.ms, recomputed: got.recomputed };
  } finally {
    await browser.close().catch(() => {});
  }
}

async function phylodeltaRun(launchOwned, target) {
  const browser = await launchOwned();
  const page = await browser.newPage({ viewport: VIEWPORT });
  // Both panels report a slice: the app's own claim that the view is real.
  const showing = () =>
    [...document.querySelectorAll(".side-counts")].filter((n) => /showing/.test(n.textContent || ""))
      .length === 2;
  try {
    await page.goto(`http://localhost:${PORT}/#/c/${target.pair}`, { timeout: 300_000 });
    await page.waitForFunction(showing, undefined, { timeout: 300_000 });
    await page.waitForFunction(() => Boolean(window.__phylodeltaApp), undefined, { timeout: 60_000 });
    const result = await page.evaluate(
      async ([pair, node, budget]) => {
        const ready = () =>
          [...document.querySelectorAll(".side-counts")].filter((n) => /showing/.test(n.textContent || ""))
            .length === 2;
        const t0 = performance.now();
        // Not awaited: it resolves when the app has opened the new comparison,
        // and the clock stops when that comparison is drawn, not before.
        const started = window.__phylodeltaApp.reroot(0, node, false);
        const opened = () => {
          const match = /^#\/c\/([^?]+)/.exec(window.location.hash);
          return match && decodeURIComponent(match[1]) !== pair ? decodeURIComponent(match[1]) : null;
        };
        // The new comparison's own panels, not the old ones still on screen
        // for a moment after the address changes: both sides of the new pair,
        // each with a slice in and nothing loading.
        const drawnFor = (id) => {
          const sides = window.__phylodelta?.state();
          const [left, right] = id.split("__");
          return Boolean(
            sides && sides[0].treeId === left && sides[1].treeId === right &&
              sides[0].slice && sides[1].slice && !sides[0].loading && !sides[1].loading,
          );
        };
        while (performance.now() - t0 < budget) {
          const id = opened();
          if (id && drawnFor(id) && ready()) {
            await new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)));
            return { ms: performance.now() - t0, id };
          }
          const failed = document.querySelector(".chip.rebuild.warn");
          if (failed) return { error: failed.getAttribute("title") || failed.textContent };
          await new Promise((r) => setTimeout(r, 50));
        }
        await started.catch(() => {});
        return { error: `not open within ${budget / 1000} s` };
      },
      [target.pair, target.node, PHYLODELTA_MS],
    );
    if (result.error) return { ok: false, outcome: "failed", why: result.error };
    // Removed, so five runs do not leave five copies of the rung in the store.
    await page.evaluate(
      (id) => fetch(`/api/v1/comparisons/${encodeURIComponent(id)}`, { method: "DELETE" }).then((r) => r.status),
      result.id,
    );
    return { ok: true, outcome: "re-rooted", ms: result.ms, new_id: result.id };
  } finally {
    await browser.close().catch(() => {});
  }
}

async function attempt(label, fn) {
  try {
    return await withDeadline(fn, ATTEMPT_MS, label);
  } catch (failed) {
    return { ok: false, outcome: "failed", why: String(failed.message || failed).split("\n")[0] };
  }
}

const targets = JSON.parse(readFileSync(join(BENCH, "results", "reroot_targets.json"), "utf8"));
const only = process.argv[2] ? Number(process.argv[2]) : null;
const server = await start(PORT);
const probe = await launch();
const BROWSER = versionOf(probe);
await probe.close();

mkdirSync(join(BENCH, "results"), { recursive: true });
const out = join(BENCH, "results", "reroot.json");
const stream = join(BENCH, "results", "reroot.jsonl");
if (!existsSync(stream)) writeFileSync(stream, "");
const previous = only !== null && existsSync(out) ? JSON.parse(readFileSync(out, "utf8")).rows : [];
const rows = [];

say(`\n${BROWSER} · ${RUNS} runs per rung per tool · ms from the re-root to the comparison drawn\n`);
try {
  for (const target of targets.filter((t) => only === null || t.leaves === only)) {
    const phyloio = [];
    const phylodelta = [];
    for (let run = 0; run < RUNS; run += 1) {
      phylodelta.push(await attempt("phylodelta", (owned) => phylodeltaRun(owned, target)));
      if (PHYLOIO_RUNGS.includes(target.leaves)) {
        phyloio.push(await attempt("phylo.io", (owned) => phyloioRun(owned, target)));
      }
      const show = (r) => (!r ? "" : r.ok ? `${(r.ms / 1000).toFixed(2)} s` : r.outcome);
      say(
        `${(run ? "" : target.leaves.toLocaleString()).padStart(9)}  run ${run + 1}/${RUNS}  ` +
          `phylo.io ${show(phyloio[run]).padStart(14)}   PhyloDelta ${show(phylodelta[run])}`,
      );
    }
    const row = {
      leaves: target.leaves,
      pair: target.pair,
      node: target.node,
      clade_leaves: target.clade_leaves,
      depth: target.depth,
      phyloio: PHYLOIO_RUNGS.includes(target.leaves) ? phyloio : null,
      phylodelta,
    };
    rows.push(row);
    appendFileSync(stream, JSON.stringify(row) + "\n");
  }
} finally {
  server.close();
}

const merged = [...previous.filter((r) => !rows.some((n) => n.leaves === r.leaves)), ...rows].sort(
  (a, b) => a.leaves - b.leaves,
);
writeFileSync(
  out,
  JSON.stringify({ browser: BROWSER, viewport: VIEWPORT, runs: RUNS, rows: merged }, null, 2),
);
say(`\nwritten to results/reroot.json`);
process.exit(0);

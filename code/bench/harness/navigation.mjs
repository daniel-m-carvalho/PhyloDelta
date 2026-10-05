/**
 * Navigation responsiveness: what each tool costs *after* it has loaded.
 *
 * The ceiling measurement answers "can it open the comparison at all". This
 * answers the other half, and it is the half where phylo.io has the structural
 * advantage: it holds the whole tree, so moving inside it is local work, while
 * PhyloDelta holds a few hundred nodes and asks the server for the rest. If the
 * design's cost shows up anywhere, it shows up here.
 *
 * **Only at sizes both tools can load.** phylo.io cannot complete a comparison
 * above 17,645 leaves, and an uncompleted comparison has no `elementBCN`, so
 * "find in the other tree" has nothing to find. Measuring PhyloDelta alone on
 * the upper rungs would be a column with no comparison in it.
 *
 * **Both tools are driven one layer below the click.** phylo.io's menu item
 * calls `container.trigger_(action, …)`; PhyloDelta's calls `focus` / `back` /
 * `focusWithContext`. The harness calls exactly those. Synthesising a click on
 * PhyloDelta's WebGL canvas would have added hit-testing to one side and not
 * the other; dispatching phylo.io's d3 handler directly would have done the
 * same in reverse. What is excluded is identical in kind for both: opening a
 * context menu and pressing an item in it.
 *
 * Three operations, chosen because both tools offer all three and a user does
 * all three:
 *
 *   expand  — open a collapsed clade
 *   back    — return to the view before that
 *   jump    — find a node's counterpart in the other tree
 *
 * Every timing ends after two animation frames, so it includes paint rather
 * than stopping at the last script statement.
 */
import { writeFileSync, readFileSync, existsSync, mkdirSync, appendFileSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { launch, versionOf } from "./browser.mjs";
import { start } from "./serve.mjs";

const HERE = fileURLToPath(new URL(".", import.meta.url));
const BENCH = join(HERE, "..");
const PORT = 8097;
const VIEWPORT = { width: 1440, height: 900 };

const LOAD_MS = 300_000;
const COMPARE_MS = 600_000;
//: One (tool, rung) attempt, everything included. Generous enough that a slow
//: tool is reported as slow rather than as failed, but a real bound: the first
//: version derived it from the sample count and arrived at 64 minutes, which is
//: not a deadline.
const ATTEMPT_MS = 900_000;

//: Operations per rung per tool. Navigation cost varies by an order of
//: magnitude with clade size, so a single sample would be a number with no
//: meaning — the earlier "PhyloDelta degrades at scale" finding was exactly
//: this mistake, n=1 reporting 2.7 s for something that takes 30 ms.
const SAMPLES = 8;

//: Navigations run and thrown away before measuring, per tool. The first one of
//: a session pays for the server's first touch of the pair and for Chrome
//: compiling the path; that is a one-off, not steady-state navigation.
const WARMUP = 3;

//: Wall-clock budget for taking samples in ONE cell. When it runs out, the cell
//: reports the samples it got and says it was truncated.
//:
//: The alternative is what happened first: phylo.io at 17,645 leaves blew the
//: 900 s attempt deadline and the cell came back as the single word "timeout".
//: That is not a measurement — it cannot distinguish "each operation takes 30 s"
//: from "the tool hung" — and those are very different claims to make about
//: someone else's tool.
const CELL_MS = 300_000;

/** Rungs both tools can actually complete a comparison at. */
const RUNGS = [1000, 2500, 5000, 10000, 17645];

function say(line) {
  writeFileSync(1, line + "\n");
}

const median = (xs) => {
  const s = [...xs].sort((a, b) => a - b);
  if (!s.length) return null;
  const mid = s.length >> 1;
  return +(s.length % 2 ? s[mid] : (s[mid - 1] + s[mid]) / 2).toFixed(1);
};
const summarise = (xs) =>
  xs.length
    ? {
        n: xs.length,
        median_ms: median(xs),
        min_ms: +Math.min(...xs).toFixed(1),
        max_ms: +Math.max(...xs).toFixed(1),
      }
    : { n: 0, median_ms: null, min_ms: null, max_ms: null };

function nwk(leaves, side) {
  return `/trees/ladder/ladder-${String(leaves).padStart(6, "0")}-${side}.nwk`;
}

/* ------------------------------------------------------------------ phylo.io */

async function runPhyloio(leaves) {
  const browser = await launch();
  const page = await browser.newPage({ viewport: VIEWPORT });
  try {
    await page.goto(`http://localhost:${PORT}/harness/navigation.html`, { timeout: LOAD_MS });
    await page.waitForFunction(() => window.__navReady === true, undefined, { timeout: LOAD_MS });

    const loaded = await page.evaluate(
      ([a, b, budget]) => window.__nav.load(a, b, budget),
      [nwk(leaves, "a"), nwk(leaves, "b"), COMPARE_MS],
    );
    if (!loaded.ready) return { ok: false, failed: "comparison never completed" };

    const candidates = await page.evaluate((n) => window.__nav.candidates(n), SAMPLES * 3);
    const expand = [];
    const back = [];
    const jump = [];
    const failures = [];
    const toggle = (at) => page.evaluate((k) => window.__nav.toggle(k), at);

    // The same discarded warm-up the other tool gets, so neither is credited
    // with a first-navigation cost the other paid. Bounded: at 17,645 leaves a
    // single re-render is slow enough that the warm-up alone can outlast the
    // whole cell, leaving nothing measured.
    const warmUntil = Date.now() + CELL_MS / 3;
    for (const node of candidates.slice(0, WARMUP)) {
      if (Date.now() > warmUntil) break;
      await toggle(node.at);
      await toggle(node.at);
    }

    const until = Date.now() + CELL_MS;
    let truncated = false;
    for (const node of candidates.slice(0, SAMPLES)) {
      if (Date.now() > until) { truncated = true; break; }
      // A node d3 is holding open is collapsed first, so that "expand" is
      // always measured as an expand rather than as whichever the tool
      // happened to start in. That preparatory toggle is not itself timed.
      if (!node.collapsed) {
        const prepared = await toggle(node.at);
        if (prepared.error) { failures.push({ op: "prepare", ...prepared }); continue; }
      }
      const opened = await toggle(node.at);
      if (opened.error) { failures.push({ op: "expand", ...opened }); continue; }
      expand.push(opened.ms);
      // Collapsing it again is this tool's "return to the previous view": there
      // is no view stack to pop, because there was never a fetch.
      const closed = await toggle(node.at);
      if (closed.error) { failures.push({ op: "back", ...closed }); continue; }
      back.push(closed.ms);
    }

    for (const node of candidates.filter((c) => c.hasBcn).slice(0, SAMPLES)) {
      if (Date.now() > until) { truncated = true; break; }
      const got = await page.evaluate((at) => window.__nav.bcn(at), node.at);
      if (got.error) failures.push({ op: "jump", leaves: node.leaves, ...got });
      else jump.push(got.ms);
    }

    const drawn = await page.evaluate(() => window.__nav.drawn());
    return {
      ok: true,
      drawn,
      sizes: candidates.slice(0, SAMPLES).map((c) => c.leaves),
      with_bcn: candidates.filter((c) => c.hasBcn).length,
      truncated,
      // Kept verbatim rather than collapsed to a count: a claim about another
      // tool failing has to carry the message it failed with.
      failures: failures.slice(0, 6),
      failure_count: failures.length,
      expand: summarise(expand),
      back: summarise(back),
      jump: summarise(jump),
    };
  } finally {
    await browser.close().catch(() => {});
  }
}

/* ---------------------------------------------------------------- PhyloDelta */

/**
 * Install the page-side probes, in one place.
 *
 * Separate from the runner because everything in here executes inside the page
 * and nothing outside it does — a boundary worth being able to see. It was
 * originally extracted because two runners each had their own copy of the
 * timing loop and had begun to disagree about what "done" meant; the runners
 * are now one, and this stays the single definition.
 */
async function installProbes(page) {
  await page.evaluate(() => {
    /**
     * Run one navigation and time it to paint, attributing the network part.
     *
     * Two things this had to get right rather than assume:
     *
     * - **What "done" means.** The first version waited for the path to change,
     *   which hangs forever when an action legitimately does not move the view
     *   (a jump whose widened ancestor is already the current root). One sample
     *   sat on a 60 s deadline and went into a median. It now watches the built
     *   tree's object identity, which changes on every applied slice — cache hit
     *   included, since the tree is rebuilt either way — and reports a
     *   non-movement as such instead of as a very slow success.
     * - **Where the time goes.** A slice is ~3 ms of server work, so if a
     *   navigation costs 45 ms the other 42 are build and draw. Guessing that
     *   split would be exactly the kind of unmeasured claim this project keeps
     *   catching, so the API requests inside the step window are summed from the
     *   Resource Timing entries.
     */
    window.__step = async (side, act) => {
      const before = window.__phylodelta.state()[side];
      const wasTree = before.tree;
      const wasError = before.jumpError;
      const seen = performance
        .getEntriesByType("resource")
        .filter((e) => e.name.includes("/api/")).length;

      const t0 = performance.now();
      act(window.__phylodelta.actions()[side], before);

      let moved = false;
      const deadline = performance.now() + 5000;
      while (performance.now() < deadline) {
        const now = window.__phylodelta.state()[side];
        if (now.jumpError && now.jumpError !== wasError) break;
        if (now.tree && now.tree !== wasTree && !now.loading) {
          moved = true;
          break;
        }
        await new Promise((r) => setTimeout(r, 2));
      }
      await new Promise((res) => requestAnimationFrame(() => requestAnimationFrame(res)));
      const ms = performance.now() - t0;

      const after = performance.getEntriesByType("resource").filter((e) => e.name.includes("/api/"));
      const fresh = after.slice(seen);
      return {
        ms,
        moved,
        jump_error: window.__phylodelta.state()[side].jumpError,
        requests: fresh.length,
        fetch_ms: +fresh.reduce((sum, e) => sum + e.duration, 0).toFixed(1),
      };
    };

    /** The biggest wedges on screen: the clades a user actually opens. */
    window.__wedges = (side) => {
      const state = window.__phylodelta.state()[side];
      const nodes = state.slice ? state.slice.nodes : null;
      if (!nodes) return [];
      return nodes.id
        .map((id, k) => ({
          id,
          leaves: nodes.true_leaf_count[k],
          truncated: nodes.truncated[k],
        }))
        .filter((n) => n.truncated && n.leaves > 1)
        .sort((a, b) => b.leaves - a.leaves);
    };

    /** Leaves in the current slice that have a counterpart, for the jump. */
    window.__leaves = (side) => {
      const state = window.__phylodelta.state()[side];
      const nodes = state.slice ? state.slice.nodes : null;
      const values = state.slice && state.slice.comparison;
      if (!nodes) return [];
      return nodes.id
        .map((id, k) => ({
          id,
          leaves: nodes.true_leaf_count[k],
          truncated: nodes.truncated[k],
          corresponds: values ? values.corresponds[k] : null,
        }))
        .filter((n) => !n.truncated && n.leaves === 1 && n.corresponds !== null);
    };
  });
}

/** Wait until both panels of the real application are showing a tree. */
async function openComparison(page, pairId) {
  await page.goto(`http://localhost:${PORT}/#/c/${pairId}`, { timeout: LOAD_MS });
  await page.waitForFunction(
    () =>
      window.__phylodelta !== undefined &&
      window.__phylodelta.state().every((s) => s.tree !== null),
    undefined,
    { timeout: LOAD_MS },
  );
  await installProbes(page);
}


/**
 * Drive the real application through the actions its menu items call.
 *
 * `window.__phylodelta` is the seam `ComparisonView` exposes for exactly this
 * (see the comment there). Each helper resolves once the panel reports a tree
 * again *and* the browser has painted, so a timing covers fetch, build and draw
 * — everything between the user asking and the picture changing.
 */
/**
 * PhyloDelta: cached and uncached navigation, interleaved in one page.
 *
 * **Why interleaved.** The first version measured the two in separate browsers,
 * one after the other, and reported the *uncached* run as three times FASTER
 * than the cached one — 46 ms against 125 ms, with its fetches at 6.5 ms
 * against 38 ms. A cache cannot slow down the operation it serves, so the
 * difference was not the cache: the first run was paying for a cold server
 * (page cache, mmap faults, the reader caches in `registry_pairs`) and the
 * second inherited a warm one. Order was the variable, and it was invisible
 * because each run only ever saw its own number.
 *
 * So: one page, one server state, a discarded warm-up, and then both variants
 * against the SAME target back to back. The cache is then the only thing that
 * differs between the pair, which is the only way its contribution can be
 * attributed to it.
 */
async function runPhylodelta(pairId) {
  const browser = await launch();
  const page = await browser.newPage({ viewport: VIEWPORT });
  try {
    await openComparison(page, pairId);

    const cached = { expand: [], back: [], jump: [] };
    const uncached = { expand: [], back: [] };
    const fetches = { expand: [], back: [], jump: [], cold_expand: [], cold_back: [] };
    const sizes = [];
    const skipped = [];

    const clear = () => page.evaluate(() => window.__phylodeltaSliceCache.clear());
    const focus = (id) => page.evaluate((k) => window.__step(0, (a) => a.focus(k)), id);
    const goBack = () => page.evaluate(() => window.__step(0, (a) => a.back()));
    const biggestWedge = () => page.evaluate(() => window.__wedges(0));

    /*
     * Warm-up, discarded.
     *
     * Not padding: the very first navigation of a session pays for the server's
     * first touch of this pair's columns and for Chrome compiling the code path.
     * Including it would put a one-off cost into a median that claims to
     * describe steady-state navigation.
     */
    for (let k = 0; k < WARMUP; k++) {
      const wedges = await biggestWedge();
      if (!wedges.length) break;
      await focus(wedges[0].id);
      await goBack();
    }
    await clear();

    const until = Date.now() + CELL_MS;
    let truncated = false;
    for (let taken = 0; taken < SAMPLES; taken++) {
      if (Date.now() > until) { truncated = true; break; }
      const wedges = await biggestWedge();
      if (!wedges.length) break;
      // A DIFFERENT wedge each time. Always taking the largest measured the
      // same 309-leaf clade eight times and reported it as eight samples —
      // n=1 wearing an n=8 label, an error this project has already made once.
      const target = wedges[Math.min(taken, wedges.length - 1)];
      sizes.push(target.leaves);

      // --- uncached first, so the cached pass below is the one that benefits
      // --- from anything the uncached pass warmed. The bias therefore runs
      // --- AGAINST the conclusion the cache is meant to support.
      await clear();
      const coldOpen = await focus(target.id);
      if (!coldOpen.moved) { skipped.push({ op: "cold expand", ...coldOpen }); continue; }
      uncached.expand.push(coldOpen.ms);
      fetches.cold_expand.push(coldOpen.fetch_ms);

      await clear();
      const coldBack = await goBack();
      if (!coldBack.moved) { skipped.push({ op: "cold back", ...coldBack }); continue; }
      uncached.back.push(coldBack.ms);
      fetches.cold_back.push(coldBack.fetch_ms);

      // --- cached: the same two moves, with whatever the cache now holds.
      const opened = await focus(target.id);
      if (!opened.moved) { skipped.push({ op: "expand", ...opened }); continue; }
      cached.expand.push(opened.ms);
      fetches.expand.push(opened.fetch_ms);

      const returned = await goBack();
      if (!returned.moved) { skipped.push({ op: "back", ...returned }); continue; }
      cached.back.push(returned.ms);
      fetches.back.push(returned.fetch_ms);
    }

    // The jump goes the other way — a leaf on the left, found on the right —
    // because that is the interaction, and because it costs the right panel an
    // /ancestor call plus a slice it has never held.
    const leaves = await page.evaluate(() => window.__leaves(0));
    for (const leaf of leaves.slice(0, SAMPLES)) {
      const found = await page.evaluate(
        (id) => window.__step(1, (actions) => actions.focusWithContext(id)),
        leaf.corresponds,
      );
      if (!found.moved) { skipped.push({ op: "jump", ...found }); continue; }
      cached.jump.push(found.ms);
      fetches.jump.push(found.fetch_ms);
      // Back to where the right panel was, so each jump starts from the same
      // place rather than from wherever the last one landed.
      //
      // `clearMark` as well as `reset`, and explicitly: a jump leaves a mark,
      // and since the mark now outlives navigation (§33 — it answers "where is
      // this leaf in the whole tree", so widening the view must not drop it)
      // `reset` alone leaves the previous jump's leaf still pinned. Each sample
      // would then start from a root slice carrying the last one's `keep`,
      // which is not the same place. Stating both here rather than relying on
      // `reset` to do it is also what keeps this run independent of that
      // decision being revisited.
      await page.evaluate(() => {
        const actions = window.__phylodelta.actions()[1];
        actions.clearMark();
        actions.reset();
      });
    }

    const drawn = await page.evaluate(() => ({
      canvases: document.querySelectorAll("canvas").length,
      shown: [...document.querySelectorAll(".side-counts")].map((n) =>
        (n.textContent || "").replace(/\s+/g, " ").trim(),
      ),
    }));
    const cache = await page.evaluate(() => window.__phylodeltaSliceCache.stats());

    return {
      ok: true,
      drawn,
      sizes,
      cache,
      // What the network cost inside each operation, so the write-up can say
      // how much of a navigation is the round trip and how much is drawing
      // rather than assume the answer.
      fetch_ms: {
        expand: summarise(fetches.expand),
        back: summarise(fetches.back),
        jump: summarise(fetches.jump),
        cold_expand: summarise(fetches.cold_expand),
        cold_back: summarise(fetches.cold_back),
      },
      skipped: skipped.slice(0, 6),
      skipped_count: skipped.length,
      truncated,
      expand: summarise(cached.expand),
      back: summarise(cached.back),
      jump: summarise(cached.jump),
      uncached: { expand: summarise(uncached.expand), back: summarise(uncached.back) },
    };
  } finally {
    await browser.close().catch(() => {});
  }
}

/* --------------------------------------------------------------------- run */

function withDeadline(promise, ms, label) {
  let timer;
  return Promise.race([
    promise.finally(() => clearTimeout(timer)),
    new Promise((_, reject) => {
      timer = setTimeout(() => reject(new Error(`${label} exceeded ${ms / 1000}s`)), ms);
    }),
  ]);
}

async function attempt(label, fn) {
  try {
    return await withDeadline(fn(), ATTEMPT_MS, label);
  } catch (failed) {
    return { ok: false, failed: String(failed.message || failed).split("\n")[0] };
  }
}

const built = JSON.parse(readFileSync(join(BENCH, "results", "server_build.json"), "utf8"));
const server = await start(PORT);
const probe = await launch();
const BROWSER = versionOf(probe);
await probe.close();

mkdirSync(join(BENCH, "results"), { recursive: true });
const stream = join(BENCH, "results", "navigation.jsonl");
if (!existsSync(stream)) writeFileSync(stream, "");
const only = process.argv[2] ? Number(process.argv[2]) : null;
const out = join(BENCH, "results", "navigation.json");
const previous =
  only !== null && existsSync(out) ? JSON.parse(readFileSync(out, "utf8")).rows : [];

const rows = [];
say(`\n${BROWSER} · viewport ${VIEWPORT.width}x${VIEWPORT.height} · ${SAMPLES} operations per cell`);
say(`median ms to painted result\n`);
say(
  `${"leaves".padStart(8)}  ${"phylo.io".padStart(8)} ${"exp".padStart(6)} ${"back".padStart(6)} ${"jump".padStart(6)}` +
    `   ${"PhyloDelta".padStart(10)} ${"exp".padStart(6)} ${"back".padStart(6)} ${"jump".padStart(6)}` +
    `   ${"no cache".padStart(8)} ${"exp".padStart(6)} ${"back".padStart(6)}`,
);

try {
  for (const leaves of RUNGS.filter((l) => only === null || l === only)) {
    const rung = built.find((r) => r.leaves === leaves && r.status === "ready");
    if (!rung) {
      say(`${leaves.toLocaleString().padStart(8)}  not built — skipped`);
      continue;
    }
    const phyloio = await attempt("phylo.io", () => runPhyloio(leaves));
    const phylodelta = await attempt("phylodelta", () => runPhylodelta(rung.id));

    rows.push({ leaves, pair: rung.id, phyloio, phylodelta });
    // Appended as it goes. The first version wrote only at the end, and the
    // 17,645 rung had Chrome at 9 GB — an OOM there would have discarded four
    // completed rungs to report nothing.
    appendFileSync(stream, JSON.stringify(rows[rows.length - 1]) + "\n");
    const cell = (r, key) =>
      (r && r.ok !== false && r[key] && r[key].median_ms !== null ? `${r[key].median_ms}` : "—").padStart(6);
    const cold = phylodelta.ok ? phylodelta.uncached : null;
    say(
      `${leaves.toLocaleString().padStart(8)}  ${"".padStart(8)} ${cell(phyloio, "expand")} ${cell(phyloio, "back")} ${cell(phyloio, "jump")}` +
        `   ${"".padStart(10)} ${cell(phylodelta, "expand")} ${cell(phylodelta, "back")} ${cell(phylodelta, "jump")}` +
        `   ${"".padStart(8)} ${cell(cold, "expand")} ${cell(cold, "back")}`,
    );
    if (!phyloio.ok) say(`          phylo.io: ${phyloio.failed}`);
    if (!phylodelta.ok) say(`          PhyloDelta: ${phylodelta.failed}`);
  }
} finally {
  server.close();
}

const merged = [...previous.filter((r) => !rows.some((n) => n.leaves === r.leaves)), ...rows].sort(
  (a, b) => a.leaves - b.leaves,
);
writeFileSync(
  out,
  JSON.stringify(
    { browser: BROWSER, viewport: VIEWPORT, samples: SAMPLES, rungs: RUNGS, rows: merged },
    null,
    2,
  ),
);
say(`\nwritten to results/navigation.json`);

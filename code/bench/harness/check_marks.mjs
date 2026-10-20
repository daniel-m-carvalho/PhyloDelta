/**
 * Is a found leaf's mark always on the right node, however the user navigates?
 * (§37.10)
 *
 *   node harness/check_marks.mjs [steps] [seed] [comparison id] [web url]
 *
 * Needs the web app and an API with that comparison. Exits non-zero on any
 * failure.
 *
 * **Why it exists.** The library holds a highlight by *graph id*, and every
 * redraw hands graph ids out again. A mark not re-placed after a redraw stays
 * on whatever node now has its old id: expanding the marked wedge lit an
 * unrelated clade while the chip still said "Found inside", and every step
 * after that pointed somewhere wrong. Reading the code did not find it; this
 * walk does, within the first thirty steps on the code before the fix.
 *
 * **What it does.** A seeded random walk over both panels — jump to a leaf,
 * search for one, go back, reset, expand a wedge (the marked one half the
 * time), expand all, collapse all, clear the mark — and after every step
 * asserts the promise, not a symptom:
 *
 * - nothing marked → nothing lit, no chip;
 * - marked but outside the view (the server's `kept: null`) → nothing lit,
 *   and the chip says "outside this view";
 * - otherwise → the lit node IS the one the slice names as standing for the
 *   leaf, and the chip says "Found" for the leaf itself, "Found inside" for a
 *   wedge.
 *
 * The lit node is read back through `window.__phylodelta.marks()`, which
 * resolves the library's graph id in the drawing on screen. The answer it is
 * held to is the server's own (`markAt`, from the slice's `kept`), checked
 * separately to contain the leaf in every case.
 */

import { launch } from "./browser.mjs";

const STEPS = Number(process.argv[2] ?? 200);
let seed = Number(process.argv[3] ?? 11) >>> 0;
const PAIR = process.argv[4] ?? "vibrio-nj__vibrio-upgma";
const WEB = process.argv[5] ?? "http://localhost:5173";

/** mulberry32: seeded, so a failure is replayable with the same arguments. */
const rnd = (n) => {
  seed = (seed + 0x6d2b79f5) >>> 0;
  let t = seed;
  t = Math.imul(t ^ (t >>> 15), t | 1);
  t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
  return ((((t ^ (t >>> 14)) >>> 0) / 4294967296) * n) | 0;
};

const browser = await launch();
const page = await browser.newPage({ viewport: { width: 1400, height: 900 } });
await page.goto(`${WEB}/#/c/${PAIR}`);
await page.waitForFunction(
  () => window.__phylodelta && window.__phylodelta.state().every((s) => s.tree && !s.loading),
  null,
  { timeout: 30_000 },
);

const settle = async () => {
  await page.waitForTimeout(250);
  await page.waitForFunction(() => window.__phylodelta.state().every((s) => !s.loading), null, {
    timeout: 15_000,
  });
  await page.waitForTimeout(500);
};

// Leaves to jump to, per panel, straight from each tree's search.
const [leftTree, rightTree] = PAIR.split("__");
const targets = await page.evaluate(
  async (trees) =>
    Promise.all(
      trees.map(async (tree) => {
        const found = await fetch(`/api/v1/trees/${tree}/search?q=1&limit=200`).then((r) => r.json());
        return found.matches.filter((m) => m.leaf).map((m) => ({ node: m.node, label: m.label }));
      }),
    ),
  [leftTree, rightTree],
);

const check = (side) =>
  page.evaluate((side) => {
    const state = window.__phylodelta.state()[side];
    const lit = window.__phylodelta.marks()[side];
    const chip =
      document.querySelectorAll(".side-summary")[side]?.querySelector(".found-chip")?.textContent ?? null;
    const wanted = state.markAt?.node ?? null;
    let ok;
    if (state.arrivedAt === null) ok = lit.storedId === null && chip === null;
    else if (state.markOffView) ok = lit.storedId === null && /outside this view/.test(chip ?? "");
    else if (wanted !== null)
      ok = lit.storedId === wanted && (state.markAt.exact ? (chip ?? "").startsWith("Found: ") : /Found inside/.test(chip));
    else ok = true; // its slice has not arrived; nothing to hold it to yet
    return { ok, keep: state.arrivedAt, wanted, off: state.markOffView, lit: lit.storedId, chip };
  }, side);

const counts = {};
const failures = [];
for (let step = 0; step < STEPS; step++) {
  const side = rnd(2);
  const k = rnd(11);
  let what;
  let target = null;
  if (k < 2) {
    what = "jump";
    const t = targets[side][rnd(targets[side].length)];
    target = t.node;
    await page.evaluate(([s, n]) => window.__phylodelta.actions()[s].focusWithContext(n), [side, t.node]);
  } else if (k === 2) {
    what = "search";
    const t = targets[side][rnd(targets[side].length)];
    target = t.node;
    await page.fill(".search-input", t.label);
    await page.waitForSelector(".search-row");
    await page.waitForTimeout(250);
    await page.click(".search-row >> nth=0");
  } else if (k < 5) {
    what = "back";
    await page.evaluate((s) => {
      if (window.__phylodelta.state()[s].canGoBack) window.__phylodelta.actions()[s].back();
    }, side);
  } else if (k < 7) {
    what = "expand wedge";
    await page.evaluate(
      ([s, pick]) => {
        const state = window.__phylodelta.state()[s];
        const wedges = [...state.tree.truncated];
        const marked = state.markAt && !state.markAt.exact ? state.markAt.node : null;
        const id = marked !== null && pick % 2 === 0 ? marked : wedges[pick % Math.max(1, wedges.length)];
        if (id !== undefined) window.__phylodelta.actions()[s].focus(id);
      },
      [side, rnd(1000)],
    );
  } else if (k === 7) {
    what = "collapse all";
    await page.evaluate((s) => window.__phylodelta.actions()[s].collapseAll(), side);
  } else if (k === 8) {
    what = "expand all";
    await page.evaluate((s) => window.__phylodelta.actions()[s].expandAll(), side);
  } else if (k === 9) {
    what = "reset";
    await page.evaluate((s) => window.__phylodelta.actions()[s].reset(), side);
  } else {
    what = "clear mark";
    await page.evaluate((s) => window.__phylodelta.actions()[s].clearMark(), side);
  }
  await settle();
  counts[what] = (counts[what] ?? 0) + 1;
  if (target !== null) {
    // The jump must *take*: the panel ends up holding that leaf, or says why
    // it could not. "Nothing marked anywhere" is consistent, so the checks
    // below cannot see a jump that silently did nothing — which is what a
    // jump into one panel did while the other held a mark (§40).
    let took = false;
    for (let attempt = 0; attempt < 10 && !took; attempt++) {
      took = await page.evaluate(
        ([s, t]) => {
          const st = window.__phylodelta.state()[s];
          return st.arrivedAt === t || st.jumpError !== null;
        },
        [side, target],
      );
      if (!took) await page.waitForTimeout(300);
    }
    if (!took) failures.push(`step ${step} ${what} on ${side ? "right" : "left"} to ${target}: the jump did not take`);
  }
  for (const s of [0, 1]) {
    // Held to it once settled, not on the first frame: drawing every leaf
    // ("expand all" on vibrio is a 35,289-node tree) can delay the chip by a
    // few hundred milliseconds behind a highlight that is already right.
    let r = await check(s);
    for (let retry = 0; !r.ok && retry < 4; retry++) {
      await page.waitForTimeout(400);
      r = await check(s);
    }
    if (!r.ok) failures.push(`step ${step} ${what} on ${side ? "right" : "left"}, ${s ? "right" : "left"} panel: ${JSON.stringify(r)}`);
  }
}
await browser.close();

console.log("steps:", JSON.stringify(counts));
if (failures.length) {
  console.error(`\n${failures.length} wrong marks:`);
  for (const f of failures.slice(0, 20)) console.error("  " + f);
  process.exit(1);
}
console.log("every step: the lit node is the one the slice names, or nothing when it should be");

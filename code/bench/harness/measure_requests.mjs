/**
 * How many requests does navigating cost, and how many could the cache answer?
 *
 *   node harness/measure_requests.mjs [steps] [seed] [latency ms] [comparison id] [web url]
 *
 * The same seeded walk as check_marks.mjs — same steps in the same order for
 * the same seed — recording every API request each step makes, and how long
 * the step takes to settle under an emulated round-trip latency (0 = none).
 *
 * Every slice request carrying a `keep` is also classified against the
 * responses the client had *already received* at that moment, to say what two
 * proposed changes would have saved without making them:
 *
 * - **pin irrelevant**: the server answered `kept: null` (the pinned node is
 *   outside the requested root, so the pin changed nothing) and the same view
 *   without the pin had been fetched before.
 * - **already drawn**: the same view without the pin had been fetched before
 *   and drew the pinned node as itself, which is all a pin promises.
 *
 * Both are upper bounds on the client side: the real cache is bounded (2 MiB,
 * ~300 slices) and this assumes nothing was evicted, which a walk this long
 * does not approach.
 */

import { launch } from "./browser.mjs";

const STEPS = Number(process.argv[2] ?? 200);
let seed = Number(process.argv[3] ?? 11) >>> 0;
const LATENCY = Number(process.argv[4] ?? 0);
const PAIR = process.argv[5] ?? "vibrio-nj__vibrio-upgma";
const WEB = process.argv[6] ?? "http://localhost:5173";

const rnd = (n) => {
  seed = (seed + 0x6d2b79f5) >>> 0;
  let t = seed;
  t = Math.imul(t ^ (t >>> 15), t | 1);
  t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
  return ((((t ^ (t >>> 14)) >>> 0) / 4294967296) * n) | 0;
};

const browser = await launch();
const page = await browser.newPage({ viewport: { width: 1400, height: 900 } });
if (LATENCY > 0) {
  const cdp = await page.context().newCDPSession(page);
  await cdp.send("Network.enable");
  await cdp.send("Network.emulateNetworkConditions", {
    offline: false,
    latency: LATENCY,
    downloadThroughput: -1,
    uploadThroughput: -1,
  });
}

// --- what goes over the wire ------------------------------------------------
let inflight = 0;
let log = [];
/** Every slice response seen, by its request minus `keep`: the "unpinned view". */
const unpinned = new Map();
const viewKey = (u) => {
  const p = new URL(u).searchParams;
  return [new URL(u).pathname, p.get("root") ?? "", p.get("budget"), p.get("compare") ?? "", p.get("metric") ?? ""].join("|");
};
page.on("request", (r) => {
  if (!r.url().includes("/api/")) return;
  inflight++;
  log.push({ url: r.url(), kind: new URL(r.url()).pathname.split("/").pop() });
});
const done = () => { inflight = Math.max(0, inflight - 1); };
page.on("requestfailed", (r) => { if (r.url().includes("/api/")) done(); });
page.on("response", async (r) => {
  if (!r.url().includes("/api/")) return;
  try {
    if (r.url().includes("/slice?") && r.ok()) {
      const body = await r.json();
      const keep = new URL(r.url()).searchParams.get("keep");
      const entry = log.find((e) => e.url === r.url() && !e.body);
      if (entry) entry.body = { kept: body.kept ?? null };
      if (keep === null) {
        const drawn = new Set(body.nodes.id.filter((_, k) => !body.nodes.truncated[k]));
        unpinned.set(viewKey(r.url()), drawn);
      }
    }
  } finally {
    done();
  }
});

await page.goto(`${WEB}/#/c/${PAIR}`);
await page.waitForFunction(
  () => window.__phylodelta && window.__phylodelta.state().every((s) => s.tree && !s.loading),
  null,
  { timeout: 60_000 },
);
await page.waitForTimeout(500);

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
await page.waitForTimeout(300);
await page.evaluate(() => (window.__walk = true));

/**
 * `page.evaluate`, surviving the one way it fails that is not the app's.
 *
 * Polled every 20 ms under Chrome's network emulation, an evaluate now and
 * then reports "Execution context was destroyed" at the moment the app
 * rewrites its URL with `history.replaceState` — a same-document change that
 * keeps the page. Measured: it killed two 250-step runs at step 36 with no
 * reload, no page error and no crash. So it is retried; and so a retry can
 * never hide a real reload, the walk marks the page at the start and fails
 * loudly if the mark is ever gone.
 */
async function poll(fn, arg) {
  for (let attempt = 0; ; attempt++) {
    try {
      const [alive, value] = await page.evaluate(
        ([source, a]) => [window.__walk === true, (0, eval)(`(${source})`)(a)],
        [fn.toString(), arg],
      );
      if (!alive) throw new Error("the page was reloaded during the walk — the measurement is void");
      return value;
    } catch (failed) {
      if (attempt >= 5 || !/Execution context was destroyed/.test(String(failed))) throw failed;
      await new Promise((r) => setTimeout(r, 50));
    }
  }
}

/**
 * How long the user waits: until what the step asked for is on screen.
 *
 * Not "until the network is quiet": a request the user is not waiting on
 * would be charged to the step. So a jump or search is done when its panel
 * shows the target (marked, or reported as unreachable) and is not loading;
 * any other step when neither panel is loading. Either held for 150ms, so a
 * flicker does not count as done.
 */
async function settled(t0, side, target) {
  let since = null;
  for (;;) {
    const ready = await poll(
      ([side, target]) => {
        const states = window.__phylodelta.state();
        if (states.some((s) => s.loading)) return false;
        if (target === null) return true;
        const s = states[side];
        return s.jumpError !== null || (s.arrivedAt === target && (s.markAt !== null || s.markOffView));
      },
      [side, target],
    );
    const now = Date.now();
    if (ready) {
      since ??= now;
      if (now - since >= 150) return since - t0;
    } else since = null;
    await new Promise((r) => setTimeout(r, 20));
  }
}

const perKind = {};
const add = (what, field, n = 1) => {
  perKind[what] ??= { steps: 0, requests: 0, slices: 0, ancestor: 0, search: 0, pinned: 0, pinIrrelevant: 0, alreadyDrawn: 0, ms: [] };
  perKind[what][field] += n;
};

for (let step = 0; step < STEPS; step++) {
  const side = rnd(2);
  const k = rnd(11);
  let what;
  let target = null;
  log = [];
  const pinnedBefore = new Map(unpinned); // what the client knew before this step
  const t0 = Date.now();
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
  const ms = await settled(t0, side, target);
  // Let what this step started finish before the next one, so its requests
  // are counted against the step that caused them.
  while (inflight > 0) await new Promise((r) => setTimeout(r, 20));
  add(what, "steps");
  perKind[what].ms.push(what === "search" ? ms - 250 : ms); // the search's own typing wait is not network
  for (const e of log) {
    add(what, "requests");
    if (e.kind === "slice") {
      add(what, "slices");
      const keep = new URL(e.url).searchParams.get("keep");
      if (keep !== null) {
        add(what, "pinned");
        const before = pinnedBefore.get(viewKey(e.url));
        if (before && e.body && e.body.kept === null) add(what, "pinIrrelevant");
        else if (before && before.has(Number(keep))) add(what, "alreadyDrawn");
      }
    } else if (e.kind === "ancestor") add(what, "ancestor");
    else if (e.kind === "search") add(what, "search");
  }
}
await browser.close();

const median = (xs) => {
  const s = [...xs].sort((a, b) => a - b);
  return s.length ? s[(s.length - 1) >> 1] : 0;
};
const rows = Object.entries(perKind).sort((a, b) => b[1].requests - a[1].requests);
const total = { steps: 0, requests: 0, slices: 0, ancestor: 0, search: 0, pinned: 0, pinIrrelevant: 0, alreadyDrawn: 0 };
console.log(`latency ${LATENCY} ms per round trip, ${STEPS} steps, seed ${process.argv[3] ?? 11}\n`);
console.log("step kind      steps  requests  /step  slices  ancestor  search  pinned  pin-irrelevant  already-drawn  median ms");
for (const [what, r] of rows) {
  for (const f of Object.keys(total)) total[f] += r[f];
  console.log(
    `${what.padEnd(13)} ${String(r.steps).padStart(5)} ${String(r.requests).padStart(9)} ${(r.requests / r.steps).toFixed(2).padStart(6)} ${String(r.slices).padStart(7)} ${String(r.ancestor).padStart(9)} ${String(r.search).padStart(7)} ${String(r.pinned).padStart(7)} ${String(r.pinIrrelevant).padStart(15)} ${String(r.alreadyDrawn).padStart(14)} ${String(median(r.ms)).padStart(10)}`,
  );
}
console.log(
  `${"all".padEnd(13)} ${String(total.steps).padStart(5)} ${String(total.requests).padStart(9)} ${(total.requests / total.steps).toFixed(2).padStart(6)} ${String(total.slices).padStart(7)} ${String(total.ancestor).padStart(9)} ${String(total.search).padStart(7)} ${String(total.pinned).padStart(7)} ${String(total.pinIrrelevant).padStart(15)} ${String(total.alreadyDrawn).padStart(14)}`,
);

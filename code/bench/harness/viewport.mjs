/**
 * Does the payload track the viewport, or the tree?
 *
 * Every other table here establishes that the payload does **not** grow with the
 * tree. None of them establishes the other half of the claim — that it is *sized
 * to the viewport* — because they all ran at one window size. Invariance to the
 * tree is necessary but not sufficient: a server returning a fixed 50 leaves
 * whatever the window would satisfy every existing table while flatly not doing
 * what the design says it does.
 *
 * So this varies the window and holds the tree, and varies the tree and holds the
 * window, in one grid. The two claims are then separable:
 *
 *   down a column  — same window, 32x more leaves: the payload must not move
 *   across a row   — same tree, a taller window: the payload must grow with it
 *
 * The quantity measured is the **slice responses only**, summed across both
 * panels, taken from the wire. Not the whole page load: the bundle and the
 * catalogue are fixed costs that would dilute the very effect being looked for.
 *
 * `readableBudget` quantises to 25 leaves so that a settling layout does not cost
 * a request, so the payload steps rather than rises smoothly. That is the design
 * and not noise, and the budget column shows it.
 */
import { writeFileSync, readFileSync, mkdirSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { launch, versionOf } from "./browser.mjs";
import { start } from "./serve.mjs";

const HERE = fileURLToPath(new URL(".", import.meta.url));
const BENCH = join(HERE, "..");
const PORT = 8093;
const LOAD_MS = 180_000;

//: Window heights, in CSS pixels, from a short laptop window to a rotated 4K
//: panel. The width is held at 1440 because the budget derives from height alone
//: — a panel is a column, and widening it adds no rows.
//:
//: Sampled to **cross the quantisation steps**, not evenly. `readableBudget`
//: rounds to 25 leaves at 14 px each, so one step is ~350 px of panel and an
//: evenly-spaced sample lands four heights inside one bucket: the first run of
//: this used 400-1000 and reported an identical payload four times, which looks
//: like the payload ignoring the viewport when it is the sample missing the
//: steps.
const HEIGHTS = [400, 700, 1000, 1200, 1400, 1700, 2000, 2600, 3200];

//: Two rungs, three orders of magnitude apart in leaves. More would not add to
//: the argument: the point of the tree axis here is that it does nothing, and the
//: ten-rung version of that is already Tables 12 and 19.
const RUNGS = [17645, 564640];

function say(line) {
  writeFileSync(1, line + "\n");
}

/** Sum the bytes of the slice responses, which is the payload under test. */
function sliceMeter(page) {
  const pending = [];
  let bytes = 0;
  let count = 0;
  page.on("requestfinished", (request) => {
    if (!request.url().includes("/slice")) return;
    pending.push(
      (async () => {
        try {
          const sizes = await request.sizes();
          bytes += (sizes.responseBodySize || 0) + (sizes.responseHeadersSize || 0);
          count += 1;
        } catch {
          /* page gone; not observed */
        }
      })(),
    );
  });
  return {
    async settle() {
      await Promise.all(pending);
      return { bytes, count };
    },
  };
}

async function measure(pairId, height) {
  const browser = await launch();
  const page = await browser.newPage({ viewport: { width: 1440, height } });
  const counted = sliceMeter(page);
  try {
    await page.goto(`http://localhost:${PORT}/#/c/${pairId}`, { timeout: LOAD_MS });
    await page.waitForFunction(
      () =>
        window.__phylodelta !== undefined &&
        window.__phylodelta.state().every((s) => s.tree !== null && !s.loading),
      undefined,
      { timeout: LOAD_MS },
    );
    const view = await page.evaluate(() => {
      const [left, right] = window.__phylodelta.state();
      const host = document.querySelector(".panel, .side, canvas");
      return {
        budget: left.budget,
        auto_budget: left.autoBudget,
        displayed_leaves: left.slice ? left.slice.displayed_leaves : null,
        total_leaves: left.slice ? left.slice.total_leaves : null,
        right_budget: right.budget,
        panel_px: host ? Math.round(host.getBoundingClientRect().height) : null,
      };
    });
    return { ok: true, ...view, ...(await counted.settle()) };
  } catch (failed) {
    return {
      ok: false,
      failed: String(failed.message || failed).split("\n")[0],
      ...(await counted.settle()),
    };
  } finally {
    await browser.close().catch(() => {});
  }
}

const built = JSON.parse(readFileSync(join(BENCH, "results", "server_build.json"), "utf8"));
const pairs = new Map(
  built.filter((r) => r.status === "ready").map((r) => [r.leaves, r.id]),
);
const server = await start(PORT);
const probe = await launch();
const BROWSER = versionOf(probe);
await probe.close();

mkdirSync(join(BENCH, "results"), { recursive: true });
const rows = [];
say(`\n${BROWSER} · width 1440, height varied · slice payload only, from the wire\n`);
say(
  `${"window".padStart(8)}  ${"panel".padStart(7)}  ${"budget".padStart(7)}  ` +
    RUNGS.map((n) => `${n.toLocaleString()} leaves`.padStart(18)).join("  "),
);

try {
  for (const height of HEIGHTS) {
    const cells = [];
    for (const leaves of RUNGS) {
      const pairId = pairs.get(leaves);
      if (!pairId) {
        cells.push({ leaves, ok: false, failed: "not built" });
        continue;
      }
      cells.push({ leaves, ...(await measure(pairId, height)) });
    }
    rows.push({ height, cells });
    const first = cells.find((c) => c.ok) ?? {};
    say(
      `${String(height).padStart(8)}  ${String(first.panel_px ?? "—").padStart(7)}  ` +
        `${String(first.budget ?? "—").padStart(7)}  ` +
        cells
          .map((c) =>
            c.ok
              ? `${(c.bytes / 1024).toFixed(1)} KB / ${c.displayed_leaves} tips`.padStart(18)
              : `FAIL`.padStart(18),
          )
          .join("  "),
    );
    for (const c of cells) if (!c.ok) say(`          ${c.leaves}: ${c.failed}`);
  }
} finally {
  server.close();
}

writeFileSync(
  join(BENCH, "results", "viewport.json"),
  JSON.stringify({ browser: BROWSER, width: 1440, heights: HEIGHTS, rungs: RUNGS, rows }, null, 2),
);
say(`\nwritten to results/viewport.json`);

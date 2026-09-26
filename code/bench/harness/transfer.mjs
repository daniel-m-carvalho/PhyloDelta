/**
 * Bytes over the wire: the thesis claim stated as the quantity it is about.
 *
 * "A server should send a summary sized to the viewport and never the whole
 * tree" is a claim about **transferred bytes**, and until this ran it was the one
 * quantity not measured. Table 12 gave a slice's size with nothing to compare it
 * against; Table 8's "bundle size" is the upload. Everything else measured time,
 * memory, or drawn elements — consequences of the transfer rather than the
 * transfer.
 *
 * **Measured from the wire, not from `stat`.** File sizes on disk would be a
 * decent estimate and a bad measurement: they miss headers, miss the application
 * bundle entirely, and cannot see a request the tool makes that nobody predicted.
 * Every response is counted through Playwright's `request.sizes()`, which reports
 * what the transport carried.
 *
 * **Both application bundles are counted, separately from data.** This is the
 * trap Table 2 exists to warn about: PhyloDelta ships a ~476 KB JS bundle, so
 * quoting only its 6 KB slices against phylo.io's whole-tree download would be
 * comparing a partial cost with a total one. App and data are reported in
 * separate columns so a reader can add them as they see fit — and at the smallest
 * rungs PhyloDelta loses on total bytes, which the table has to show.
 *
 * **What "reached" means differs by tool, and the table says so.** For
 * PhyloDelta the measurement ends when both panels are showing a comparison. For
 * phylo.io it ends when both Newick files have arrived — which is *not* the same
 * as being able to use them: above 17,645 leaves the comparison never completes
 * (Table 1). Separating the download from the outcome is what lets the finding be
 * stated precisely: it transfers 35 MB and still cannot open the comparison.
 *
 * **Run twice, once per transport.** Uncompressed by default; with `BENCH_GZIP=1`
 * `serve.mjs` compresses static files *and* proxied API responses, and the results
 * go to their own file. Both tools get the same treatment in both runs — the API
 * had to be compressed in the proxy, since FastAPI ships no GZipMiddleware, or the
 * gzip run would have compressed phylo.io's Newick and left this frontend's JSON
 * alone, measuring a transport difference and reporting it as a design one.
 */
import { writeFileSync, readFileSync, existsSync, mkdirSync, appendFileSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { launch, versionOf } from "./browser.mjs";
import { start } from "./serve.mjs";

const HERE = fileURLToPath(new URL(".", import.meta.url));
const BENCH = join(HERE, "..");
const PORT = 8096;
const VIEWPORT = { width: 1440, height: 900 };

//: Downloading 35 MB from localhost is fast; parsing it is what is slow, and this
//: runner does not parse. Generous anyway, because a rung that times out must be
//: reported as a timeout rather than as a zero.
const FETCH_MS = 300_000;
const LOAD_MS = 300_000;

function say(line) {
  writeFileSync(1, line + "\n");
}

/**
 * Accumulate transferred bytes per response, split app from data.
 *
 * `requestfinished` rather than `response`, because `sizes()` is only complete
 * once the body has been read — asking on the response event returns a
 * responseBodySize of 0 for anything still streaming, which at 35 MB is all of
 * it.
 */
function meter(page) {
  const totals = { app: 0, data: 0, other: 0, requests: 0, byUrl: [] };
  const pending = [];

  page.on("requestfinished", (request) => {
    pending.push(
      (async () => {
        let sizes;
        try {
          sizes = await request.sizes();
        } catch {
          return; // the page went away mid-flight; counted as not observed
        }
        const bytes =
          (sizes.responseBodySize || 0) + (sizes.responseHeadersSize || 0);
        const url = new URL(request.url()).pathname;
        // Data is the tree content: Newick files for one tool, API responses for
        // the other. Everything else a page fetches to exist is application.
        const isData = url.startsWith("/trees/") || url.startsWith("/api/");
        totals[isData ? "data" : "app"] += bytes;
        totals.requests += 1;
        totals.byUrl.push({ url, bytes, kind: isData ? "data" : "app" });
      })(),
    );
  });

  return {
    totals,
    /** Let the in-flight size lookups land before reading the totals. */
    async settle() {
      await Promise.all(pending);
      // Largest first, trimmed: enough to see what dominates without carrying a
      // few hundred asset rows into the results file.
      totals.byUrl.sort((a, b) => b.bytes - a.bytes);
      totals.byUrl = totals.byUrl.slice(0, 8);
      return totals;
    },
  };
}

function nwk(leaves, side) {
  return `/trees/ladder/ladder-${String(leaves).padStart(6, "0")}-${side}.nwk`;
}

async function runPhyloio(leaves) {
  const browser = await launch();
  const page = await browser.newPage({ viewport: VIEWPORT });
  const counted = meter(page);
  try {
    await page.goto(`http://localhost:${PORT}/harness/transfer.html`, { timeout: LOAD_MS });
    await page.waitForFunction(() => window.__transferReady === true, undefined, {
      timeout: LOAD_MS,
    });
    const received = await page.evaluate(
      ([a, b]) => window.__transfer.fetchTrees(a, b),
      [nwk(leaves, "a"), nwk(leaves, "b")],
    );
    return { ok: true, received, ...(await counted.settle()) };
  } catch (failed) {
    // Partial totals are still worth having: they say how far the download got.
    return {
      ok: false,
      failed: String(failed.message || failed).split("\n")[0],
      ...(await counted.settle()),
    };
  } finally {
    await browser.close().catch(() => {});
  }
}

async function runPhylodelta(pairId) {
  const browser = await launch();
  const page = await browser.newPage({ viewport: VIEWPORT });
  const counted = meter(page);
  try {
    await page.goto(`http://localhost:${PORT}/#/c/${pairId}`, { timeout: LOAD_MS });
    // The same readiness signal the ceiling run uses: both panels stating what
    // they are showing. Stopping earlier would undercount the slices.
    await page.waitForFunction(
      () =>
        [...document.querySelectorAll(".side-counts")].filter((n) =>
          /showing/.test(n.textContent || ""),
        ).length === 2,
      undefined,
      { timeout: LOAD_MS },
    );
    const shown = await page.evaluate(() =>
      [...document.querySelectorAll(".side-counts")].map((n) =>
        (n.textContent || "").replace(/\s+/g, " ").trim(),
      ),
    );
    return { ok: true, shown, ...(await counted.settle()) };
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
    return await withDeadline(fn(), FETCH_MS, label);
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
//: Which transport this run measures. Separate files, because the two are not
//: interchangeable and merging them would silently mix encodings in one column.
const GZIP = process.env.BENCH_GZIP === "1";
const suffix = GZIP ? "_gzip" : "";
const out = join(BENCH, "results", `transfer${suffix}.json`);
const stream = join(BENCH, "results", `transfer${suffix}.jsonl`);
const only = process.argv[2] ? Number(process.argv[2]) : null;
const previous =
  only !== null && existsSync(out) ? JSON.parse(readFileSync(out, "utf8")).rows : [];
if (!existsSync(stream)) writeFileSync(stream, "");

const rows = [];
const mb = (bytes) => bytes / 1e6;
say(
  `\n${BROWSER} · ${GZIP ? "GZIP" : "uncompressed"}, one origin · ` +
    `bytes measured from the wire\n`,
);
say(
  `${"leaves".padStart(9)}  ${"phylo.io app".padStart(12)} ${"data".padStart(10)}` +
    `  ${"PhyloDelta app".padStart(14)} ${"data".padStart(9)}  ${"data ratio".padStart(10)}`,
);

try {
  for (const rung of built.filter(
    (r) => r.status === "ready" && (only === null || r.leaves === only),
  )) {
    const phyloio = await attempt("phylo.io", () => runPhyloio(rung.leaves));
    const phylodelta = await attempt("phylodelta", () => runPhylodelta(rung.id));

    const row = { leaves: rung.leaves, pair: rung.id, phyloio, phylodelta };
    rows.push(row);
    appendFileSync(stream, JSON.stringify(row) + "\n");

    const ratio =
      phyloio.data && phylodelta.data ? (phyloio.data / phylodelta.data).toFixed(0) : "—";
    say(
      `${rung.leaves.toLocaleString().padStart(9)}  ` +
        `${mb(phyloio.app ?? 0).toFixed(2).padStart(9)} MB ${mb(phyloio.data ?? 0).toFixed(2).padStart(7)} MB` +
        `  ${mb(phylodelta.app ?? 0).toFixed(2).padStart(11)} MB ` +
        `${((phylodelta.data ?? 0) / 1024).toFixed(1).padStart(6)} KB` +
        `  ${String(ratio).padStart(8)}x`,
    );
    if (!phyloio.ok) say(`           phylo.io: ${phyloio.failed}`);
    if (!phylodelta.ok) say(`           PhyloDelta: ${phylodelta.failed}`);
  }
} finally {
  server.close();
}

const merged = [...previous.filter((r) => !rows.some((n) => n.leaves === r.leaves)), ...rows].sort(
  (a, b) => a.leaves - b.leaves,
);
writeFileSync(
  out,
  JSON.stringify({ browser: BROWSER, viewport: VIEWPORT, compressed: GZIP, rows: merged }, null, 2),
);
say(`\nwritten to results/transfer${suffix}.json`);

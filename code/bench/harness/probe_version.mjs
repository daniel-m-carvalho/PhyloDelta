/**
 * Do the two findings about phylo.io still hold on the current release?
 *
 * The comparison was measured against 2.1.1 (a 2025-07-02 checkout); 2.2.5 shipped
 * 2026-01-30. Most findings here follow from architecture — the whole tree in
 * memory, the comparison in a worker — which patch releases do not change. One
 * does not: "Highlight BCN throws" is a bug report, and bug reports expire.
 *
 * So exactly two questions, against the release's own prebuilt `dist/`:
 *
 *   1. does `trigger_("BCN", …)` still throw?
 *   2. does the comparison still fail to complete above 17,645 leaves?
 *
 * Run with PHYLOIO_DIST pointing at the version under test, so the same probe
 * answers for both and the answer cannot come from a difference in the harness.
 */
import { createServer } from "node:http";
import { createReadStream, statSync, writeFileSync } from "node:fs";
import { extname, join, normalize } from "node:path";
import { fileURLToPath } from "node:url";
import { launch, versionOf } from "./browser.mjs";

const HERE = fileURLToPath(new URL(".", import.meta.url));
const BENCH = join(HERE, "..");
const DIST = process.env.PHYLOIO_DIST;
if (!DIST) throw new Error("set PHYLOIO_DIST to the version's dist/ directory");
const LABEL = process.env.PHYLOIO_LABEL ?? DIST;
const PORT = Number(process.env.PROBE_PORT ?? 8092);
const LEAVES = Number(process.argv[2] ?? 1000);
const COMPARE_MS = Number(process.env.COMPARE_MS ?? 300_000);

const TYPES = { ".html": "text/html", ".js": "text/javascript", ".nwk": "text/plain" };

// A minimal server: only what this probe needs, and the dist root is swappable.
const server = createServer((req, res) => {
  const url = decodeURIComponent((req.url || "/").split("?")[0]);
  /*
   * The worker chunks, mapped before anything else.
   *
   * phylo.io's bundle builds its workers with `new Worker(new URL(...,
   * import.meta.url))`, which webpack resolves RELATIVE TO THE PAGE — so they are
   * requested at /harness/src_worker_*.phylo.js, not from the dist. Without this
   * they 404, the BCN worker never constructs, `message_loader` never clears, and
   * the probe reports "the comparison did not complete" for a version that
   * completes fine. That is exactly how the first ceiling run was invalidated
   * (DECISIONS, Corrections), and it would have produced a false finding about a
   * release rather than about a rung.
   */
  const worker = /^\/harness\/(src_worker_\w+\.phylo\.js)$/.exec(url);
  if (worker) {
    const chunk = join(DIST, worker[1]);
    res.writeHead(200, { "Content-Type": "text/javascript", "Cache-Control": "no-store" });
    createReadStream(chunk).pipe(res);
    return;
  }

  const file = url.startsWith("/phyloio/dist/")
    ? join(DIST, normalize(url.slice("/phyloio/dist/".length)))
    : url.startsWith("/trees/")
      ? join(BENCH, "trees", normalize(url.slice("/trees/".length)))
      : join(BENCH, "harness", normalize(url.replace(/^\/harness\//, "")));
  try {
    if (!statSync(file).isFile()) throw new Error("nope");
  } catch {
    console.error(`  !! 404 ${url}`);
    res.writeHead(404).end("not found");
    return;
  }
  res.writeHead(200, {
    "Content-Type": TYPES[extname(file)] ?? "application/octet-stream",
    "Cache-Control": "no-store",
  });
  createReadStream(file).pipe(res);
});
await new Promise((r) => server.listen(PORT, r));

const nwk = (side) => `/trees/ladder/ladder-${String(LEAVES).padStart(6, "0")}-${side}.nwk`;
//: Fresh page loads. The finding this probe exists to pin down is that the
//: outcome is decided per load and then holds for almost every node in it, so one
//: load can only ever report one of the two behaviours — which is how "it throws"
//: was recorded from n=1 in the first place.
const LOADS = Number(process.env.PROBE_LOADS ?? 1);
const loads = [];

for (let load = 0; load < LOADS; load++) {
const browser = await launch();
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
const out = { label: LABEL, browser: versionOf(browser), leaves: LEAVES, load };

try {
  await page.goto(`http://localhost:${PORT}/harness/navigation.html`, { timeout: 120_000 });
  await page.waitForFunction(() => window.__navReady === true, undefined, { timeout: 120_000 });

  const loaded = await page.evaluate(
    ([a, b, budget]) => window.__nav.load(a, b, budget),
    [nwk("a"), nwk("b"), COMPARE_MS],
  );
  out.comparison_completed = loaded.ready;

  if (loaded.ready) {
    const candidates = await page.evaluate(() => window.__nav.candidates(40));
    out.candidates = candidates.length;
    out.with_bcn = candidates.filter((c) => c.hasBcn).length;
    /*
     * Many attempts, not three.
     *
     * The first run of this tried three and got one success on 2.2.5 against
     * none on 2.1.1, which reads as "fixed in the new release". Both versions'
     * crash paths are byte-identical and so is model construction, so a
     * behavioural difference had to be either non-determinism or a difference in
     * WHICH nodes got tried. Three attempts cannot tell those apart.
     */
    const attempts = Number(process.env.BCN_ATTEMPTS ?? 15);
    const tried = [];
    for (const node of candidates.filter((c) => c.hasBcn).slice(0, attempts)) {
      const got = await page.evaluate((at) => window.__nav.bcn(at), node.at);
      tried.push({ leaves: node.leaves, ...got });
    }
    out.attempted = tried.length;
    out.succeeded = tried.filter((t) => t && t.ms !== undefined).length;
    out.threw = tried.filter((t) => t && t.error).length;
    out.reachable = tried.filter((t) => t && t.reachable).length;
    out.bcn_throws_always = out.succeeded === 0;
    // Kept so a reader can see which clades worked rather than take a count.
    out.detail = tried.map((t) => ({
      leaves: t.leaves,
      ok: t.ms !== undefined,
      reachable: t.reachable,
    }));
  }
} catch (failed) {
  out.failed = String(failed.message || failed).split("\n")[0];
} finally {
  await browser.close().catch(() => {});
}
loads.push(out);
writeFileSync(
  1,
  `  load ${load + 1}/${LOADS}: completed=${out.comparison_completed} ` +
    `jump ${out.succeeded ?? 0}/${out.attempted ?? 0}\n`,
);
}

server.close();

const withSuccess = loads.filter((l) => (l.succeeded ?? 0) > 0).length;
const summary = {
  label: LABEL,
  browser: loads[0]?.browser,
  leaves: LEAVES,
  loads: loads.length,
  loads_with_any_success: withSuccess,
  loads_all_failed: loads.length - withSuccess,
  attempts_total: loads.reduce((n, l) => n + (l.attempted ?? 0), 0),
  attempts_succeeded: loads.reduce((n, l) => n + (l.succeeded ?? 0), 0),
  per_load: loads.map((l) => ({
    completed: l.comparison_completed,
    attempted: l.attempted ?? 0,
    succeeded: l.succeeded ?? 0,
  })),
};
if (process.env.PROBE_OUT) {
  writeFileSync(process.env.PROBE_OUT, JSON.stringify(summary, null, 2));
}
console.log(JSON.stringify(summary, null, 2));

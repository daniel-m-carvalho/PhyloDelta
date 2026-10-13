/** Drive phylo.io's compare and dump its per-clade scores for comparison. */
import { readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { launch } from "./browser.mjs";
import { start } from "./serve.mjs";

const BENCH = join(fileURLToPath(new URL(".", import.meta.url)), "..");
const leaves = Number(process.argv[2] ?? 10000);
const PORT = 8096;
const server = await start(PORT);
const browser = await launch();
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
page.on("pageerror", (e) => console.log("  pageerror:", e.message.split("\n")[0]));

try {
  await page.goto(`http://localhost:${PORT}/harness/accuracy.html`, { timeout: 120_000 });
  await page.waitForFunction(() => window.__benchReady === true, undefined, { timeout: 120_000 });
  const pad = String(leaves).padStart(6, "0");
  const result = await page.evaluate(
    ([a, b]) => window.__bench.extract(a, b),
    [`/trees/ladder/ladder-${pad}-a.nwk`, `/trees/ladder/ladder-${pad}-b.nwk`],
  );
  const out = join(BENCH, "results", `phyloio_scores_${leaves}.json`);
  writeFileSync(out, JSON.stringify(result));
  console.log(
    `${leaves.toLocaleString()} leaves: ${result.clades.length.toLocaleString()} clades, ` +
      `${result.scored.toLocaleString()} scored, ${result.unscored.toLocaleString()} unscored`,
  );
  console.log(`written to ${out}`);
} finally {
  await browser.close();
  server.close();
}

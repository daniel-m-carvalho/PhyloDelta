import { launch } from "./browser.mjs";
import { start } from "./serve.mjs";
const PORT = 8094;
const server = await start(PORT);
const browser = await launch();
const page = await browser.newPage();
const failed = [];
page.on("requestfailed", (r) => failed.push(`FAILED ${r.url()}`));
page.on("response", (r) => { if (r.status() >= 400) failed.push(`${r.status()} ${r.url()}`); });
page.on("pageerror", (e) => failed.push(`pageerror: ${e.message.split("\n")[0]}`));
page.on("console", (m) => { if (m.type() === "error") failed.push(`console: ${m.text().slice(0,120)}`); });

await page.goto(`http://localhost:${PORT}/harness/accuracy.html`);
await page.waitForFunction(() => window.__benchReady === true, undefined, { timeout: 60_000 });
await page.evaluate(async () => {
  const [a, b] = await Promise.all([
    fetch("/trees/ladder/ladder-001000-a.nwk").then((r) => r.text()),
    fetch("/trees/ladder/ladder-001000-b.nwk").then((r) => r.text()),
  ]);
  const phylo = PhyloIO.init();
  const c1 = phylo.create_container("left");
  const c2 = phylo.create_container("right");
  phylo.settings.compareMode = true;
  phylo.bound_container = [c1, c2];
  c1.add_tree(a); c2.add_tree(b);
  phylo.start();
  await new Promise((r) => setTimeout(r, 20_000));
});
console.log(failed.length ? failed.slice(0, 10).join("\n") : "no failures observed");
await browser.close(); server.close();

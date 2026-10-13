import { launch } from "./browser.mjs";
import { start } from "./serve.mjs";
const PORT = 8095;
const server = await start(PORT);
const browser = await launch();
const page = await browser.newPage();
page.on("pageerror", (e) => console.log("pageerror:", e.message.split("\n")[0]));
await page.goto(`http://localhost:${PORT}/harness/accuracy.html`);
await page.waitForFunction(() => window.__benchReady === true, undefined, { timeout: 60_000 });

const shape = await page.evaluate(async () => {
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
  await new Promise((r) => setTimeout(r, 15_000));

  const look = (label, model) => {
    if (!model) return `${label}: <no model>`;
    const root = model.data;
    if (!root) return `${label}: model has no .data (keys: ${Object.keys(model).slice(0,12)})`;
    const kids = root.children || root.branchset || [];
    return `${label}: root keys=[${Object.keys(root).slice(0, 16).join(",")}] children=${kids.length}`;
  };
  return [
    look("models[0]", c1.models[0]),
    look("viewer.model", c1.viewer && c1.viewer.model),
    `loader=${JSON.stringify(c1.message_loader)}`,
  ].join("\n");
});
console.log(shape);
await browser.close(); server.close();

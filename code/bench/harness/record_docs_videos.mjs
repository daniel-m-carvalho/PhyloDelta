/**
 * Records the videos in docs/videos/ — one per task in docs/web-app-guide.md —
 * and the annotated screenshot in docs/images/.
 *
 *   node harness/record_docs_videos.mjs [web url] [only, e.g. 03,04]
 *
 * **Re-run it when the interface changes** rather than re-recording by hand:
 * every video is this script driving the real app, so they stay consistent
 * with one another and with the guide.
 *
 * Needs, against a **fresh store** (the upload video adds a comparison and the
 * remove video deletes it, so run all of them, in order, on a store you do not
 * mind changing):
 *
 *   export PHYLODELTA_STORE=/tmp/docs_store
 *   uv run phylodelta build-all                                   # code/server
 *   uv run uvicorn phylodelta.api.app:app --port 8020             # code/server
 *   uv run phylodelta worker                                      # code/server
 *   PHYLODELTA_API=http://127.0.0.1:8020 npx vite --port 5181     # code/web
 *
 * and ffmpeg on the PATH (Playwright records WebM; GitHub and most players
 * want H.264 MP4).
 *
 * Headless Chrome draws no pointer, so the page gets a drawn one that follows
 * the mouse and shows each click, and a caption line saying what is being done,
 * since the videos have no sound. Long waits on the server are sped up in the
 * MP4, and the caption says so while they are.
 */

import { execFileSync } from "node:child_process";
import { mkdirSync, mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { launch } from "./browser.mjs";

const WEB = process.argv[2] ?? "http://localhost:5181";
const ONLY = process.argv[3]?.split(",") ?? null;
const PAIR = "vibrio-nj__vibrio-upgma";

const here = fileURLToPath(new URL(".", import.meta.url));
const REPO = join(here, "..", "..", "..");
const VIDEOS = join(REPO, "docs", "videos");
const IMAGES = join(REPO, "docs", "images");
const DATASETS = join(REPO, "datasets");
const SIZE = { width: 1280, height: 800 };

mkdirSync(VIDEOS, { recursive: true });
mkdirSync(IMAGES, { recursive: true });
const scratch = mkdtempSync(join(tmpdir(), "phylodelta-docs-"));

// --- the drawn pointer and the caption, installed in every page ----------

const OVERLAY = () => {
  const install = () => {
    if (document.getElementById("doc-cursor")) return;
    const style = document.createElement("style");
    style.textContent = `
      #doc-cursor { position: fixed; left: 0; top: 0; width: 22px; height: 22px; z-index: 2147483647;
        pointer-events: none; transform: translate(-100px, -100px); }
      #doc-cursor svg { filter: drop-shadow(0 1px 2px rgba(0,0,0,.45)); }
      .doc-ripple { position: fixed; z-index: 2147483646; pointer-events: none; width: 34px; height: 34px;
        margin: -17px 0 0 -17px; border-radius: 50%; border: 3px solid #d9480f;
        animation: doc-ripple .55s ease-out forwards; }
      .doc-ripple.right { border-color: #7048e8; }
      @keyframes doc-ripple { from { transform: scale(.3); opacity: 1 } to { transform: scale(1.4); opacity: 0 } }
      #doc-caption { position: fixed; right: 16px; top: 58px;
        z-index: 2147483645; pointer-events: none; max-width: 780px; padding: 9px 16px;
        border-radius: 10px; background: rgba(20, 24, 32, .86); color: #fff;
        font: 500 16px/1.35 system-ui, -apple-system, "Segoe UI", sans-serif; text-align: left;
        transition: opacity .25s; opacity: 0; }
      #doc-caption.on { opacity: 1; }`;
    document.head.appendChild(style);
    const cursor = document.createElement("div");
    cursor.id = "doc-cursor";
    cursor.innerHTML =
      '<svg width="22" height="22" viewBox="0 0 22 22"><path d="M3 2 L3 18 L7.5 13.8 L10.6 20.4 L13.4 19.1 ' +
      'L10.4 12.6 L16.5 12.6 Z" fill="#111" stroke="#fff" stroke-width="1.4" stroke-linejoin="round"/></svg>';
    document.body.appendChild(cursor);
    const caption = document.createElement("div");
    caption.id = "doc-caption";
    document.body.appendChild(caption);
    const move = (event) => {
      cursor.style.transform = `translate(${event.clientX - 3}px, ${event.clientY - 2}px)`;
    };
    // Capture phase, so a component that stops propagation still moves it.
    window.addEventListener("mousemove", move, true);
    window.addEventListener(
      "mousedown",
      (event) => {
        move(event);
        const ripple = document.createElement("div");
        ripple.className = event.button === 2 ? "doc-ripple right" : "doc-ripple";
        ripple.style.left = `${event.clientX}px`;
        ripple.style.top = `${event.clientY}px`;
        document.body.appendChild(ripple);
        setTimeout(() => ripple.remove(), 600);
      },
      true,
    );
  };
  if (document.body) install();
  else document.addEventListener("DOMContentLoaded", install);
};

// --- one recording --------------------------------------------------------

/**
 * Runs `scenario` in a fresh recorded page and writes `<name>.mp4` and the
 * `<name>.png` still. The scenario gets helpers that move the drawn pointer
 * the way a hand would, and marks the moments to cut, speed up and use as the
 * still.
 */
async function record(browser, name, scenario) {
  if (ONLY && !ONLY.some((prefix) => name.startsWith(prefix))) return;
  const raw = join(scratch, name);
  const context = await browser.newContext({
    viewport: SIZE,
    deviceScaleFactor: 1,
    recordVideo: { dir: raw, size: SIZE },
    acceptDownloads: true,
  });
  await context.addInitScript(OVERLAY);
  const page = await context.newPage();
  const started = Date.now();
  const now = () => (Date.now() - started) / 1000;

  let pointer = { x: SIZE.width / 2, y: SIZE.height / 2 };
  const marks = { start: 0, fast: [], poster: null };

  const h = {
    page,
    /** Where the video begins: after the first page has drawn. */
    begin: () => {
      marks.start = now();
    },
    /** Captions sit top right; "left" moves them clear of a menu that opens there. */
    captionSide: (side) =>
      page.evaluate((side) => {
        const el = document.getElementById("doc-caption");
        el.style.right = side === "left" ? "auto" : "16px";
        el.style.left = side === "left" ? "16px" : "auto";
      }, side),
    caption: async (text, hold = 0) => {
      await page.evaluate((text) => {
        const el = document.getElementById("doc-caption");
        if (!el) return;
        el.textContent = text ?? "";
        el.classList.toggle("on", Boolean(text));
      }, text);
      if (hold) await page.waitForTimeout(hold);
    },
    pause: (ms) => page.waitForTimeout(ms),
    moveTo: async (x, y) => {
      const distance = Math.hypot(x - pointer.x, y - pointer.y);
      await page.mouse.move(x, y, { steps: Math.max(8, Math.round(distance / 14)) });
      pointer = { x, y };
      await page.waitForTimeout(180);
    },
    clickAt: async (x, y, button = "left") => {
      await h.moveTo(x, y);
      await page.mouse.click(x, y, { button });
      await page.waitForTimeout(350);
    },
    click: async (locator, button = "left") => {
      const target = typeof locator === "string" ? page.locator(locator).first() : locator;
      await target.scrollIntoViewIfNeeded();
      const box = await target.boundingBox();
      if (!box) throw new Error(`${name}: nothing to click for ${locator}`);
      await h.clickAt(box.x + box.width / 2, box.y + box.height / 2, button);
    },
    hover: async (locator) => {
      const box = await page.locator(locator).first().boundingBox();
      await h.moveTo(box.x + box.width / 2, box.y + box.height / 2);
    },
    type: async (locator, text) => {
      await h.click(locator);
      await page.locator(locator).first().pressSequentially(text, { delay: 110 });
    },
    /** Click a drop zone and answer the file chooser it opens. */
    chooseFile: async (locator, file) => {
      const box = await page.locator(locator).first().boundingBox();
      await h.moveTo(box.x + box.width / 2, box.y + box.height / 2);
      const [chooser] = await Promise.all([
        page.waitForEvent("filechooser"),
        page.mouse.click(box.x + box.width / 2, box.y + box.height / 2),
      ]);
      await chooser.setFiles(file);
      await page.waitForTimeout(500);
    },
    /** From here to `fastEnd`, the MP4 plays `speed` times faster. */
    fastStart: () => marks.fast.push({ from: now(), to: null }),
    fastEnd: () => {
      marks.fast[marks.fast.length - 1].to = now();
    },
    /** This moment, without the caption, is the still the guide shows. */
    poster: async () => {
      await page.evaluate(() => document.getElementById("doc-caption")?.classList.remove("on"));
      await page.waitForTimeout(300);
      marks.poster = await page.screenshot();
      await page.evaluate(() => {
        const el = document.getElementById("doc-caption");
        if (el?.textContent) el.classList.add("on");
      });
    },
    ...comparisonHelpers(page, () => h),
  };

  try {
    await scenario(h);
    await h.caption(null);
    await page.waitForTimeout(800);
  } finally {
    const video = page.video();
    await context.close();
    const webm = await video.path();
    encode(webm, join(VIDEOS, `${name}.mp4`), marks.start, marks.fast, now());
    if (marks.poster) still(marks.poster, join(VIDEOS, `${name}.png`));
    console.log(`  ${name}  ${now().toFixed(0)} s recorded`);
  }
}

/**
 * WebM → H.264 MP4: drop the page load before `start`, and play the marked
 * waits 8x faster. Small files on purpose — they live in the repository.
 */
function encode(webm, mp4, start, fast, end) {
  const SPEED = 8;
  const parts = [];
  let at = start;
  for (const { from, to } of fast) {
    if (from > at) parts.push({ from: at, to: from, speed: 1 });
    parts.push({ from, to, speed: SPEED });
    at = to;
  }
  parts.push({ from: at, to: end + 1, speed: 1 });
  const filters = parts
    .map(
      ({ from, to, speed }, i) =>
        `[0:v]trim=start=${from.toFixed(3)}:end=${to.toFixed(3)},setpts=(PTS-STARTPTS)/${speed}[p${i}]`,
    )
    .join(";");
  const concat = `${parts.map((_, i) => `[p${i}]`).join("")}concat=n=${parts.length}:v=1:a=0,fps=25[out]`;
  execFileSync(
    "ffmpeg",
    [
      "-y", "-loglevel", "error", "-i", webm,
      "-filter_complex", `${filters};${concat}`, "-map", "[out]",
      "-c:v", "libx264", "-preset", "slow", "-crf", "26", "-pix_fmt", "yuv420p",
      "-movflags", "+faststart", "-an", mp4,
    ],
    { stdio: "inherit" },
  );
}

/** The still: the screenshot with a play button over it, so it reads as a video. */
function still(png, out) {
  const source = join(scratch, "poster-source.png");
  writeFileSync(source, png);
  const play =
    "drawbox=x=(iw-120)/2:y=(ih-120)/2:w=120:h=120:color=black@0.55:t=fill," +
    // A triangle, from three thin boxes would be crude; a geq mask draws it exactly.
    "geq=r='if(between(X-(W/2-22),0,48)*lte(abs(Y-H/2),24-(X-(W/2-22))/2),255,r(X,Y))':" +
    "g='if(between(X-(W/2-22),0,48)*lte(abs(Y-H/2),24-(X-(W/2-22))/2),255,g(X,Y))':" +
    "b='if(between(X-(W/2-22),0,48)*lte(abs(Y-H/2),24-(X-(W/2-22))/2),255,b(X,Y))'";
  execFileSync("ffmpeg", ["-y", "-loglevel", "error", "-i", source, "-vf", play, out], { stdio: "inherit" });
}

// --- the comparison page --------------------------------------------------

/** A View options entry by how its label starts: "Branch lengths" also appears in Phylogram's note. */
const viewItem = (page, name) =>
  page.locator(".app-bar .picker-menu label").filter({ hasText: new RegExp(`^${name}`) });

function comparisonHelpers(page, self) {
  const seam = (fn, arg) => page.evaluate(fn, arg);
  return {
    openComparison: async (pair = PAIR, hash = "") => {
      await page.goto(`${WEB}/#/c/${pair}${hash}`);
      await self().settle();
    },
    /** Both panels drawn and nothing loading. */
    settle: async () => {
      await page.waitForTimeout(200);
      await page.waitForFunction(
        () => window.__phylodelta?.drawn && window.__phylodelta.state().every((s) => s.tree && !s.loading),
        null,
        { timeout: 60_000 },
      );
      await page.waitForTimeout(500);
    },
    drawn: (side) => seam((side) => window.__phylodelta.drawn(side), side),
    /** A panel's drawing area. */
    panelBox: (side) => page.locator(".sigma-host").nth(side).boundingBox(),
    /** A point in the panel with nothing drawn near it: where "empty space" is. */
    emptyPoint: async (side) => {
      const box = await self().panelBox(side);
      const nodes = await self().drawn(side);
      let best = null;
      for (let gx = 0.12; gx <= 0.88; gx += 0.04) {
        for (let gy = 0.15; gy <= 0.7; gy += 0.04) {
          const x = box.x + box.width * gx;
          const y = box.y + box.height * gy;
          const clear = Math.min(...nodes.map((n) => Math.hypot(n.x - x, n.y - y)));
          if (!best || clear > best.clear) best = { x, y, clear };
        }
      }
      return best;
    },
    /** Right-click a drawn node, then choose `item` from the menu. */
    menuOnNode: async (node, item) => {
      await self().clickAt(node.x, node.y, "right");
      await page.waitForSelector(".context-menu");
      await page.waitForTimeout(700);
      if (item) await self().click(page.locator(".context-menu-item", { hasText: item }));
    },
    menuOnEmpty: async (side, item) => {
      const at = await self().emptyPoint(side);
      await self().clickAt(at.x, at.y, "right");
      await page.waitForSelector(".context-menu");
      await page.waitForTimeout(700);
      if (item) await self().click(page.locator(".context-menu-item", { hasText: item }));
    },
    /** Drawn nodes with their leaf counts, from the slice the panel is showing. */
    sized: async (side) => {
      const counts = await page.evaluate((side) => {
        const slice = window.__phylodelta.state()[side].slice;
        return Object.fromEntries(slice.nodes.id.map((id, k) => [id, slice.nodes.true_leaf_count[k]]));
      }, side);
      return (await self().drawn(side)).map((n) => ({ ...n, leaves: counts[n.storedId] ?? 0 }));
    },
    /** A triangle holding between `min` and `max` leaves, nearest the middle of the panel. */
    wedgeOfSize: async (side, min, max) => {
      const box = await self().panelBox(side);
      const mid = box.y + box.height * 0.5;
      const fits = (await self().sized(side)).filter((n) => n.collapsed && n.leaves >= min && n.leaves <= max);
      return fits.sort((a, b) => Math.abs(a.y - mid) - Math.abs(b.y - mid))[0];
    },
    /** A branch point with between `min` and `max` leaves under it. */
    internalOfSize: async (side, min, max) => {
      const box = await self().panelBox(side);
      const mid = box.y + box.height * 0.5;
      const root = await page.evaluate((side) => window.__phylodelta.state()[side].slice.root, side);
      const fits = (await self().sized(side)).filter(
        (n) => !n.leaf && !n.collapsed && n.storedId !== root && n.leaves >= min && n.leaves <= max,
      );
      if (!fits.length) throw new Error("no branch point of that size on screen");
      return fits.sort((a, b) => Math.abs(a.y - mid) - Math.abs(b.y - mid))[0];
    },
    /** The collapsed clade nearest the middle of a panel. */
    middleWedge: async (side) => {
      const box = await self().panelBox(side);
      const mid = box.y + box.height * 0.45;
      const wedges = (await self().drawn(side)).filter((n) => n.collapsed);
      return wedges.sort((a, b) => Math.abs(a.y - mid) - Math.abs(b.y - mid))[0];
    },
    viewMenu: async (item) => {
      await self().click(".app-bar .picker-button");
      await page.waitForTimeout(500);
      if (item) await self().click(viewItem(page, item));
    },
  };
}

// --- the scenarios: one per section of docs/web-app-guide.md ---------------

const browser = await launch();
console.log(`recording against ${WEB} into ${VIDEOS}`);

await record(browser, "01-upload", async (h) => {
  const { page } = h;
  await page.goto(WEB);
  await page.waitForSelector(".upload");
  await h.pause(600);
  h.begin();
  await h.caption("Choose the two trees to compare — Newick files", 1600);
  await h.chooseFile(".drop-row >> nth=0 >> [role=button] >> nth=0", join(DATASETS, "gen_trees", "vibrio-nj-tree.nwk"));
  await h.chooseFile(".drop-row >> nth=0 >> [role=button] >> nth=1", join(DATASETS, "gen_trees", "vibrio-upgma-tree.nwk"));
  await h.caption("Optional: the isolate data behind the leaves, one table for both trees", 1400);
  await h.chooseFile(".typing [role=button]", join(DATASETS, "isolated_data", "vibrio.tsv"));
  await h.caption("Optional: a name, and the species of each tree", 600);
  await h.type(".fields label:has-text('Name') input", "Vibrio: NJ vs UPGMA");
  await h.type(".fields label:has-text('Left species') input", "vibrio");
  await h.type(".fields label:has-text('Right species') input", "vibrio");
  await h.caption("Choose the metric. The line below says where its computation comes from", 600);
  await h.hover(".upload-metric select");
  await h.pause(2200);
  await h.poster();
  await h.caption("Upload and compare", 500);
  await h.click(".upload button.primary");
  await page.waitForSelector(".upload-status");
  await h.caption("The server computes the comparison in the background (sped up 8×)");
  h.fastStart();
  await page.waitForFunction(() => window.__phylodelta?.state?.().every((s) => s.tree && !s.loading), null, {
    timeout: 600_000,
  });
  h.fastEnd();
  await h.caption("When it is ready, the comparison opens", 3500);
});

await record(browser, "02-open-comparison", async (h) => {
  const { page } = h;
  await page.goto(WEB);
  await page.waitForSelector(".pair-list");
  await h.pause(600);
  h.begin();
  await h.caption("Your comparisons: every comparison you have, with its shared leaves and metrics", 2200);
  await h.hover(".pair-list li >> nth=0");
  await h.pause(800);
  await h.poster();
  await h.caption("Click one to open it", 600);
  await h.click(page.locator(".pair", { hasText: "vibrio-nj vs vibrio-upgma" }));
  await h.settle();
  await h.caption("The address names what is on screen: bookmark it or share it", 3000);
  await h.caption("← Back returns to the list", 600);
  await h.click(page.locator(".back-button", { hasText: "Back" }));
  await page.waitForSelector(".pair-list");
  await h.pause(1500);
});

await record(browser, "03-navigate", async (h) => {
  const { page } = h;
  await h.openComparison();
  h.begin();
  await h.caption("Scroll to zoom, drag to move", 400);
  const box = await h.panelBox(0);
  const cx = box.x + box.width * 0.6;
  const cy = box.y + box.height * 0.45;
  await h.moveTo(cx, cy);
  for (let i = 0; i < 3; i++) {
    await page.mouse.wheel(0, -100);
    await h.pause(250);
  }
  await h.pause(500);
  await page.mouse.down();
  await h.moveTo(cx + 50, cy + 70);
  await page.mouse.up();
  await h.pause(700);
  for (let i = 0; i < 3; i++) {
    await page.mouse.wheel(0, 100);
    await h.pause(250);
  }
  await h.pause(900);

  await h.caption("Triangles are collapsed clades. Right-click one → Expand this clade", 400);
  await h.menuOnNode(await h.wedgeOfSize(0, 150, 1500), null);
  await h.pause(900);
  await h.poster();
  await h.click(page.locator(".context-menu-item", { hasText: "Expand this clade" }));
  await h.settle();
  await h.caption("The panel now shows that clade alone, in more detail", 2600);

  await h.caption("Click a node to select it, then right-click anywhere in the panel to act on it", 400);
  const branch = await h.internalOfSize(0, 10, 1000);
  await h.clickAt(branch.x, branch.y);
  await h.pause(1400);
  await h.menuOnEmpty(0, "Focus this subtree");
  await h.settle();
  await h.pause(1800);
  // While a node is selected, a right-click anywhere is about that node; a
  // click on empty space lets go of it, and the menu is about the view again.
  const clear = await h.emptyPoint(0);
  await h.clickAt(clear.x, clear.y);

  await h.caption("Right-click empty space → Collapse all folds it to its outline", 400);
  await h.menuOnEmpty(0, "Collapse all");
  await h.settle();
  await h.pause(1500);
  await h.caption("Expand all draws every leaf of what is on screen", 400);
  await h.menuOnEmpty(0, "Expand all");
  await h.settle();
  await h.pause(2000);
  await h.caption("Go back: one level out", 400);
  await h.menuOnEmpty(0, "Go back");
  await h.settle();
  await h.pause(1400);
  await h.caption("Reset to the whole tree", 400);
  await h.menuOnEmpty(0, "Reset to the whole tree");
  await h.settle();
  await h.pause(1500);
});

await record(browser, "04-search", async (h) => {
  const { page } = h;
  await h.openComparison();
  h.begin();
  await h.caption("Type a leaf's name in the search box", 400);
  await h.type(".search-input", "1203");
  await page.waitForSelector(".search-row");
  await h.caption("The exact name first, then names starting with it; ✓ / ✗ for each tree", 1800);
  await h.hover(".search-row >> nth=0");
  await h.pause(600);
  await h.click(".search-row >> nth=0");
  await h.settle();
  await h.caption("Each panel with the leaf moves to it and marks it", 3000);
  await h.poster();
  await h.caption("Try a name only one tree has: the other panel stays and says so", 400);
  await page.fill(".search-input", "");
  await h.type(".search-input", "211");
  await page.waitForSelector(".search-row");
  await h.pause(900);
  const row = page.locator(".search-row").filter({ hasText: /^\s*211\b/ }).first();
  await h.click((await row.count()) ? row : page.locator(".search-row").first());
  await h.settle();
  await h.pause(3200);
});

await record(browser, "05-find-in-other-tree", async (h) => {
  const { page } = h;
  await h.openComparison();
  h.begin();
  await h.caption("Right-click a leaf → Find this leaf in the other tree", 400);
  const leaves = (await h.drawn(0)).filter((n) => n.leaf);
  const leaf = leaves[Math.floor(leaves.length / 2)];
  await h.menuOnNode(leaf, "Find this leaf in the other tree");
  await h.settle();
  await h.caption("The other panel moves to the same leaf, with its surroundings, and marks it", 3200);
  await h.poster();
  await h.caption("The chip above the panel names it. × or Esc clears the mark", 400);
  await h.hover(".found-clear");
  await h.pause(1200);
  await h.click(".found-clear");
  await h.pause(1500);
});

await record(browser, "06-view-options", async (h) => {
  const { page } = h;
  await h.openComparison();
  await h.captionSide("left");
  h.begin();
  await h.caption("View options holds every display setting", 400);
  await h.viewMenu("Clade sizes");
  await h.pause(1500);
  await h.poster();
  await h.caption("Branch lengths: each branch's length, where there is room", 400);
  await h.click(viewItem(page, "Branch lengths"));
  await h.pause(1600);
  await h.caption("Phylogram: branches drawn to their length", 400);
  await h.click(viewItem(page, "Phylogram"));
  await h.settle();
  await h.pause(1500);
  await h.caption("Logarithmic scale: a few long branches no longer squash the rest", 400);
  await h.click(viewItem(page, "Logarithmic"));
  await h.settle();
  await h.pause(1800);
  await h.caption("Colour the divergence on the clades instead of the branches", 400);
  await h.click(viewItem(page, "Clades"));
  await h.pause(1800);
  await page.keyboard.press("Escape");
  await h.clickAt(420, 24);
  await h.pause(2200);
});

await record(browser, "07-isolate-data", async (h) => {
  const { page } = h;
  await h.openComparison();
  h.begin();
  await h.caption("View options → Isolate data: a bar of isolates on each leaf", 400);
  await h.viewMenu("Isolate data");
  await page.keyboard.press("Escape");
  await h.clickAt(420, 24);
  await page.waitForSelector(".legend-swatches .swatch");
  await h.pause(2000);
  await h.caption("Colour by: which column of the table splits the bars", 400);
  await h.click(".typing-legend .picker-button");
  await h.pause(600);
  await h.click(page.locator(".typing-legend .picker-menu label", { hasText: "Continent" }));
  await h.click(page.locator(".typing-legend .picker-menu label", { hasText: "Source Niche" }));
  await h.pause(900);
  await page.keyboard.press("Escape");
  await h.clickAt(420, 24);
  await h.pause(1800);
  await h.poster();
  await h.caption("Bar length: logarithmic by default, or linear", 400);
  const scale = page.locator(".legend-scale select");
  await h.hover(".legend-scale select");
  await scale.selectOption({ label: "Linear" });
  await h.pause(1800);
  await scale.selectOption({ label: "Logarithmic" });
  await h.pause(900);
  await h.caption("Click a colour square to choose a new colour", 400);
  const swatch = page.locator(".swatch-pick").nth(1);
  await h.click(swatch);
  // The browser's own colour picker is not drawn in a recording; choose as it would.
  await swatch.locator("input").evaluate((input) => {
    input.value = "#000000";
    input.dispatchEvent(new Event("change", { bubbles: true }));
  });
  await h.pause(1800);
  await h.caption("Reset colours restores them", 400);
  await h.click(".legend-reset");
  await h.pause(1800);
});

await record(browser, "08-export", async (h) => {
  const { page } = h;
  await h.openComparison();
  h.begin();
  await h.caption("Export: a report with the scores, what the colours mean and both trees", 400);
  await h.click(page.locator(".back-button", { hasText: "Export" }));
  await page.waitForSelector(".export-panel");
  await h.pause(1500);
  await h.poster();
  await h.caption("Choose HTML, PDF or PNG", 400);
  await h.click(page.locator(".export-formats label", { hasText: "PDF" }));
  await h.pause(900);
  await h.hover(".export-panel label:has-text('Include the two trees')");
  await h.pause(1400);
  await h.caption("The file downloads", 400);
  const [download] = await Promise.all([
    page.waitForEvent("download", { timeout: 120_000 }),
    h.click(page.locator(".export-actions button", { hasText: "Export report" })),
  ]);
  await download.path();
  await h.pause(1500);
});

await record(browser, "09-remove", async (h) => {
  const { page } = h;
  await page.goto(WEB);
  await page.waitForSelector(".pair-list");
  await h.pause(600);
  h.begin();
  await h.caption("× removes a comparison, with the data only it was using", 400);
  const item = page.locator(".pair-list li", { hasText: "Vibrio: NJ vs UPGMA" });
  await h.click(item.locator(".pair-remove"));
  await page.waitForSelector(".notice");
  await h.caption("It asks first: this cannot be undone", 1800);
  await h.poster();
  await h.click(".notice .primary.danger");
  await item.waitFor({ state: "detached", timeout: 30_000 });
  await h.caption(null);
  await h.pause(2000);
});

// --- the annotated screenshot for docs/reading-a-comparison.md ------------

if (!ONLY || ONLY.includes("annotated")) {
  const page = await browser.newPage({ viewport: SIZE, deviceScaleFactor: 2 });
  await page.goto(`${WEB}/#/c/${PAIR}`);
  await page.waitForFunction(
    () => window.__phylodelta?.drawn && window.__phylodelta.state().every((s) => s.tree && !s.loading),
    null,
    { timeout: 60_000 },
  );
  // Isolate bars on, and a leaf found in the right tree from the left one, so
  // the left panel keeps the whole tree's triangles while the right shows a
  // marked leaf: every kind of mark on screen at once.
  await page.click(".app-bar .picker-button");
  await page.click(".app-bar .picker-menu label:has-text('Isolate data')");
  await page.keyboard.press("Escape");
  await page.mouse.click(420, 24);
  await page.waitForTimeout(800);
  const leaves = (await page.evaluate(() => window.__phylodelta.drawn(0))).filter((n) => n.leaf);
  const from = leaves[Math.floor(leaves.length / 2)];
  await page.mouse.click(from.x, from.y, { button: "right" });
  await page.click(".context-menu-item:has-text('Find this leaf in the other tree')");
  await page.waitForTimeout(600);
  await page.waitForFunction(() => window.__phylodelta.state().every((s) => !s.loading));
  await page.waitForSelector(".legend-swatches .swatch");
  await page.waitForTimeout(3000);

  const targets = await page.evaluate(() => {
    const rect = (selector, index = 0) => {
      const r = document.querySelectorAll(selector)[index]?.getBoundingClientRect();
      return r ? { x: r.left, y: r.top, w: r.width, h: r.height } : null;
    };
    const hostBox = document.querySelectorAll(".sigma-host")[0].getBoundingClientRect();
    const nearest = (nodes, at) =>
      [...nodes].sort(
        (a, b) =>
          Math.abs(a.y - (hostBox.top + hostBox.height * at)) - Math.abs(b.y - (hostBox.top + hostBox.height * at)),
      )[0];
    // The overlay drawn for a triangle: the smallest element just inside its
    // tip (left panel, so it opens to the right). Searched by position, since
    // the overlays take no pointer events and elementsFromPoint skips them.
    const boxOf = (panel, w) => {
      const r = [...panel.querySelectorAll("div, svg")]
        .map((el) => el.getBoundingClientRect())
        .filter(
          (r) =>
            r.width > 2 && r.width < 80 && r.height < 80 &&
            r.left <= w.x + 4 && r.right >= w.x + 4 && r.top <= w.y && r.bottom >= w.y,
        )
        .sort((a, b) => a.width * a.height - b.width * b.height)[0];
      return r ? { x: r.left, y: r.top, w: r.width, h: r.height } : null;
    };
    const right = window.__phylodelta.drawn(1);
    const left = window.__phylodelta.drawn(0);
    const marked = window.__phylodelta.marks()[1].storedId;
    return {
      score: rect(".app-bar .headline"),
      search: rect(".search-input"),
      // The text, not its full-width line, so the label lands inside the left panel.
      header: (() => {
        const range = document.createRange();
        range.selectNodeContents(document.querySelector(".side-counts"));
        const r = range.getBoundingClientRect();
        return { x: r.left, y: r.top, w: r.width, h: r.height };
      })(),
      chip: rect(".found-chip", 1) ?? rect(".found-chip", 0),
      // The library's legend box has no class: the smallest element in the
      // left panel that holds both ends of the scale.
      legend: (() => {
        const host = document.querySelectorAll(".panel")[0];
        const boxes = [...host.querySelectorAll("div")].filter(
          (el) => /Identical/.test(el.textContent) && /Not in the other tree/.test(el.textContent),
        );
        const r = boxes.at(-1)?.getBoundingClientRect();
        return r ? { x: r.left, y: r.top, w: r.width, h: r.height } : null;
      })(),
      typing: (() => {
        const r = rect(".typing-legend");
        return r && { x: r.x + 8, y: r.y + 6, w: r.w - 16, h: r.h - 12 };
      })(),
      // A triangle and a leaf well apart, in the body of the tree.
      wedge: nearest(left.filter((n) => n.collapsed), 0.42),
      // The largest triangle in the left panel, ringed by its own outline.
      wedgeBox: (() => {
        const panel = document.querySelectorAll(".panel")[0];
        const boxes = left.filter((n) => n.collapsed).map((w) => boxOf(panel, w)).filter(Boolean);
        return boxes.sort((a, b) => b.h - a.h)[0] ?? null;
      })(),
      leaf: nearest(left.filter((n) => n.leaf), 0.62),
      found: right.find((n) => n.storedId === marked) ?? null,
      hostL: rect(".sigma-host", 0),
    };
  });
  console.log("  annotated targets", JSON.stringify(targets));
  await page.evaluate((t) => {
    const layer = document.createElement("div");
    layer.style.cssText = "position:fixed;inset:0;z-index:2147483647;pointer-events:none;";
    document.body.appendChild(layer);
    const label = (n, x, y) => {
      const el = document.createElement("div");
      el.textContent = String(n);
      // Kept inside the picture: a number half off the edge is no help.
      x = Math.min(Math.max(x, 18), innerWidth - 18);
      y = Math.min(Math.max(y, 18), innerHeight - 18);
      el.style.cssText =
        `position:fixed;left:${x - 13}px;top:${y - 13}px;width:26px;height:26px;border-radius:50%;` +
        "background:#d9480f;color:#fff;font:700 15px/26px system-ui,sans-serif;text-align:center;" +
        "box-shadow:0 0 0 3px #fff,0 2px 6px rgba(0,0,0,.35);";
      layer.appendChild(el);
    };
    const ring = (x, y, w, h) => {
      const el = document.createElement("div");
      el.style.cssText =
        `position:fixed;left:${x - 4}px;top:${y - 4}px;width:${w + 8}px;height:${h + 8}px;` +
        "border:2.5px solid #d9480f;border-radius:8px;";
      layer.appendChild(el);
    };
    const boxed = (n, r, side = "left") => {
      if (!r) return;
      ring(r.x, r.y, r.w, r.h);
      // Beside the box, clear of the text it rings.
      label(n, side === "left" ? r.x - 22 : r.x + r.w + 22, r.y + r.h / 2);
    };
    const point = (n, p, dx = -22, dy = -18) => {
      if (!p) return;
      ring(p.x - 9, p.y - 9, 18, 18);
      label(n, p.x + dx, p.y + dy);
    };
    boxed(1, t.score);
    boxed(2, t.header, "right");
    boxed(3, t.chip, "right");
    point(4, t.found, 24, -18);
    // The triangle's own outline, not its anchor: the anchor is where the
    // triangle starts, and a ring round it misses the shape it points at.
    if (t.wedgeBox) {
      ring(t.wedgeBox.x, t.wedgeBox.y, t.wedgeBox.w, t.wedgeBox.h);
      // Above it: to the right are the leaf names.
      label(5, t.wedgeBox.x + t.wedgeBox.w / 2, t.wedgeBox.y - 22);
    } else point(5, t.wedge, 30, 0);
    point(6, t.leaf, -30, 0);
    boxed(7, t.legend, "right");
    if (t.typing) {
      ring(t.typing.x, t.typing.y, t.typing.w, t.typing.h);
      label(8, t.typing.x + t.typing.w - 30, t.typing.y + t.typing.h / 2);
    }
  }, targets);
  await page.waitForTimeout(300);
  await page.screenshot({ path: join(IMAGES, "comparison-annotated.png") });
  await page.close();
  console.log("  comparison-annotated.png");
}

await browser.close();
rmSync(scratch, { recursive: true, force: true });

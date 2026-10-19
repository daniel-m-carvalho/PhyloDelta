/**
 * Does anything on screen make the page resize itself? (§39)
 *
 *   node harness/check_layout_stability.mjs [comparison id] [web url]
 *
 * Needs the web app and an API with that comparison. Exits non-zero on any
 * failure, so it can gate a change to the layout, the panels or the library's
 * overlays.
 *
 * **Why it exists.** On Windows the app trembled: zooming the right panel, or
 * switching the typing data on, flipped the layout every frame. Sigma sized
 * its canvases in whole pixels, so a 639.5px panel got 640px canvases and the
 * right panel's half pixel landed past the window. Half a pixel of overflow is
 * a 17px scrollbar on Windows; the scrollbar narrowed the panels until the
 * overflow went away, the scrollbar left, and round again.
 *
 * **Why it looks like Windows.** On a Mac, scrollbars float over the content
 * and take no space, so the loop cannot happen there and nobody developing on
 * one would ever see it. Two things make Chrome behave like Windows here:
 * Playwright's default `--hide-scrollbars` is dropped, and the overlay
 * scrollbar feature is disabled — measured: a scrolling div then reports a
 * 15px scrollbar, against 0px with either left in place.
 *
 * **What counts as a failure.** A frame where the page's usable width or
 * height changed (a flip), or where the page has a scrollbar at all. The app
 * is one window-sized layout; the page itself should never scroll.
 */

import { chromium } from "playwright";

const PAIR = process.argv[2] ?? "vibrio-nj__vibrio-upgma";
const WEB = process.argv[3] ?? "http://localhost:5173";
// Even and odd widths: the half-pixel only exists where (width - gap) / 2 is
// fractional, so an odd width can pass while an even one fails. 1281 did.
const WIDTHS = [1280, 1281, 1366, 1600];

const browser = await chromium.launch({
  channel: "chrome",
  headless: true,
  ignoreDefaultArgs: ["--hide-scrollbars"],
  args: ["--disable-features=OverlayScrollbar"],
});

const failures = [];
const rows = [];

for (const width of WIDTHS) {
  const page = await browser.newPage({ viewport: { width, height: 680 } });
  await page.goto(`${WEB}/#/c/${PAIR}`);
  await page.waitForFunction(
    () => window.__phylodelta && window.__phylodelta.state().every((s) => s.tree && !s.loading),
    null,
    { timeout: 30_000 },
  );
  await page.waitForTimeout(800);

  const scrollbarWidth = await page.evaluate(() => {
    const probe = document.createElement("div");
    probe.style.cssText = "position:absolute;top:-999px;width:100px;height:100px;overflow:scroll";
    document.body.appendChild(probe);
    const w = probe.offsetWidth - probe.clientWidth;
    probe.remove();
    return w;
  });
  if (scrollbarWidth === 0) {
    // Without space-taking scrollbars this check proves nothing; say so
    // rather than pass.
    console.error("scrollbars take no space in this browser — the check cannot run");
    process.exit(2);
  }

  await page.evaluate(() => {
    window.__flips = 0;
    window.__barred = 0;
    let last = null;
    const tick = () => {
      const d = document.documentElement;
      const now = `${d.clientWidth}x${d.clientHeight}`;
      if (last && now !== last) window.__flips++;
      if (window.innerWidth !== d.clientWidth || window.innerHeight !== d.clientHeight) window.__barred++;
      last = now;
      requestAnimationFrame(tick);
    };
    requestAnimationFrame(tick);
  });

  const check = async (what, act) => {
    await page.evaluate(() => {
      window.__flips = 0;
      window.__barred = 0;
    });
    await act();
    const { flips, barred } = await page.evaluate(() => ({
      flips: window.__flips,
      barred: window.__barred,
    }));
    const ok = flips === 0 && barred === 0;
    rows.push(`${ok ? "ok  " : "FAIL"} ${String(width).padStart(4)}px  ${what.padEnd(20)} flips ${flips}, frames with a page scrollbar ${barred}`);
    if (!ok) failures.push(`${width}px ${what}`);
  };

  const zoom = async (x, y) => {
    await page.mouse.move(x, y);
    for (let k = 0; k < 8; k++) {
      await page.mouse.wheel(0, -250);
      await page.waitForTimeout(120);
    }
    await page.waitForTimeout(1500);
  };
  const hoverColumn = async (x) => {
    for (let y = 200; y < 600; y += 8) {
      await page.mouse.move(x, y);
      await page.waitForTimeout(15);
    }
    await page.waitForTimeout(500);
  };

  await check("typing data on", async () => {
    await page.click("text=View options");
    await page.waitForTimeout(200);
    await page.click("text=Isolate data");
    await page.keyboard.press("Escape");
    await page.waitForTimeout(2000);
  });
  await check("zoom right panel", () => zoom(width - 150, 420));
  await check("zoom left panel", () => zoom(150, 420));
  await check("hover right edge", () => hoverColumn(width - 40));
  // Resized first and measured after: the resizes themselves change the
  // page's width, legitimately. What must not happen is the layout going on
  // changing once the window has stopped.
  for (const w of [width - 1, width - 17, width + 3, width]) {
    await page.setViewportSize({ width: w, height: 680 });
    await page.waitForTimeout(400);
  }
  await check("after window resizes", () => page.waitForTimeout(1500));
  await page.close();
}

await browser.close();
console.log(rows.join("\n"));
if (failures.length) {
  console.error(`\n${failures.length} unstable: ${failures.join("; ")}`);
  process.exit(1);
}
console.log("\nstable: no flips, no page scrollbar");

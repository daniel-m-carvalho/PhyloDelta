/**
 * One browser, configured once, for every runner.
 *
 * **System Chrome, not Playwright's bundled Chromium.** The claim is about
 * what a user's browser does, and pinning the real Chrome the examiner could
 * install makes the result reproducible in the ordinary sense rather than the
 * "if you have this exact build artefact" sense. Its version is recorded with
 * every result.
 *
 * `--js-flags=--expose-gc` is not used: memory is read through CDP's
 * `HeapProfiler.collectGarbage`, which needs no flag and does not change how
 * the page under test behaves.
 */
import { chromium } from "playwright";

export async function launch({ headless = true } = {}) {
  return chromium.launch({
    channel: "chrome",
    headless,
    args: [
      // The default heap cap makes "it ran out of memory" a property of the
      // flag rather than of the tool. Raised for BOTH tools equally, so a
      // failure is the tool's own ceiling.
      "--js-flags=--max-old-space-size=8192",
      "--disable-dev-shm-usage",
    ],
  });
}

/**
 * One attempt with a real end: past `ms` its browsers are closed, not left behind.
 *
 * A bare `Promise.race` against a timer abandons the work instead of stopping
 * it. The attempt's own `finally` only runs once the page call returns, and a
 * page busy for an hour never returns, so `ceiling.mjs` left a renderer working
 * through the next measurement and then never exited (§34.21).
 *
 * `fn` is handed a launcher in place of `launch`, so the deadline knows what to
 * close. Its own `finally` stays as it is: closing twice does nothing.
 */
export async function withDeadline(fn, ms, label) {
  const launched = [];
  const owned = async () => {
    const browser = await launch();
    launched.push(browser);
    return browser;
  };
  let timer;
  try {
    return await Promise.race([
      fn(owned),
      new Promise((_, reject) => {
        timer = setTimeout(() => reject(new Error(`${label} exceeded ${ms / 1000}s`)), ms);
      }),
    ]);
  } catch (failed) {
    await Promise.all(launched.map(closeWithin));
    throw failed;
  } finally {
    clearTimeout(timer);
  }
}

/** Closing a renderer that is stuck must not become the next thing to hang. */
function closeWithin(browser) {
  let timer;
  return Promise.race([
    browser.close().catch(() => {}),
    new Promise((resolve) => {
      timer = setTimeout(resolve, 30_000);
    }),
  ]).finally(() => clearTimeout(timer));
}

export function versionOf(browser) {
  return `Chrome ${browser.version()}`;
}

/**
 * Static server for the benchmark. Serves three roots under one origin so both
 * tools fetch trees from the same place and neither gets a cross-origin penalty
 * the other avoids:
 *
 *   /phyloio/dist/...  phylo.io's prebuilt bundle (upstream, untouched)
 *   /harness/...       our driver pages
 *   /trees/...         the generated tree ladder
 *
 * No compression: gzip would measure the server, not the browser, and the two
 * tools must be compared on identical transport.
 */
import { createServer, request as httpRequest } from "node:http";
import { createGzip } from "node:zlib";
import { createReadStream, statSync } from "node:fs";
import { extname, join, normalize } from "node:path";
import { fileURLToPath } from "node:url";

const here = fileURLToPath(new URL(".", import.meta.url));
const BENCH = join(here, "..");
const PHYLOIO = "/Users/danielcarvalho/Documents/masters/Theses/examples/tools/phylo-io";

const ROOTS = {
  "/phyloio/": PHYLOIO,
  "/harness/": join(BENCH, "harness"),
  "/trees/": join(BENCH, "trees"),
};

// Everything not matching a prefix falls through to the thesis frontend's
// production build. It is served at the ORIGIN ROOT on purpose: its
// index.html references /assets/... absolutely, so a subpath would 404 it.
// The benchmark measures the shipping build, not the dev server.
//
// (This was `lib_demo/dist` while that was the only frontend. lib_demo is
// frozen and loads whole trees from static files — comparing *it* against
// phylo.io is the mistake recorded under Corrections.)
const WEB = join(BENCH, "..", "web", "dist");

//: Where /api/v1/... goes. The frontend fetches it relatively, so the
//: benchmark origin has to carry it: serving the app from one origin and the
//: API from another would add a preflight to every request on one side of the
//: comparison and not the other.
const API_PORT = Number(process.env.PHYLODELTA_BENCH_API_PORT ?? 8010);

/*
 * Compression is OFF by default, and that default is a measurement decision.
 *
 * Every figure in the results was taken uncompressed, so that both tools face
 * identical transport and neither benefits from a server setting the other did
 * not get. Turning it on globally would silently re-baseline every re-run.
 *
 * `BENCH_GZIP=1` turns it on for one run, which is how the compressed column in
 * the transfer table is produced — the same two tools, the same request paths,
 * the same compression level, differing only in this. Both tools get it or
 * neither does.
 */
const GZIP = process.env.BENCH_GZIP === "1";

//: Only what a real server would compress. Compressing an already-compressed
//: image would cost CPU to make the payload slightly larger, and a server that
//: did it would be misconfigured — so measuring it would measure a strawman.
const COMPRESSIBLE = new Set([
  ".html", ".js", ".mjs", ".css", ".json", ".nwk", ".tsv", ".map",
]);

function accepts(req) {
  return /\bgzip\b/.test(req.headers["accept-encoding"] ?? "");
}

const TYPES = {
  ".html": "text/html", ".js": "text/javascript", ".mjs": "text/javascript",
  ".css": "text/css", ".json": "application/json", ".nwk": "text/plain",
  ".tsv": "text/tab-separated-values", ".map": "application/json",
};

export function start(port = 8099) {
  const server = createServer((req, res) => {
    const raw = req.url || "/";
    if (raw.startsWith("/api/")) {
      const upstream = httpRequest(
        { host: "127.0.0.1", port: API_PORT, path: raw, method: req.method, headers: req.headers },
        (answer) => {
          /*
           * The API is compressed HERE, not by FastAPI, which ships no
           * GZipMiddleware.
           *
           * Without this, `BENCH_GZIP=1` would compress phylo.io's Newick and
           * leave this frontend's JSON uncompressed — measuring a transport
           * difference and reporting it as a design difference. That is the
           * asymmetry the whole comparison is written to avoid, and it would
           * have moved the number in our own favour.
           */
          const type = String(answer.headers["content-type"] ?? "");
          const compress =
            GZIP &&
            accepts(req) &&
            !answer.headers["content-encoding"] &&
            /json|text|javascript/.test(type);
          if (!compress) {
            res.writeHead(answer.statusCode ?? 502, answer.headers);
            answer.pipe(res);
            return;
          }
          const headers = { ...answer.headers };
          // The encoded length is unknown until the stream ends, and a stale
          // content-length would truncate the body.
          delete headers["content-length"];
          headers["content-encoding"] = "gzip";
          headers["vary"] = "Accept-Encoding";
          res.writeHead(answer.statusCode ?? 502, headers);
          answer.pipe(createGzip()).pipe(res);
        },
      );
      upstream.on("error", () => res.writeHead(502).end("api unreachable"));
      req.pipe(upstream);
      return;
    }

    const url = decodeURIComponent(raw.split("?")[0]);

    // phylo.io's bundle builds its workers with `new Worker(new URL(...,
    // import.meta.url))`, which webpack resolves RELATIVE TO THE PAGE. The
    // driver pages live under /harness/, so the chunks were requested at
    // /harness/src_worker_*.phylo.js and 404'd — silently, because a failed
    // Worker construction only shows up as a console error and the app simply
    // never finishes computing. Mapped here so the comparison actually runs.
    const worker = /^\/harness\/(src_worker_\w+\.phylo\.js)$/.exec(url);
    if (worker) {
      const chunk = join(PHYLOIO, "dist", worker[1]);
      res.writeHead(200, { "Content-Type": "text/javascript", "Cache-Control": "no-store" });
      createReadStream(chunk).pipe(res);
      return;
    }

    const prefix = Object.keys(ROOTS).find((p) => url.startsWith(p));
    // normalize() collapses any "..", so a crafted URL cannot escape the root.
    const file = prefix
      ? join(ROOTS[prefix], normalize(url.slice(prefix.length)))
      : join(WEB, normalize(url === "/" ? "index.html" : url));
    try {
      if (!statSync(file).isFile()) throw new Error("not a file");
    } catch {
      res.writeHead(404).end("not found");
      return;
    }
    const extension = extname(file);
    const compress = GZIP && COMPRESSIBLE.has(extension) && accepts(req);
    res.writeHead(200, {
      "Content-Type": TYPES[extension] ?? "application/octet-stream",
      "Cache-Control": "no-store", // every run pays the same cost
      ...(compress ? { "Content-Encoding": "gzip" } : {}),
      // No Content-Length when compressing: it would have to be the encoded
      // length, which is not known until the stream ends. Chrome reads the
      // chunked body either way and `request.sizes()` reports what arrived.
      Vary: "Accept-Encoding",
    });
    if (compress) createReadStream(file).pipe(createGzip()).pipe(res);
    else createReadStream(file).pipe(res);
  });
  return new Promise((resolve) => server.listen(port, () => resolve(server)));
}

if (import.meta.url === `file://${process.argv[1]}`) {
  const port = Number(process.argv[2] ?? 8099);
  await start(port);
  console.log(`serving on http://localhost:${port}/  (web build at /, harness/ phyloio/ trees/, api -> :${API_PORT})`);
}

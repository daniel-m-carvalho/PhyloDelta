import { readFileSync } from "node:fs";
import { defineConfig } from "vite";

/**
 * The published build: ESM in `dist/`, one file per entry point (§48).
 *
 * Only what is published is built here. Inside the workspace the web app reads
 * the TypeScript source through the `source` export condition, so this build
 * is never in the development loop and cannot go stale under it.
 *
 * Dependencies and peers stay imports, not bundled: sigma and graphology are
 * peers because the consumer must share one instance with the library
 * (package.json), and a bundled copy would be a second one.
 */
const manifest = JSON.parse(readFileSync(new URL("./package.json", import.meta.url), "utf8"));
const external = [
  ...Object.keys(manifest.dependencies ?? {}),
  ...Object.keys(manifest.peerDependencies ?? {}),
];

export default defineConfig({
  build: {
    outDir: "dist",
    emptyOutDir: true,
    target: "es2020",
    minify: false,
    sourcemap: false,
    lib: {
      entry: {
        index: "src/index.ts",
        performance: "src/performance/index.ts",
      },
      formats: ["es"],
    },
    rolldownOptions: {
      // "sigma" and its subpaths ("sigma/rendering", …) alike.
      external: (id) => external.some((name) => id === name || id.startsWith(`${name}/`)),
    },
  },
});

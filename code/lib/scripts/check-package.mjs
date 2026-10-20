#!/usr/bin/env node
/**
 * Can someone outside this repository build an app on the published package?
 * (DECISIONS §48.)
 *
 * The workspace cannot answer that: the web app reads the library's source
 * through the `source` condition, so it would pass with `dist/` missing or
 * wrong. This packs the library as `npm publish` would, installs the tarball
 * into an empty app that knows nothing of the condition, and uses it there:
 *
 *   1. the tarball holds the build, the types and the README — and no source,
 *      tests or test support;
 *   2. a TypeScript app typechecks against it (moduleResolution "bundler",
 *      what Vite and webpack apps use);
 *   3. a bundler builds that app from it, resolving the package's default
 *      conditions, so `dist/` is what gets bundled;
 *   4. Node imports the renderer-free entry `/performance` and runs it.
 *
 * Offline: the app's dependencies (sigma, graphology, newick) are linked from
 * this workspace's node_modules rather than downloaded.
 */

import { execFileSync } from "node:child_process";
import {
  existsSync,
  mkdirSync,
  mkdtempSync,
  readFileSync,
  rmSync,
  symlinkSync,
  writeFileSync,
} from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const lib = dirname(dirname(fileURLToPath(import.meta.url)));
const workspace = dirname(lib);
const bin = (name) => join(workspace, "node_modules", ".bin", name);
const manifest = JSON.parse(readFileSync(join(lib, "package.json"), "utf8"));

const scratch = mkdtempSync(join(tmpdir(), "check-package-"));
const failures = [];
const fail = (message) => failures.push(message);

try {
  // --- 1. what the tarball holds -------------------------------------------
  // Built here, then packed without `prepack` (which would build again and
  // print the build into the JSON): the tarball is never older than the
  // source it is checked against. Packed with a cache of its own: packing
  // needs nothing from one, and a user cache npm cannot write to (root-owned
  // files, an old npm bug) otherwise fails the check with EACCES.
  execFileSync("npm", ["run", "build"], { cwd: lib, stdio: ["ignore", "ignore", "inherit"] });
  const pack = ["pack", "--json", "--ignore-scripts", "--pack-destination", scratch];
  const [packed] = JSON.parse(
    execFileSync("npm", [...pack, "--cache", join(scratch, "npm-cache")], {
      cwd: lib,
      encoding: "utf8",
      stdio: ["ignore", "pipe", "inherit"],
    }),
  );
  const files = packed.files.map((file) => file.path);
  for (const required of [
    "package.json",
    "README.md",
    "LICENSE",
    "dist/index.js",
    "dist/performance.js",
    "dist/types/index.d.ts",
    "dist/types/performance/index.d.ts",
  ]) {
    if (!files.includes(required)) fail(`the tarball has no ${required}`);
  }
  for (const file of files) {
    if (file.startsWith("src/")) fail(`the tarball ships source: ${file}`);
    if (/\.test\.|test_support|harness/.test(file)) fail(`the tarball ships a test file: ${file}`);
  }

  // --- an empty app with the tarball installed ------------------------------
  const app = join(scratch, "app");
  const installed = join(app, "node_modules", manifest.name);
  mkdirSync(installed, { recursive: true });
  execFileSync("tar", ["-xzf", join(scratch, packed.filename), "-C", installed, "--strip-components=1"]);
  for (const name of [...Object.keys(manifest.dependencies ?? {}), ...Object.keys(manifest.peerDependencies ?? {})]) {
    symlinkSync(join(workspace, "node_modules", name), join(app, "node_modules", name), "dir");
  }
  writeFileSync(join(app, "package.json"), JSON.stringify({ name: "consumer", private: true, type: "module" }));
  writeFileSync(
    join(app, "main.ts"),
    [
      `import { TreeViewer, countLeaves, parseNewick, type NewickNode } from "${manifest.name}";`,
      `import { CacheManager } from "${manifest.name}/performance";`,
      ``,
      `const tree: NewickNode = parseNewick("((a:1,b:1):1,c:2);");`,
      `export const leaves: number = countLeaves(tree);`,
      `export const cache = new CacheManager<string>({ budgetBytes: 1024 });`,
      `export function mount(container: HTMLElement): TreeViewer {`,
      `  const viewer = new TreeViewer(container, {});`,
      `  viewer.setTree(tree);`,
      `  return viewer;`,
      `}`,
    ].join("\n"),
  );

  // --- 2. it typechecks ------------------------------------------------------
  writeFileSync(
    join(app, "tsconfig.json"),
    JSON.stringify({
      compilerOptions: {
        target: "ES2022",
        module: "ESNext",
        moduleResolution: "bundler",
        lib: ["ES2022", "DOM"],
        strict: true,
        noEmit: true,
        // The package's own declarations are checked too, not skipped. That
        // checks sigma's as well, which need Node's `events` types — as they
        // do in any app that uses sigma — hence @types/node, as Vite apps have.
        skipLibCheck: false,
        typeRoots: [join(workspace, "node_modules", "@types")],
        types: ["node"],
      },
      files: ["main.ts"],
    }),
  );
  try {
    execFileSync(bin("tsc"), ["-p", app], { encoding: "utf8", stdio: "pipe" });
  } catch (error) {
    fail(`an app does not typecheck against the package:\n${error.stdout}${error.stderr}`);
  }

  // --- 3. a bundler builds it ------------------------------------------------
  const { build } = await import("vite");
  try {
    await build({
      root: app,
      configFile: false,
      logLevel: "silent",
      build: {
        outDir: join(scratch, "bundle"),
        lib: { entry: join(app, "main.ts"), formats: ["es"], fileName: "app" },
      },
    });
  } catch (error) {
    fail(`a bundler cannot build an app from the package: ${error.message}`);
  }

  // --- 4. Node runs the renderer-free entry ---------------------------------
  try {
    const out = execFileSync(
      "node",
      [
        "--input-type=module",
        "-e",
        `const { CacheManager } = await import("${manifest.name}/performance");
         const cache = new CacheManager({ budgetBytes: 10 });
         cache.set("a", "x", 4);
         process.stdout.write(String(cache.get("a")));`,
      ],
      { cwd: app, encoding: "utf8", stdio: "pipe" },
    );
    if (out !== "x") fail(`the /performance entry ran but returned ${JSON.stringify(out)}`);
  } catch (error) {
    fail(`Node cannot import ${manifest.name}/performance:\n${error.stderr}`);
  }

  if (!existsSync(join(lib, "dist", "index.js"))) fail("packing did not build dist/");
  if (failures.length) {
    console.error(failures.map((message) => `✗ ${message}`).join("\n"));
    process.exitCode = 1;
  } else {
    console.log(
      `✓ ${packed.filename}: ${files.length} files, ${(packed.size / 1024).toFixed(0)} kB packed; ` +
        "typechecks, bundles and runs in an app outside the workspace",
    );
  }
} finally {
  rmSync(scratch, { recursive: true, force: true });
}

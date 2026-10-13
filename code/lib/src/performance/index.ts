/**
 * Caching, standalone.
 *
 * A separate entry point (`phylo-tree-viewer/performance`) because nothing in
 * here touches the renderer, and the package root does: importing it pulls in
 * Sigma, which needs a WebGL context and therefore a browser. A consumer that
 * wants an LRU should not have to provide one — the frontend's slice cache runs
 * in plain unit tests, and the root import made three suites fail on
 * `WebGL2RenderingContext is not defined`.
 *
 * The split is also the honest statement of the dependency: this code is
 * domain-blind and renderer-blind, and the export map now says so.
 */

export { CacheManager } from "./cache_manager";
export type { CacheManagerOptions, CacheCallback } from "./cache_manager";
export { CacheEntry } from "./cache_entry";
export type { CacheTier } from "./cache_entry";

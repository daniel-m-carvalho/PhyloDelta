/**
 * Holding slices the user has already seen.
 *
 * The library ships a generic two-tier LRU (`CacheManager`) and it was exported
 * but never wired to anything — every navigation, including pressing Back onto
 * a view that had just been on screen, went to the network. That is ~2.9 ms and
 * ~6 KB, so it was never slow; but it is the one operation where a tool holding
 * the whole tree in memory has a real advantage, and conceding it for nothing
 * was a gap rather than a decision.
 *
 * This module is the domain half of the seam the library deliberately leaves
 * open: it knows what a slice request *is* (so it can key one), what a slice
 * *costs* (so it can be bounded in bytes), and which slices are on screen (so
 * those are the ones protected from eviction). The cache itself knows none of
 * that.
 *
 * **What is cached is the server's response, not the built tree.** `labelClades`
 * changes only display names, so it must rebuild the viewer's tree — but it is
 * the same slice, and making it part of the key would throw away a perfectly
 * good response every time the option is toggled.
 */

import { CacheManager } from "phylo-tree-viewer/performance";
import type { TreeSlice } from "./types";

/**
 * Total bytes of slices held, across both panels.
 *
 * Chosen against the two numbers that matter, not picked for roundness. A
 * slice measures 5.4–6.9 KB at every tree size — that is the whole mechanism,
 * a payload sized to the viewport rather than to the tree — so this holds
 * roughly 300 of them. A navigation session visits tens, so the bound is not
 * the thing a user meets; it is the thing that guarantees the claim.
 *
 * And it must stay **independent of tree size**, which is the claim itself:
 * the frontend sits at 3.6 MB flat from 1,000 to 564,640 leaves, so a cache
 * that grew with the tree would give back exactly what the design bought. 2 MB
 * is a constant, and a deliberately small one against the heap it is added to.
 */
export const SLICE_CACHE_BYTES = 2 * 1024 * 1024;

/** Everything that changes what the server sends back. */
export interface SliceKeyParts {
  treeId: string;
  root?: number;
  budget: number;
  compare?: string;
  metric: string;
  keep?: number;
}

/**
 * The cache key: the request, exactly.
 *
 * Every field the API branches on and nothing else. `treeId` is encoded
 * because it is user-supplied and the separator must not be forgeable — two
 * different requests colliding on one key would serve the wrong tree, which is
 * far worse than a miss.
 */
export function sliceKey({ treeId, root, budget, compare, metric, keep }: SliceKeyParts): string {
  return [
    encodeURIComponent(treeId),
    root ?? "",
    budget,
    compare ?? "",
    metric,
    keep ?? "",
  ].join("|");
}

/**
 * Roughly how much memory a slice occupies.
 *
 * An estimate, and it only has to be one: its job is to bound the cache and to
 * rank entries against each other, not to report a true heap figure. What it
 * must not be is *constant* — slices differ by an order of magnitude between a
 * collapsed view and an expanded one, and charging them the same would let a
 * handful of expanded slices sit inside a budget that thinks it is nearly
 * empty.
 *
 * Eight bytes a number is the float slot; a string is two bytes a character
 * plus a header. Both are conservative in the safe direction — over-estimating
 * costs a slightly smaller effective cache, under-estimating breaks the bound.
 */
export function estimateSliceBytes(slice: TreeSlice): number {
  const { id, label } = slice.nodes;
  const n = id.length;

  // The columns are parallel, one entry per node, so the node count is enough:
  // four numeric (`id`, `parent`, `branch_len`, `true_leaf_count` — a null
  // occupies the same slot) and one boolean (`truncated`).
  let bytes = n * (8 * 4 + 4);
  for (const text of label) bytes += 24 + text.length * 2;

  const comparison = slice.comparison;
  if (comparison) {
    bytes += comparison.similarity.length * 8;
    bytes += comparison.corresponds.length * 8;
    for (const column of Object.values(comparison.columns ?? {})) bytes += column.length * 8;
  }

  // Object headers for the response's own fields; a floor, so a degenerate
  // one-node slice is never charged nothing at all.
  return bytes + 256;
}

/** Hits and misses, for measuring whether the cache earns its place. */
export interface SliceCacheStats {
  hits: number;
  misses: number;
  evictions: number;
  entries: number;
  rendered: number;
  bytes: number;
  budgetBytes: number;
}

export class SliceCache {
  #cache: CacheManager<TreeSlice>;
  #hits = 0;
  #misses = 0;
  #evictions = 0;

  constructor(budgetBytes: number = SLICE_CACHE_BYTES) {
    this.#cache = new CacheManager<TreeSlice>({
      budgetBytes,
      onEvict: () => {
        this.#evictions += 1;
      },
    });
  }

  /** The cached response for this request, or null. Counts the attempt. */
  get(parts: SliceKeyParts): TreeSlice | null {
    const found = this.#cache.get(sliceKey(parts));
    if (found) this.#hits += 1;
    else this.#misses += 1;
    return found;
  }

  /**
   * Store a response.
   *
   * A slice larger than the whole budget is simply not cached. The library
   * throws `RangeError` rather than evicting everything for one entry, which
   * is the right call — but "expand all" on a 5,000-leaf tree can legitimately
   * produce such a slice, and refusing to *display* it because it will not fit
   * in a cache would be absurd. The view is unaffected; only the next visit
   * pays for it again.
   */
  put(parts: SliceKeyParts, slice: TreeSlice): void {
    try {
      this.#cache.set(sliceKey(parts), slice, estimateSliceBytes(slice));
    } catch (failed) {
      if (!(failed instanceof RangeError)) throw failed;
    }
  }

  /** Mark the slice a panel is currently drawing, protecting it from eviction. */
  render(parts: SliceKeyParts): void {
    this.#cache.promote(sliceKey(parts));
  }

  /** The panel has moved on: this slice is an eviction candidate again. */
  unrender(parts: SliceKeyParts): void {
    this.#cache.demote(sliceKey(parts));
  }

  /** True while an identical request is already in flight. */
  isPending(parts: SliceKeyParts): boolean {
    return this.#cache.isPending(sliceKey(parts));
  }

  /** Share one in-flight request between callers that asked for the same thing. */
  share<P extends Promise<unknown>>(parts: SliceKeyParts, promise: P): P {
    return this.#cache.registerPending(sliceKey(parts), promise);
  }

  /**
   * Forget everything held for one tree.
   *
   * What the reload button means: not "re-render", but "what I have may be
   * wrong". A rebuilt store keeps the tree id and changes the bytes behind it,
   * so a cache that survived reload would serve the stale answer indefinitely
   * — the reload would visibly do nothing, which is the worst available
   * outcome.
   */
  invalidateTree(treeId: string): void {
    const prefix = `${encodeURIComponent(treeId)}|`;
    for (const key of this.#cache.keys()) {
      if (key.startsWith(prefix)) this.#cache.delete(key);
    }
  }

  clear(): void {
    this.#cache.clear();
    this.#hits = 0;
    this.#misses = 0;
    this.#evictions = 0;
  }

  stats(): SliceCacheStats {
    return {
      hits: this.#hits,
      misses: this.#misses,
      evictions: this.#evictions,
      entries: this.#cache.entryCount,
      rendered: this.#cache.renderedCount,
      bytes: this.#cache.currentBytes,
      budgetBytes: this.#cache.budgetBytes,
    };
  }
}

/**
 * One cache for the application, shared by both panels.
 *
 * Deliberately not one per panel. The budget is a statement about the
 * browser's memory, and two independent budgets would be two statements — a
 * panel showing collapsed views would hold its unused allowance while the
 * other evicted slices it was about to want back. One pool lets whichever
 * panel is being navigated use it.
 */
export const sliceCache = new SliceCache();

/**
 * Reachable from the page, for the benchmark harness.
 *
 * `bench/harness` drives the real application through Chrome and has to
 * distinguish a served navigation from a fetched one. Reading the counters is
 * the only honest way: timing alone cannot tell a cache hit from a fast
 * server. Read-only from the harness's point of view, apart from `clear()`,
 * which is how a run starts from cold.
 */
declare global {
  interface Window {
    __phylodeltaSliceCache?: SliceCache;
  }
}
if (typeof window !== "undefined") window.__phylodeltaSliceCache = sliceCache;

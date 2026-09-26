/**
 * What the slice cache must and must not do.
 *
 * The bound is the part that matters: this project's claim is that the browser
 * holds an amount that does not grow with the tree, and a cache is the easiest
 * possible way to give that back by accident.
 */

import { describe, expect, it } from "vitest";
import {
  SliceCache,
  SLICE_CACHE_BYTES,
  estimateSliceBytes,
  sliceKey,
} from "./sliceCache";
import type { TreeSlice } from "./types";

function slice(nodes: number, { labels = 8, compare = false } = {}): TreeSlice {
  const range = Array.from({ length: nodes }, (_, k) => k);
  return {
    tree: "t",
    root: 0,
    budget: 120,
    displayed_leaves: nodes,
    hidden_leaves: 0,
    total_leaves: nodes,
    nodes: {
      id: range,
      parent: range.map((k) => k - 1),
      label: range.map(() => "x".repeat(labels)),
      branch_len: range.map(() => 0.1),
      true_leaf_count: range.map(() => 1),
      truncated: range.map(() => false),
    },
    comparison: compare
      ? { similarity: range.map(() => 0.5), corresponds: range.map((k) => k) }
      : null,
  };
}

const parts = (over: Partial<Parameters<typeof sliceKey>[0]> = {}) => ({
  treeId: "vibrio_nj",
  budget: 120,
  metric: "rf",
  ...over,
});

describe("the key is the request", () => {
  it("separates every field the server branches on", () => {
    const base = parts();
    const keys = new Set([
      sliceKey(base),
      sliceKey({ ...base, root: 12 }),
      sliceKey({ ...base, budget: 125 }),
      sliceKey({ ...base, compare: "pair1" }),
      sliceKey({ ...base, metric: "jaccard" }),
      sliceKey({ ...base, keep: 3296 }),
    ]);
    expect(keys.size).toBe(6);
  });

  it("is stable for the same request", () => {
    expect(sliceKey(parts({ root: 5 }))).toBe(sliceKey(parts({ root: 5 })));
  });

  it("distinguishes an omitted root from root 0", () => {
    // Root 0 is the stored tree's actual root and a legitimate explicit value;
    // if it keyed the same as "omitted" the distinction would be invisible.
    expect(sliceKey(parts({ root: 0 }))).not.toBe(sliceKey(parts()));
  });

  it("cannot be forged by a tree id containing the separator", () => {
    // Two different trees colliding on one key serves the wrong tree, which is
    // far worse than a miss.
    const a = sliceKey(parts({ treeId: "a|120|" }));
    const b = sliceKey(parts({ treeId: "a" }));
    expect(a).not.toBe(b);
  });
});

describe("size estimation", () => {
  it("is not constant — it grows with the slice", () => {
    // The failure this guards: charging every slice the same would let a
    // handful of expanded slices sit inside a budget that thinks it is empty.
    expect(estimateSliceBytes(slice(400))).toBeGreaterThan(
      estimateSliceBytes(slice(40)) * 5,
    );
  });

  it("charges for comparison columns, which are half a compared slice", () => {
    expect(estimateSliceBytes(slice(100, { compare: true }))).toBeGreaterThan(
      estimateSliceBytes(slice(100)),
    );
  });

  it("charges for long labels", () => {
    expect(estimateSliceBytes(slice(100, { labels: 60 }))).toBeGreaterThan(
      estimateSliceBytes(slice(100, { labels: 8 })),
    );
  });

  it("lands in the right order of magnitude for a real slice", () => {
    // Measured on the wire: 5.4–6.9 KB for a ~120-leaf compared slice. An
    // estimate that were out by 100x would make the byte budget meaningless.
    const bytes = estimateSliceBytes(slice(120, { compare: true, labels: 20 }));
    expect(bytes).toBeGreaterThan(2_000);
    expect(bytes).toBeLessThan(60_000);
  });
});

describe("the bound", () => {
  it("never exceeds its budget, however many slices are stored", () => {
    const cache = new SliceCache(64 * 1024);
    for (let root = 0; root < 500; root++) cache.put(parts({ root }), slice(120));
    expect(cache.stats().bytes).toBeLessThanOrEqual(64 * 1024);
    expect(cache.stats().evictions).toBeGreaterThan(0);
  });

  it("is a constant, not a function of tree size", () => {
    // The claim itself: 3.6 MB flat from 1,000 to 564,640 leaves. A cache that
    // scaled with the tree would hand back exactly what the design bought.
    expect(SLICE_CACHE_BYTES).toBe(2 * 1024 * 1024);
  });

  it("holds enough slices that a session never meets the bound", () => {
    const cache = new SliceCache();
    for (let root = 0; root < 60; root++) cache.put(parts({ root }), slice(120, { compare: true }));
    expect(cache.stats().entries).toBe(60);
    expect(cache.stats().evictions).toBe(0);
  });

  it("declines an oversized slice instead of throwing or emptying itself", () => {
    // "Expand all" on a 5,000-leaf tree can exceed the whole budget. Refusing
    // to display it because it will not fit in a cache would be absurd.
    const cache = new SliceCache(16 * 1024);
    cache.put(parts({ root: 1 }), slice(120));
    expect(() => cache.put(parts({ root: 2 }), slice(20_000))).not.toThrow();
    expect(cache.get(parts({ root: 2 }))).toBeNull();
    expect(cache.get(parts({ root: 1 }))).not.toBeNull();
  });
});

describe("what is on screen is protected", () => {
  it("keeps a rendered slice while warm ones are evicted around it", () => {
    const cache = new SliceCache(64 * 1024);
    const visible = parts({ root: 1 });
    cache.put(visible, slice(120));
    cache.render(visible);
    for (let root = 100; root < 400; root++) cache.put(parts({ root }), slice(120));

    expect(cache.get(visible)).not.toBeNull();
    expect(cache.stats().rendered).toBe(1);
  });

  it("releases a slice the panel has moved off", () => {
    const cache = new SliceCache();
    const first = parts({ root: 1 });
    cache.render(first);
    cache.put(first, slice(10));
    cache.render(first);
    cache.unrender(first);
    expect(cache.stats().rendered).toBe(0);
  });
});

describe("reload means what it says", () => {
  it("forgets one tree and keeps the other", () => {
    const cache = new SliceCache();
    cache.put(parts({ treeId: "left", root: 1 }), slice(10));
    cache.put(parts({ treeId: "right", root: 1 }), slice(10));

    cache.invalidateTree("left");

    expect(cache.get(parts({ treeId: "left", root: 1 }))).toBeNull();
    expect(cache.get(parts({ treeId: "right", root: 1 }))).not.toBeNull();
  });

  it("does not take a tree whose encoded id is a prefix of another", () => {
    const cache = new SliceCache();
    cache.put(parts({ treeId: "vibrio" }), slice(10));
    cache.put(parts({ treeId: "vibrio_nj" }), slice(10));

    cache.invalidateTree("vibrio");

    expect(cache.get(parts({ treeId: "vibrio" }))).toBeNull();
    expect(cache.get(parts({ treeId: "vibrio_nj" }))).not.toBeNull();
  });
});

describe("hit accounting", () => {
  it("counts hits and misses, because timing alone cannot tell them apart", () => {
    const cache = new SliceCache();
    cache.get(parts({ root: 1 })); // miss
    cache.put(parts({ root: 1 }), slice(10));
    cache.get(parts({ root: 1 })); // hit
    cache.get(parts({ root: 1 })); // hit

    expect(cache.stats()).toMatchObject({ hits: 2, misses: 1 });
  });
});

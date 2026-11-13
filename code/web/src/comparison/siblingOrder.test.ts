import { describe, expect, it, vi } from "vitest";

// The library's entry point loads its renderer, which reads WebGL classes the
// test DOM does not have. Nothing here draws; only the tree functions run.
vi.hoisted(() => {
  const g = globalThis as Record<string, unknown>;
  g.WebGL2RenderingContext ??= class {};
  g.WebGLRenderingContext ??= class {};
});
import { NEVER_COLLAPSED, prepareTree, type NewickNode } from "phylo-tree-viewer";
import realSlice from "../tree/__fixtures__/slice.json";
import { treeFromSlice } from "../tree/fromSlice";
import { gradientFrom } from "../tree/comparisonValues";
import type { TreeSlice } from "../api/types";
import { siblingOrders, storedIdOf } from "./siblingOrder";

const slice = realSlice as unknown as TreeSlice;

/** Every node as `id -> [parent id, similarity]`: the structure and the values, not the order. */
function facts(root: NewickNode, similarityOf: (id: number) => number | undefined) {
  const out = new Map<number, [number | undefined, number | undefined]>();
  const walk = (node: NewickNode, parent: number | undefined) => {
    const id = storedIdOf(node)!;
    out.set(id, [parent, similarityOf(id)]);
    for (const child of node.branchset ?? []) walk(child, id);
  };
  walk(root, undefined);
  return out;
}

describe("order to match the other tree (§55.3)", () => {
  const built = treeFromSlice(slice);
  const gradient = gradientFrom(built, slice.comparison);
  const [, right] = siblingOrders(true, gradient.correspondingTo);
  const plain = prepareTree(built.root, NEVER_COLLAPSED, 100_000)!;
  const matched = prepareTree(built.root, NEVER_COLLAPSED, 100_000, right)!;

  it("changes no clade, no value and no id: only the order of siblings", () => {
    expect(facts(matched, gradient.similarityOf)).toEqual(facts(plain, gradient.similarityOf));
  });

  it("puts each node's matched children in their counterparts' order, the unmatched after", () => {
    let rotated = 0;
    const walk = (node: NewickNode) => {
      const keys = (node.branchset ?? []).map((child) => gradient.correspondingTo(storedIdOf(child)!));
      const matchedKeys = keys.filter((k) => k !== undefined) as number[];
      expect(matchedKeys).toEqual([...matchedKeys].sort((a, b) => a - b));
      expect(keys.slice(0, matchedKeys.length).every((k) => k !== undefined)).toBe(true);
      for (const child of node.branchset ?? []) walk(child);
    };
    walk(matched);
    const order = (root: NewickNode): number[] => [storedIdOf(root)!, ...(root.branchset ?? []).flatMap(order)];
    if (order(matched).join() !== order(plain).join()) rotated += 1;
    // The fixture's trees disagree, so following the other tree must move something.
    expect(rotated).toBe(1);
  });

  it("is the usual order when switched off", () => {
    const [l, r] = siblingOrders(false, gradient.correspondingTo);
    const a = prepareTree(built.root, NEVER_COLLAPSED, 100_000, l)!;
    const b = prepareTree(built.root, NEVER_COLLAPSED, 100_000, r)!;
    const ids = (root: NewickNode): number[] => [storedIdOf(root)!, ...(root.branchset ?? []).flatMap(ids)];
    expect(ids(a)).toEqual(ids(plain));
    expect(ids(b)).toEqual(ids(plain));
  });
});
